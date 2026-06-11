# PDF → EPUB3 Converter

Converte PDFs em **EPUB3 Fixed Layout**, preservando diagramação, imagens, tabelas e estilos do documento original. Suporta geração de EPUB completo e EPUBs separados por capítulo.

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Vercel)                        │
│  Next.js 14 + React + TailwindCSS + TypeScript                  │
│  Upload / Dashboard / Status / Histórico / Download             │
└─────────────────────────┬───────────────────────────────────────┘
                          │ REST API
┌─────────────────────────▼───────────────────────────────────────┐
│                        BACKEND (Railway)                         │
│  FastAPI + Python                                               │
│  POST /upload → enfileira task Celery                           │
│  GET  /status/{id} → polling                                    │
│  GET  /download/{id} → EPUB                                     │
└──────────┬────────────────────────┬────────────────────────────┘
           │                        │
     ┌─────▼──────┐         ┌───────▼────────┐
     │   Redis    │         │ Supabase        │
     │  (broker)  │         │ PostgreSQL +    │
     └─────┬──────┘         │ Storage         │
           │                └────────────────┘
    ┌──────▼──────┐
    │Celery Worker│
    │  PyMuPDF    │ ← analisa PDF
    │  EPUB Gen.  │ ← gera EPUB3 Fixed Layout
    │  Tesseract  │ ← OCR se escaneado
    └─────────────┘
```

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Frontend | Next.js 14, React, TailwindCSS, TypeScript |
| Backend | Python 3.12, FastAPI |
| Fila | Celery + Redis |
| Banco | PostgreSQL (Supabase) |
| Storage | Supabase Storage |
| PDF | PyMuPDF (fitz) |
| EPUB | Geração própria (EPUB3 Fixed Layout via zipfile) |
| OCR | Tesseract OCR |
| Deploy FE | Vercel |
| Deploy BE | Railway |
| Infra | Docker + Docker Compose |

---

## Instalação Local (5 minutos)

### Pré-requisitos
- Docker + Docker Compose
- Node.js 20+ (para dev frontend sem Docker)

### Passo a passo

```bash
# 1. Clone o repositório
git clone <repo-url>
cd pdf-to-epub

# 2. Execute o setup automatizado
chmod +x scripts/setup.sh
./scripts/setup.sh
```

O script:
- Cria `.env` a partir do `.env.example`
- Cria `frontend/.env.local`
- Faz build e sobe todos os containers

Acesse:
- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **Flower** (monitor Celery): http://localhost:5555

---

## Configuração Manual

### Variáveis de Ambiente (`.env`)

```bash
# Obrigatórias
DATABASE_URL=postgresql://user:password@db:5432/pdfepub
REDIS_URL=redis://redis:6379/0
SECRET_KEY=gere-uma-chave-aleatoria-longa

# Supabase (opcional em dev, obrigatório em produção)
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_SERVICE_KEY=sua-service-role-key
SUPABASE_STORAGE_BUCKET=pdf-epub-files

# CORS (produção)
CORS_ORIGINS=https://sua-app.vercel.app
```

### Variáveis do Frontend (`frontend/.env.local`)

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## Deploy Produção

### Supabase

1. Crie projeto em https://supabase.com
2. No SQL Editor, execute o conteúdo de `scripts/init.sql`
3. Em Storage, crie bucket `pdf-epub-files` (público)
4. Copie `SUPABASE_URL` e `SUPABASE_SERVICE_KEY` das configurações

### Railway (Backend)

1. Crie projeto em https://railway.app
2. Conecte ao repositório, aponte para `/backend`
3. Configure variáveis de ambiente (copie do `.env.example`)
4. Railway detecta o Dockerfile automaticamente

Para o worker Celery, crie um segundo serviço no mesmo projeto:
- Start command: `celery -A app.workers.celery_app worker --loglevel=info --concurrency=2`

Para Redis, adicione o plugin Redis no Railway.

### Vercel (Frontend)

1. Importe o repositório em https://vercel.com
2. Configure Root Directory como `frontend`
3. Adicione variável: `NEXT_PUBLIC_API_URL=https://sua-api.railway.app`
4. Deploy automático

---

## Estrutura do Projeto

```
pdf-to-epub/
├── frontend/                    # Next.js app
│   └── src/
│       ├── app/                 # Rotas (App Router)
│       ├── components/          # Componentes React
│       ├── hooks/               # Custom hooks
│       └── lib/                 # API client, utils
├── backend/                     # FastAPI app
│   └── app/
│       ├── main.py              # Entry point
│       ├── config.py            # Settings
│       ├── database.py          # SQLAlchemy async
│       ├── models/              # ORM models
│       ├── schemas/             # Pydantic schemas
│       ├── routers/             # Endpoints
│       ├── services/            # Lógica de negócio
│       │   ├── pdf_processor.py # Análise PDF (PyMuPDF)
│       │   ├── epub_generator.py# Geração EPUB3
│       │   ├── ocr_service.py   # Tesseract OCR
│       │   └── storage_service.py # Upload Supabase
│       └── workers/
│           └── celery_app.py    # Tasks Celery
├── scripts/
│   ├── init.sql                 # Schema PostgreSQL
│   └── setup.sh                 # Setup local
├── docker-compose.yml
└── .env.example
```

---

## API Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/upload/` | Upload PDF + enfileira conversão |
| `GET`  | `/books` | Lista todos os livros |
| `GET`  | `/books/{id}` | Detalhes do livro + capítulos |
| `GET`  | `/status/{id}` | Status da conversão (para polling) |
| `GET`  | `/chapters/{id}` | Capítulos de um livro |
| `GET`  | `/download/{id}` | Download EPUB completo |
| `GET`  | `/download/{id}/chapter/{ch_id}` | Download EPUB do capítulo |
| `GET`  | `/conversions/{id}` | Logs de conversão |
| `GET`  | `/health` | Health check |

---

## Como funciona a conversão

1. **Upload**: PDF é validado (magic bytes, extensão, tamanho) e salvo
2. **Análise**: PyMuPDF extrai estrutura, detecta capítulos por TOC digital ou heurística tipográfica
3. **OCR**: Se PDF for escaneado (>50% das páginas sem texto), Tesseract é ativado automaticamente
4. **EPUB completo**: Cada página vira um XHTML com o SVG da página embutido (Fixed Layout)
5. **EPUBs por capítulo**: Idem, mas com páginas do capítulo apenas
6. **Upload**: Arquivos enviados ao Supabase Storage
7. **Download**: Links disponíveis no dashboard

### Por que SVG?

EPUB3 Fixed Layout com SVG preserva o layout exato do PDF — fontes, posicionamento, imagens — sem tentativa de reflow de texto que quebraria a diagramação.

---

## Observações

- **Fidelidade ao conteúdo**: o sistema nunca altera texto, pontuação ou estrutura — apenas converte o formato visual
- **Compatibilidade**: testado em Apple Books, Calibre, Adobe Digital Editions
- **Limite padrão**: 100MB por arquivo (configurável via `MAX_UPLOAD_MB`)
- **Concorrência**: 2 workers Celery por padrão (ajuste em `docker-compose.yml`)
