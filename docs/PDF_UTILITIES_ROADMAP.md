# PDF utilities roadmap (Stirling-class)

**Status:** planning (2026-06). Protect (flatten to scan) ships today; utilities and Extract are planned lanes in the same app.

## Role in DOCRAFT

Magical PDF evolves from **Protect-only** into a **local PDF workstation**:

```text
magical-pdf
├── Protect     — PDF → scan-like PDF (shipped)
├── Utilities   — merge, split, compress, … (this doc)
└── Extract     — scan → DOCX/PPTX (merge from ocr-docs, phase 7)
```

Docraft **Create** links here — it does not embed [Stirling-PDF](https://github.com/Stirling-Tools/Stirling-PDF) or duplicate PDF UIs.

## Why utilities live in magical-pdf (not Docraft SaaS)

| Reason | Detail |
|--------|--------|
| Local-first | Same privacy model as Protect; PII stays on device |
| User mental model | «Открыл PDF → сделал операцию» |
| Stack | JS/Tauri UI already handles PDF bytes client-side |
| Stirling fit | Stirling is a **toolbox**, not Extract; aligns with Protect adjacency |

## Stirling-PDF: what to adopt vs avoid

**Adopt (native or thin adapter):**

| Feature | Priority | Implementation note |
|---------|----------|---------------------|
| Merge / split / rotate | P1 | pdf-lib or WASM; match Stirling UX |
| Compress | P1 | Ghostscript/qpdf sidecar optional on desktop |
| Page preview | Done | Existing «Предпросмотр страниц» |
| OCR → searchable PDF | P2 | Optional; Tesseract/OCRmyPDF sidecar for **preview only** |
| Batch / pipelines | P3 | After single-tool stability |

**Avoid as primary path:**

| Feature | Why |
|---------|-----|
| PDF → DOCX (LibreOffice) | Poor on scans; use **Extract** (ocr-docs pipeline) |
| Full Stirling Docker in product | Java stack, open-core license, heavy deploy |
| Cloud upload | Conflicts with Protect promise |

Optional: developers run Stirling locally (`docker run …8080`) as **dev reference** for API shapes — not shipped to end users by default.

## DOCRAFT UI hooks (future)

| CTA in Docraft | magical-pdf entry |
|----------------|-------------------|
| Защитить PDF | `?source=docraft&mode=protect` |
| PDF: инструменты | `?source=docraft&mode=tools` |
| Распознать в Word | `?source=docraft&mode=extract` |

See also `docs/DOCRAFT_API_HOOK.md` (extend with `mode` query when implementing).

## Extract merge (ocr-docs)

Pipeline and DocumentIR develop in [ocr-docs](https://github.com/beaver20007/docraft) sandbox (`C:\Projects\ocr-docs`) until quality gates pass, then merge as **Extract tab** in this repo.

Spec: ocr-docs `docs/ECOSYSTEM_ROADMAP.md`, `docs/DOCRAFT_INTEGRATION.md`.

**Do not** implement Extract via Stirling `pdf-to-word`.

## Phases

| Phase | Deliverable |
|-------|-------------|
| 5a | Utilities spec + 1–2 tools (merge, compress) in web/Tauri |
| 5b | Docraft deep link `mode=tools` |
| 6 | Extract prototype UI (ocr-docs API or embedded worker) |
| 7 | Merge ocr-docs pipeline; deprecate standalone Extract repo |

Tracked in [docraft/docs/INTEGRATION_PHASES.md](https://github.com/beaver20007/docraft/blob/main/docs/INTEGRATION_PHASES.md).

## Links

- ocr-docs ecosystem plan: sibling repo `docs/ECOSYSTEM_ROADMAP.md`
- Stirling docs: https://docs.stirlingpdf.com
- DOCRAFT REPOS: https://github.com/beaver20007/docraft/blob/main/docs/REPOS.md
