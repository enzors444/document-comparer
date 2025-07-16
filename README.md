# Comparador de Documentos Jurídicos em PDF

Este projeto é um sistema completo para extração, segmentação e comparação de documentos jurídicos em PDF, incluindo suporte a PDFs digitalizados (OCR). Ele permite comparar versões de documentos, identificar alterações e visualizar diferenças de forma clara e amigável.

## Funcionalidades
- **Extração robusta de texto** de PDFs nativos e digitalizados (OCR com EasyOCR).
- **Segmentação inteligente de frases** usando Stanza (Português).
- **Comparação detalhada** entre dois documentos, com detecção de adições, remoções e modificações.
- **Interface web moderna** para upload, comparação e visualização dos resultados.
- **API Flask** para integração e automação.
- **Suporte a CORS** para uso com frontends externos.

## Requisitos
- Python 3.10+
- Node.js (opcional, apenas se quiser customizar o frontend)

### Dependências principais (instaladas via `requirements.txt`):
- Flask
- stanza
- easyocr
- pymupdf
- pdfplumber
- pillow
- rapidfuzz

## Instalação

1. **Clone o repositório:**
   ```bash
   git clone <url-do-repo>
   cd comparer
   ```

2. **Crie um ambiente virtual (opcional, mas recomendado):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   venv\Scripts\activate    # Windows
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Baixe o modelo do Stanza para português (primeira execução):**
   O código já faz isso automaticamente, mas você pode rodar manualmente:
   ```python
   import stanza
   stanza.download('pt')
   ```

## Como usar

### Backend (API Flask)

1. **Inicie a API:**
   ```bash
   python src/api.py
   ```
   A API estará disponível em `http://127.0.0.1:8000`.

2. **Endpoints principais:**
   - `POST /api/comparar` — Recebe dois PDFs e retorna a comparação.
   - `POST /api/analisar` — Analisa um único PDF.
   - `GET /api/resultado/<id>` — Busca resultado salvo.
   - `GET /api/filtrar-alterados/<id>` — Retorna apenas segmentos alterados.

### Frontend (Interface Web)

1. **Abra o arquivo `index.html` no navegador.**
   - Não é necessário servidor web, basta abrir localmente.
   - Faça upload de dois PDFs e clique em "Comparar".
   - Veja o resultado na tabela, com destaques para adições, remoções e modificações.

> **Obs:** O frontend se comunica com a API Flask em `http://127.0.0.1:8000`. Certifique-se de que a API está rodando.

## Estrutura do Projeto

```
comparer/
├── src/
│   ├── api.py           # API Flask
│   ├── extrator.py      # Extração e segmentação de texto
│   ├── processador.py   # Orquestração do processamento
│   ├── comparador.py    # Lógica de comparação
│   ├── normalizador.py  # Limpeza e normalização de texto
│   ├── models.py        # Modelos de dados
│   └── utils.py         # Utilitários
├── uploads/             # PDFs enviados
├── resultados/api/      # Resultados das comparações
├── index.html           # Interface web (frontend)
├── requirements.txt     # Dependências Python
└── README.md            # Este arquivo
```

## Observações
- O sistema usa **apenas Stanza** para segmentação de frases.
- O OCR é feito exclusivamente com EasyOCR (não é necessário Tesseract).
- O código foi otimizado para rodar em Python 3.10+ e evitar dependências pesadas.
- Para produção, recomenda-se servir a API com Gunicorn ou outro WSGI server.

## Licença
Este projeto é open-source e pode ser adaptado conforme sua necessidade. 