"""
epub_editor_service.py
Aplica edições (texto + substituição de imagem) num EPUB JÁ GERADO, sem
reprocessar o DOCX original — o DOCX permanece intocado no Storage. Baixa
o EPUB atual, localiza o documento de conteúdo via content.opf (spine +
manifest — funciona igual pros 3 templates de texto, sem hardcodar nome
de arquivo, já que Caderno usa Section0001.xhtml e Medcel/Genérico usam
chapter.xhtml), aplica as edições e devolve os bytes do novo zip. Quem
chama decide se valida (via conversion_service._validate_epub_zip) antes
de persistir — este módulo não sobe nada no Storage sozinho.
"""

import io
import zipfile
from dataclasses import dataclass
from lxml import etree
import structlog

from app.services.html_sanitizer import sanitize_inline_html

logger = structlog.get_logger()

XHTML_NS = "http://www.w3.org/1999/xhtml"
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB
EDITABLE_TEXT_TAGS = {"p", "h2", "h3", "li"}


class EpubEditError(Exception):
    """Erro esperado (entrada inválida, não um bug) — mensagem já pronta pro usuário."""


@dataclass
class TextEdit:
    edit_id: str
    html: str


@dataclass
class ImageEdit:
    edit_id: str
    data: bytes
    content_type: str


def _find_content_document(opf_bytes: bytes) -> str:
    """Resolve o caminho do documento de conteúdo via spine+manifest do
    content.opf. Genérico o bastante pra funcionar nos 3 templates de texto
    sem hardcodar nome de arquivo."""
    ns = {"opf": "http://www.idpf.org/2007/opf"}
    root = etree.fromstring(opf_bytes)
    manifest = {
        item.get("id"): item.get("href")
        for item in root.findall(".//opf:manifest/opf:item", ns)
    }
    spine_items = root.findall(".//opf:spine/opf:itemref", ns)
    if not spine_items:
        raise EpubEditError("EPUB sem spine — estrutura inesperada, não é possível editar.")
    href = manifest.get(spine_items[0].get("idref"))
    if not href:
        raise EpubEditError("Não foi possível localizar o documento de conteúdo do EPUB.")
    return f"OEBPS/{href}"


def _tag_name(el) -> str:
    if not isinstance(el.tag, str):
        return ""
    return etree.QName(el).localname


def apply_edits(
    epub_bytes: bytes,
    text_edits: list[TextEdit],
    image_edits: list[ImageEdit],
) -> bytes:
    """Aplica as edições sobre os bytes do EPUB atual e retorna os bytes do
    novo zip. Levanta EpubEditError (mensagem já pronta pro usuário) se
    algum edit_id for inválido/inconsistente."""
    zin = zipfile.ZipFile(io.BytesIO(epub_bytes))
    names = set(zin.namelist())

    opf_name = next((n for n in names if n.endswith("content.opf")), None)
    if not opf_name:
        raise EpubEditError("EPUB sem content.opf — estrutura inesperada.")

    content_path = _find_content_document(zin.read(opf_name))
    if content_path not in names:
        raise EpubEditError(f"Documento de conteúdo '{content_path}' não encontrado no EPUB.")

    tree = etree.fromstring(zin.read(content_path))

    applied_text = 0
    for edit in text_edits:
        el = tree.find(f'.//*[@data-edit-id="{edit.edit_id}"]')
        if el is None:
            raise EpubEditError(f"Elemento '{edit.edit_id}' não encontrado no documento.")
        tag = _tag_name(el)
        if tag not in EDITABLE_TEXT_TAGS:
            raise EpubEditError(f"Elemento '{edit.edit_id}' ({tag}) não é um texto editável.")

        safe_html = sanitize_inline_html(edit.html)
        for child in list(el):
            el.remove(child)
        # Envolve no MESMO namespace do documento (xmlns padrão da árvore) —
        # sem isso os filhos (b/i/span do texto sanitizado) ficam num
        # namespace diferente do resto do XHTML.
        wrapper = etree.fromstring(f'<{tag} xmlns="{XHTML_NS}">{safe_html}</{tag}>')
        el.text = wrapper.text
        for child in wrapper:
            el.append(child)
        applied_text += 1

    # O nome do arquivo de imagem é resolvido AQUI, a partir do src já
    # gravado no XHTML armazenado no servidor — nunca a partir do que o
    # frontend informa. O <img> renderizado no navegador tem o src reescrito
    # pelo epub.js pra uma blob: URL (pra exibição), então o frontend não
    # tem como saber com certeza qual é o nome real do arquivo; o data-edit-id
    # sozinho já é suficiente pra identificar a imagem de forma inequívoca.
    image_targets: dict[str, ImageEdit] = {}
    for edit in image_edits:
        el = tree.find(f'.//*[@data-edit-id="{edit.edit_id}"]')
        if el is None:
            raise EpubEditError(f"Elemento '{edit.edit_id}' não encontrado no documento.")
        if _tag_name(el) != "img":
            raise EpubEditError(f"Elemento '{edit.edit_id}' não é uma imagem.")

        current_filename = (el.get("src") or "").rsplit("/", 1)[-1]
        if not current_filename:
            raise EpubEditError(f"Elemento '{edit.edit_id}' não tem uma imagem associada.")
        image_path = f"OEBPS/Images/{current_filename}"
        if image_path not in names:
            raise EpubEditError(f"Imagem '{current_filename}' não encontrada no EPUB atual.")
        if len(edit.data) > MAX_IMAGE_BYTES:
            raise EpubEditError(
                f"Imagem '{current_filename}' excede o limite de {MAX_IMAGE_BYTES // (1024*1024)}MB."
            )
        image_targets[image_path] = edit

    new_xhtml_bytes = etree.tostring(tree, xml_declaration=True, encoding="utf-8")

    out_buffer = io.BytesIO()
    with zipfile.ZipFile(out_buffer, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            if info.filename == "mimetype":
                zout.writestr(
                    zipfile.ZipInfo("mimetype"),
                    zin.read("mimetype"),
                    compress_type=zipfile.ZIP_STORED,
                )
            elif info.filename == content_path:
                zout.writestr(content_path, new_xhtml_bytes)
            elif info.filename in image_targets:
                zout.writestr(info.filename, image_targets[info.filename].data)
            else:
                zout.writestr(info, zin.read(info.filename))

    zin.close()

    logger.info(
        "epub_edits_applied",
        text_edits_applied=applied_text,
        image_edits_applied=len(image_targets),
    )
    return out_buffer.getvalue()
