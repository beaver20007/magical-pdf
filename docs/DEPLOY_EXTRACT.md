# Deploy Extract API for public beta (GitHub Pages)

GitHub Pages serves **static files only**. Full **Распознать** (OCR → DOCX/PPTX) needs a hosted Extract API. Protect works entirely in the browser.

## Architecture

```text
User browser
  ├─ https://beaver20007.github.io/magical-pdf/          → Protect (client-side)
  └─ https://beaver20007.github.io/magical-pdf/extract/  → UI → POST/POLL cloud API
                                                              https://<your-api>/api/v1/jobs
```

## 1. Deploy API on Render (recommended)

1. Open [Render Blueprint deploy](https://dashboard.render.com/select-repo?type=blueprint) and connect repo `beaver20007/magical-pdf`.
2. Render reads [`render.yaml`](../render.yaml) — service `magical-pdf-extract`, plan **Standard** (2 GB RAM minimum; Docling + EasyOCR need memory).
3. Wait for first build (10–20 min). First OCR job may download models (~1–3 GB) — allow 5–15 min extra.
4. Copy the service URL, e.g. `https://magical-pdf-extract.onrender.com`.
5. Check: `curl https://magical-pdf-extract.onrender.com/health` → `{"status":"ok",...}`.

### Beta limits (default on Render)

| Limit | Value |
|-------|--------|
| Max PDF size | 20 MB |
| Max pages | 15 |
| Job retention | 24 h |

Override via env vars in `render.yaml` or Render dashboard.

## 2. Wire GitHub Pages to the API

1. GitHub repo **Settings → Secrets and variables → Actions → Variables**.
2. Add repository variable: `EXTRACT_API_URL` = `https://magical-pdf-extract.onrender.com` (no trailing slash).
3. Re-run workflow **Deploy web** (or push to `main`).

The build injects the URL into `api-config.js` on Pages. Extract tab becomes fully functional for external testers.

## 3. Verify end-to-end

1. Open [magical-pdf/extract/](https://beaver20007.github.io/magical-pdf/extract/).
2. Yellow **Бета-тест** banner should appear (not “сервер не подключён”).
3. Upload a small scanned PDF (1–2 pages), wait for DOCX download.

## Local development (unchanged)

```powershell
cd extract
.\run-api.ps1          # :8765
cd ..
npm run dev:web        # :5173 → ./extract/
```

Override API in browser: `?api=http://127.0.0.1:8765`.

## Privacy

Public beta sends PDFs to the cloud server. Do not use for confidential contracts. Jobs are deleted after 24 hours; logs must not contain document text (see AGENTS rules in ocr-docs).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| “Сервер Extract не подключён” on Pages | Set `EXTRACT_API_URL` variable, redeploy Pages |
| CORS error in browser console | Add your origin to `EXTRACT_CORS_ORIGINS` on API |
| 502 / timeout on first job | Render cold start; retry after `/health` is OK |
| OOM / worker killed | Upgrade Render plan or lower `OCR_DOCS_MAX_PAGES` |
| `failed` job with layout error | Try PPTX for landscape slides; check `manifest.json` link |

## Docker (manual)

```bash
cd extract
docker build -t magical-pdf-extract .
docker run -p 8765:8765 -e EXTRACT_PUBLIC_BETA=1 -v extract-data:/data magical-pdf-extract
```
