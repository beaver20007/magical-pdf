/**
 * Extract tab UI — Phase 5.2/5.3
 * Handles PDF upload → jobs API → progress polling → download.
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

const apiBase = extractApiBase();

if (!apiBase) {
  noticeMissing.hidden = false;
  startBtn.disabled = true;
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

function selectFile(file) {
  if (!file || !file.name.toLowerCase().endsWith(".pdf")) {
    setError("Выберите файл в формате PDF.");
    return;
  }
  selectedFile = file;
  fileHint.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(2)} МБ)`;
  dropZone.classList.add("has-file");
  startBtn.disabled = !apiBase;
  resetJob();
  setStatus("Файл выбран. Нажмите «Распознать».");
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
    queued:     "В очереди…",
    running:    "Распознаётся…",
    done:       "Готово!",
    failed:     "Ошибка распознавания",
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
