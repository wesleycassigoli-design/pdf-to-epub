#!/usr/bin/env bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  PDF → EPUB3 Converter — Setup Local"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Copia .env.example se não existe .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✓ .env criado a partir do .env.example"
  echo "  → Edite o arquivo .env com suas configurações antes de continuar"
  echo ""
fi

# Copia .env.local do frontend
if [ ! -f frontend/.env.local ]; then
  cp frontend/.env.local.example frontend/.env.local
  echo "✓ frontend/.env.local criado"
fi

# Verifica Docker
if ! command -v docker &> /dev/null; then
  echo "✗ Docker não encontrado. Instale Docker antes de continuar."
  exit 1
fi

if ! command -v docker compose &> /dev/null; then
  echo "✗ Docker Compose não encontrado."
  exit 1
fi

echo "✓ Docker encontrado"

# Build e sobe os containers
echo ""
echo "→ Construindo imagens Docker..."
docker compose build

echo ""
echo "→ Subindo containers..."
docker compose up -d

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ Sistema rodando!"
echo ""
echo "  Frontend:    http://localhost:3000"
echo "  API:         http://localhost:8000"
echo "  API Docs:    http://localhost:8000/docs"
echo "  Flower:      http://localhost:5555"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
