# Extract — scanned PDF → editable DOCX/PPTX

Python sidecar for magical-pdf **Распознать** tab. Ported from [ocr-docs](https://github.com/beaver20007/ocr-docs) (Phase 5.1).

## Setup (Windows)

```powershell
cd extract
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:HF_HUB_DISABLE_SSL_VERIFICATION = "1"   # if corporate SSL
.\run-api.ps1
```

API: http://127.0.0.1:8765 — Swagger at `/docs`.

## Public beta (Railway)

Deploy from repo with **Root Directory** = `extract` — see [`../docs/DEPLOY_EXTRACT.md`](../docs/DEPLOY_EXTRACT.md).  
Config: [`railway.toml`](railway.toml), [`Dockerfile`](Dockerfile).

## Jobs data

`extract/data/jobs/` (gitignored). Override with `OCR_DOCS_DATA_DIR`.

## Dev with magical-pdf UI

1. Start API: `.\run-api.ps1`
2. Start web: `npm run dev:web` (Extract tab — phase 5.3)

## Layout mode

Worker uses `layout` (single positioned DOCX). Landscape PDFs: request `pptx` in API (phase 5.5 auto-detect).
