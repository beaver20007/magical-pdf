# Extract integration plan (ocr-docs → magical-pdf)

**Decision (2026-06):** Do **not** finish a standalone ocr-docs product. Port pipeline into magical-pdf now and build **Extract UI** in the existing web/Tauri shell.

## Why now

| Old plan | New plan |
|----------|----------|
| ocr-docs sandbox → UI → merge phase 7 | One repo, one UI, one installer |
| Two UIs to maintain | Protect + Extract tabs in magical-pdf |
| Terminal / separate `:8765` for authors | Sidecar API started by Tauri (or dev server) |

ocr-docs (`C:\Projects\ocr-docs`) becomes a **source tree** until port completes; then archive or submodule.

## Target layout (magical-pdf repo)

```text
magical-pdf/
├── index.html              # shell + tab bar
├── src/
│   ├── protect.js          # today’s app.js logic
│   ├── extract.js          # upload, progress, download
│   ├── router.js           # ?mode=protect|extract
│   └── platform.js         # Tauri / Capacitor / web save
├── extract/                # Python (from ocr-docs)
│   ├── pipeline/           # DocumentIR, Docling, emitters
│   ├── api/                # FastAPI jobs
│   ├── worker.py
│   └── requirements.txt
├── src-tauri/
│   └── src/main.rs         # spawn extract API, health check
└── scripts/
    └── prepare-dist.mjs    # copy web + optional sidecar hints
```

## Runtime

```text
User → magical-pdf UI (Extract tab)
         │
         ├─ Web dev:  fetch http://127.0.0.1:8765/api/v1/jobs
         │
         └─ Tauri:    invoke("ensure_extract_server") → local FastAPI
                      → same jobs API, files on disk only
```

**Privacy:** unchanged — PDF and DOCX never leave the machine.

## Port checklist (from ocr-docs)

Copy verbatim first, refactor later:

- [x] `src/pipeline/` → `extract/src/pipeline/` (Phase 5.1)
- [x] `src/api/`, `src/worker.py`, `src/config.py` (Phase 5.1)
- [ ] `docs/IR_SCHEMA.md` mirror → `extract/docs/` or link to docraft
- [ ] Worker: `layout_mode="layout"` default; auto PPTX if landscape
- [ ] Drop `both` mode from user-facing UI (internal debug only)

## UI (Extract tab) — MVP

1. Drag-drop PDF (same affordance as Protect).
2. Output: DOCX and/or PPTX (radio); languages ru,en.
3. Progress bar from `GET /api/v1/jobs/{id}`.
4. Download buttons when `status: done`.
5. Show validation errors from `layout.validation.txt` summary (no PII).

## Phases (docraft meta)

Tracked as **Phase 5** in [docraft/docs/INTEGRATION_PHASES.md](https://github.com/beaver20007/docraft/blob/main/docs/INTEGRATION_PHASES.md).

| Sub | Deliverable |
|-----|-------------|
| 5.1 | `extract/` folder + `pip install -r extract/requirements.txt` works |
| 5.2 | Tab UI + `?mode=extract` — **GitHub Pages** tabs + `/extract/` (Protect on Pages; Extract UI preview) |
| 5.3 | Jobs API wired from UI — local `:8765` and `npm run dev:web` → `./extract/` |
| 5.4 | Tauri `ensure_extract_server` (Windows first) |
| 5.5 | Quality on Plan.pptx + Lukoil via UI |
| 5.6 | Docraft deep link «Распознать» |
| 5.7 | ocr-docs repo frozen; REPOS.md single PDF hub |

**Deferred:** PDF utilities (merge/compress) → Phase 6.

## What not to do

- New ocr-docs web UI as separate app
- Stirling PDF→Word for scans
- Cloud Extract in Docraft Create (local only)

## Links

- ocr-docs pipeline: `C:\Projects\ocr-docs\src\pipeline\`
- API spec: ocr-docs `docs/API.md`
- Protect spec: `docs/DOCRAFT_API_HOOK.md`
