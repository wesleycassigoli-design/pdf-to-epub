# Fontes do template "Caderno de Conceitos Matadores — v2"

- `AfyaSans-Regular.ttf`, `AfyaSans-Bold.ttf`, `AfyaSans-Italic.ttf`,
  `AfyaSans-BoldItalic.ttf` — fontes **completas**, copiadas de
  `backend/app/assets/fonts/ttf/` (mesmo acervo usado pelo template Medcel).
  São as únicas fontes de fato embutidas no EPUB gerado por
  `epub_generator_caderno_v2.py`.

- `AfyaSansPro-Light.ttf`, `AfyaSansPro-Regular.ttf`, `AfyaSansPro-Bold.ttf`,
  `AfyaSansPro-ExtraBold.ttf` — **NÃO são fontes completas**. São o
  subconjunto (subset) extraído diretamente de
  `_referencia_caderno_v2/00_MODELO_CONCEITOS_MATADORES_2026.pdf` via
  `fitz.Document.extract_font()`, porque o acervo do Medcel não tem a
  família "Pro" (só a "AfyaSans" normal). **Ficam neste diretório só como
  referência para uma futura substituição — não são usadas no CSS
  (`brand_caderno_v2.css`) nem embutidas no EPUB gerado.**

## Por que AfyaSansPro não é usada

Verificado empiricamente (Chromium headless, PyMuPDF/fontTools) ao preparar
este template:

1. `AfyaSansPro-Light` e `AfyaSansPro-ExtraBold` foram embutidas no PDF de
   origem como fontes Type0 (CID-keyed, `Identity-H`) — **não têm tabela
   `cmap`**. Sem `cmap`, nenhum motor de renderização baseado em
   texto/Unicode (Chromium, WebKit, e por extensão a maioria dos leitores de
   EPUB) consegue usá-las via `@font-face`: o texto sempre cai pra fonte
   serifada padrão do sistema. Isso não tem conserto sem a fonte original —
   só reextrair de um PDF onde essas variantes tenham sido embutidas como
   TrueType simples (`WinAnsiEncoding`), ou obter a fonte comercial completa.

2. `AfyaSansPro-Regular` e `AfyaSansPro-Bold` foram embutidas como TrueType
   simples e têm `cmap` válido, mas (a) os bytes extraídos por
   `extract_font()` falham a sanitização de fonte do Chromium/WebKit (OTS) —
   resolvido reprocessando com `fontTools.ttLib.TTFont(...).save(...)`, que
   recalcula checksums/tabelas — e (b) mesmo depois de reparadas, só contêm
   os glifos dos caracteres que aparecem nesse PDF de exemplo específico.
   Qualquer texto gerado depois (ex.: título de um capítulo com uma palavra
   que não apareça no PDF de referência) teria caracteres faltantes.

Por isso `pdf_processor_caderno_v2.py` e `epub_generator_caderno_v2.py`
usam **AfyaSans-Bold/AfyaSans-Regular** (fonte completa) como substituto
visual na página INCIDÊNCIA e no Sumário gerado — mais seguro que arriscar
texto quebrado ou invisível num leitor de EPUB real.

## Para repor com a fonte completa no futuro

Substituir os 4 arquivos `AfyaSansPro-*.ttf` deste diretório pelas fontes
completas (mesma família usada pelo Medcel para a família "Pro", se/quando
estiver disponível), depois trocar as referências `"AfyaSans-Bold"` /
`"AfyaSans-Regular"` de volta para `"AfyaSansPro-ExtraBold"` /
`"AfyaSansPro-Bold"` / `"AfyaSansPro-Regular"` nos seletores `.sumario-titulo`,
`.sumario-lista a`, `.incidencia-titulo`, `.incidencia-intro`,
`.incidencia-numero` e `.incidencia-rotulo` de `brand_caderno_v2.css`, e
adicionar os 4 arquivos de volta a `_FONT_FILES` em
`epub_generator_caderno_v2.py`.
