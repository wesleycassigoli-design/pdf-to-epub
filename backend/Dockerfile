FROM python:3.12-slim

# System deps (inclui Tesseract para OCR)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-por \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Diretórios de output
RUN mkdir -p /app/output /tmp/pdfepub

# Nunca rodar como root
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app /tmp/pdfepub
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
