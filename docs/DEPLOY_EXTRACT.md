# Deploy Extract API for public beta (GitHub Pages)

GitHub Pages serves **static files only**. Full **Распознать** (OCR → DOCX/PPTX) needs a hosted Extract API. Protect works entirely in the browser.

## Architecture

```text
User browser
  ├─ https://beaver20007.github.io/magical-pdf/          → Protect (client-side)
  └─ https://beaver20007.github.io/magical-pdf/extract/  → UI → POST/POLL cloud API
                                                              https://<your-api>/api/v1/jobs
```

---

## 1. Deploy API on Railway (recommended)

Uses existing [`extract/Dockerfile`](../extract/Dockerfile) and [`extract/railway.toml`](../extract/railway.toml).

### New project from GitHub

1. [Railway Dashboard](https://railway.app/dashboard) → **New Project** → **Deploy from GitHub repo** → `beaver20007/magical-pdf`.
2. Open the service → **Settings**:
   - **Root Directory**: `extract`
   - **Builder**: Dockerfile (auto from `railway.toml`)
3. **Settings → Networking** → **Generate Domain** (public URL).
4. **Settings → Resources**: **≥ 4 GB RAM** recommended (Docling + EasyOCR + PyTorch on CPU). Less than 2 GB often OOMs.
5. **Volumes** (recommended): add volume, mount path `/data` — jobs + Hugging Face model cache persist across redeploys.
6. **Variables** — paste (adjust if needed):

```env
PYTHONUNBUFFERED=1
OCR_DOCS_DATA_DIR=/data
HF_HOME=/data/huggingface
EXTRACT_PUBLIC_BETA=1
OCR_DOCS_MAX_PAGES=15
OCR_DOCS_MAX_BYTES=20971520
OCR_DOCS_JOB_TTL_HOURS=24
EXTRACT_CORS_ORIGINS=https://beaver20007.github.io,http://127.0.0.1:5173,http://localhost:5173
```

7. Deploy. First build: **15–25 min** (pip + torch). First OCR job downloads models (~1–3 GB) — allow **5–15 min** extra.
8. Check: `https://<your-app>.up.railway.app/health` → `{"status":"ok","public_beta":true,...}`.

### Existing Railway project

Add a service → **GitHub Repo** → same repo, **Root Directory** = `extract`, variables as above.

### Beta limits (defaults with `EXTRACT_PUBLIC_BETA=1`)

| Limit | Value |
|-------|--------|
| Max PDF size | 20 MB |
| Max pages | 15 |
| Job retention | 24 h |

Override via Railway variables.

---

## 1b. Deploy on Render (alternative)

[Render Blueprint](../render.yaml) — plan **Standard** (2 GB) minimum. See `render.yaml` for env defaults.

---

## 2. Wire GitHub Pages to the API

1. GitHub repo **Settings → Secrets and variables → Actions → Variables**.
2. Add: `EXTRACT_API_URL` = `https://<your-app>.up.railway.app` (no trailing slash).
3. Re-run workflow **Deploy web** (or push to `main`).

The build injects the URL into `api-config.js`. Extract tab becomes fully functional for external testers.

## 3. Verify end-to-end

1. Open [magical-pdf/extract/](https://beaver20007.github.io/magical-pdf/extract/).
2. Yellow **Бета-тест** banner (not «сервер не подключён»).
3. Upload a small scanned PDF (1–2 pages) → wait → download DOCX.

## Local development (unchanged)

```powershell
cd extract
.\run-api.ps1          # :8765
cd ..
npm run dev:web        # :5173 → ./extract/
```

Browser override: `?api=http://127.0.0.1:8765`.

## Privacy

Public beta sends PDFs to the cloud server. Do not use for confidential contracts. Jobs deleted after 24 h; never log document text.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| «Сервер Extract не подключён» on Pages | Set `EXTRACT_API_URL`, redeploy Pages workflow |
| CORS error | Add origin to `EXTRACT_CORS_ORIGINS` on Railway |
| Build fails / OOM | Raise RAM to 4–8 GB on Railway |
| First job very slow | Model download; check volume on `/data` |
| `failed` layout error | Try PPTX for landscape; open `manifest.json` |
| 502 on long job | Normal for big PDFs — client polls until `done` |

## Docker (local / manual)

```bash
cd extract
docker build -t magical-pdf-extract .
docker run -p 8765:8765 -e EXTRACT_PUBLIC_BETA=1 -v extract-data:/data magical-pdf-extract
```
