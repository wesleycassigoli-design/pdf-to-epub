"""
html_sanitizer.py
Sanitiza HTML inline vindo do editor de EPUB (/reader/[id], modo edição)
antes de gravar dentro do XHTML do livro. Whitelist estrita — nunca grava
HTML arbitrário vindo do navegador dentro do EPUB.

Regras:
- Tags permitidas: b, i, em, strong, br, span — sem NENHUM atributo.
- Tags perigosas (script, style, iframe, object, embed, link, meta, form,
  input, button) são removidas por completo, incluindo o conteúdo interno.
- Qualquer outra tag desconhecida é removida (unwrap), mas o texto/filhos
  internos são preservados.
- Comentários e processing instructions são descartados.
"""

import lxml.html

ALLOWED_TAGS = {"b", "i", "em", "strong", "br", "span"}
STRIP_ENTIRELY_TAGS = {"script", "style", "iframe", "object", "embed", "link", "meta", "form", "input", "button"}


def _sanitize_element(el) -> None:
    for child in list(el):
        tag = child.tag
        if not isinstance(tag, str):
            # Comentário ou processing instruction — descarta.
            child.drop_tree()
            continue
        tag_lower = tag.lower()
        if tag_lower in STRIP_ENTIRELY_TAGS:
            child.drop_tree()
            continue
        _sanitize_element(child)
        if tag_lower not in ALLOWED_TAGS:
            child.drop_tag()
        else:
            for attr in list(child.attrib):
                del child.attrib[attr]


def sanitize_inline_html(html: str) -> str:
    """Sanitiza um fragmento de HTML inline (o novo conteúdo de um <p>/<h2>/
    <h3>/<li> editado). Retorna HTML seguro pra inserir dentro do XHTML do
    EPUB — nunca lança exceção para entrada malformada, na pior hipótese
    retorna string vazia."""
    if not html or not html.strip():
        return ""
    try:
        root = lxml.html.fromstring(f"<div>{html}</div>")
    except Exception:
        # HTML malformado o suficiente pra nem o parser tolerante do lxml
        # dar conta — mais seguro tratar como texto puro escapado.
        return (html
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))
    _sanitize_element(root)
    serialized = lxml.html.tostring(root, encoding="unicode", method="xml")
    return serialized[len("<div>"):-len("</div>")]
