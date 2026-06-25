/**
 * Extract tab UI — Phase 5.2/5.3/5.4
 * Handles PDF upload → jobs API → progress polling → download.
 * In Tauri context: invokes ensure_extract_server + polls /health until ready.
 */
import { extractApiBase, isPublicExtractBeta, initModeTabs } from "../../nav.js";

initModeTabs({ active: "extract" });

const fileInput      = document.querySelector("#fileInput");
const dropZone       = document.querySelector("#dropZone");
const fileHint       = document.querySelector("#fileHint");
const outputSelect   = document.querySelector("#outputSelect");
const languagesInput = document.querySelector("#languagesInput");
const startBtn       = document.querySelector("#startBtn");
const statusText     = document.querySelector("#statusText");
const progressBar    = document.querySelector("#progressBar");
const messageText    = document.querySelector("#messageText");
const downloadsEl    = document.querySelector("#downloads");
const docxLink       = document.querySelector("#docxLink");
const pptxLink       = document.querySelector("#pptxLink");
const manifestLink   = document.querySelector("#manifestLink");
const errorBox       = document.querySelector("#errorBox");
const noticeMissing  = document.querySelector("#pagesNoticeMissing");
const noticeBeta     = document.querySelector("#pagesNoticeBeta");
const fileInfoChip   = document.querySelector("#fileInfoChip");
const fileInfoName   = document.querySelector("#fileInfoName");
const fileInfoMeta   = document.querySelector("#fileInfoMeta");

const apiBase = extractApiBase();
const isTauri = typeof window.__TAURI__ !== "undefined";

// ── Deep link: ?source=docraft&back=<url> ─────────────────────────────────────
(function initSourceBack() {
  const params = new URLSearchParams(location.search);
  const source = params.get("source");
  if (!source) return;
  const backEl = document.querySelector("#sourceBack");
  if (!backEl) return;
  const LABELS = { docraft: "Docraft", "magical-pdf": "Magical PDF" };
  const label = LABELS[source] ?? source;
  const backUrl = params.get("back") ?? (source === "docraft" ? "https://docraft.pro" : "../");
  backEl.textContent = label;
  backEl.href = backUrl;
  backEl.hidden = false;
})();

// ── Tauri: auto-start + health check ─────────────────────────────────────────
async function waitForHealth(maxMs = 30_000, intervalMs = 600) {
  const deadline = Date.now() + maxMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${apiBase}/health`);
      if (res.ok) return true;
    } catch { /* server not up yet */ }
    await new Promise(r => setTimeout(r, intervalMs));
  }
  return false;
}

async function initTauri() {
  setStatus("Запуск сервера распознавания…", 0);
  startBtn.disabled = true;
  try {
    await window.__TAURI__.core.invoke("ensure_extract_server");
  } catch (e) {
    setError(`Не удалось запустить сервер: ${e}`);
    return;
  }
  const ready = await waitForHealth();
  if (ready) {
    setStatus("Сервер готов. Выберите PDF для распознавания.");
  } else {
    setError("Сервер не ответил за 30 секунд. Проверьте Python и зависимости в extract/.venv");
  }
}

// ── init ──────────────────────────────────────────────────────────────────────
if (!apiBase) {
  noticeMissing.hidden = false;
  startBtn.disabled = true;
} else if (isTauri) {
  initTauri();
} else if (isPublicExtractBeta()) {
  noticeBeta.hidden = false;
}

let selectedFile = null;
let pollTimer = null;

function setError(msg) {
  errorBox.textContent = msg;
  errorBox.hidden = !msg;
}

function setStatus(text, progress) {
  statusText.textContent = text;
  if (progress != null) {
    progressBar.hidden = false;
    progressBar.value = Math.round(progress * 100);
  } else {
    progressBar.hidden = true;
  }
}

function resetJob() {
  clearInterval(pollTimer);
  pollTimer = null;
  downloadsEl.hidden = true;
  docxLink.hidden = true;
  pptxLink.hidden = true;
  manifestLink.hidden = true;
  progressBar.hidden = true;
  messageText.textContent = "";
  setError("");
}

function fmtSize(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(2)} МБ`;
}

function selectFile(file) {
  if (!file || !file.name.toLowerCase().endsWith(".pdf")) {
    setError("Выберите файл в формате PDF.");
    return;
  }
  selectedFile = file;
  fileHint.textContent = `${file.name} (${fmtSize(file.size)})`;
  dropZone.classList.add("has-file");
  startBtn.disabled = !apiBase;
  resetJob();
  setStatus("Файл выбран. Нажмите «Распознать».");

  // Show file info chip with page count (async, non-blocking).
  if (fileInfoChip) {
    fileInfoName.textContent = file.name;
    fileInfoMeta.textContent = fmtSize(file.size) + " · считаю страницы…";
    fileInfoChip.hidden = false;
    (async () => {
      try {
        const { PDFDocument } = window.PDFLib;
        if (!PDFDocument) return;
        const buf = await file.arrayBuffer();
        const doc = await PDFDocument.load(buf, { ignoreEncryption: true });
        fileInfoMeta.textContent = `${fmtSize(file.size)} · ${doc.getPageCount()} стр.`;
      } catch { fileInfoMeta.textContent = fmtSize(file.size); }
    })();
  }
}

fileInput.addEventListener("change", () => {
  if (fileInput.files?.length) selectFile(fileInput.files[0]);
});

dropZone.addEventListener("click", () => {
  fileInput.value = "";
  fileInput.click();
});

dropZone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
});

for (const ev of ["dragenter", "dragover"]) {
  dropZone.addEventListener(ev, (e) => { e.preventDefault(); dropZone.classList.add("drag-over"); });
}

for (const ev of ["dragleave", "drop"]) {
  dropZone.addEventListener(ev, (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
  });
}

dropZone.addEventListener("drop", (e) => {
  const files = Array.from(e.dataTransfer?.files || []);
  if (files.length) selectFile(files[0]);
});

async function pollJob(jobId) {
  const url = `${apiBase}/api/v1/jobs/${jobId}`;
  let meta;
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    meta = await res.json();
  } catch (err) {
    setStatus("Ошибка опроса сервера.");
    setError(`Не удалось получить статус задачи: ${err.message}`);
    clearInterval(pollTimer);
    startBtn.disabled = false;
    return;
  }

  const STATUS_LABELS = {
    queued:  "В очереди… ожидание сервера",
    running: meta.progress != null
      ? `Распознаётся… стр. ${Math.round((meta.progress ?? 0) * (meta.total_pages ?? 1))} / ${meta.total_pages ?? "?"}`
      : "Распознаётся…",
    done:    "Готово!",
    failed:  "Ошибка распознавания",
  };

  setStatus(STATUS_LABELS[meta.status] ?? meta.status, meta.progress ?? null);

  if (meta.warnings?.length) {
    messageText.textContent = meta.warnings.slice(0, 2).join(" · ");
  }

  if (meta.status === "done") {
    clearInterval(pollTimer);
    startBtn.disabled = false;
    showDownloads(jobId, meta.outputs ?? []);
  } else if (meta.status === "failed") {
    clearInterval(pollTimer);
    startBtn.disabled = false;
    setError(meta.error ?? "Произошла ошибка. Попробуйте другой файл.");
  }
}

function showDownloads(jobId, outputs) {
  downloadsEl.hidden = false;

  if (outputs.includes("docx")) {
    docxLink.href = `${apiBase}/api/v1/jobs/${jobId}/download.docx`;
    docxLink.hidden = false;
  }
  if (outputs.includes("pptx")) {
    pptxLink.href = `${apiBase}/api/v1/jobs/${jobId}/download.pptx`;
    pptxLink.hidden = false;
  }
  manifestLink.href = `${apiBase}/api/v1/jobs/${jobId}/manifest.json`;
  manifestLink.hidden = false;
}

startBtn.addEventListener("click", async () => {
  if (!selectedFile || !apiBase) return;

  resetJob();
  startBtn.disabled = true;
  setStatus("Отправка файла…", 0);

  const form = new FormData();
  form.append("file", selectedFile);
  form.append("output", outputSelect.value);
  form.append("languages", languagesInput.value.trim() || "ru,en");

  let job;
  try {
    const res = await fetch(`${apiBase}/api/v1/jobs`, { method: "POST", body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
    job = await res.json();
  } catch (err) {
    setStatus("Не удалось отправить файл.");
    setError(`Ошибка: ${err.message}`);
    startBtn.disabled = false;
    return;
  }

  setStatus("Задача принята, ждём очереди…", 0.02);
  pollTimer = setInterval(() => pollJob(job.id), 2000);
  pollJob(job.id);
});
