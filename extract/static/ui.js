import {
  extractApiBase,
  initModeTabs,
  isGitHubPages,
  isPublicExtractBeta,
} from "./nav.js";

// When running inside Tauri desktop app, start the extract server automatically.
if (window.__TAURI__?.core?.invoke) {
  window.__TAURI__.core.invoke("ensure_extract_server").catch((e) => {
    console.warn("ensure_extract_server:", e);
  });
}

const fileInput = document.getElementById("fileInput");
const dropZone = document.getElementById("dropZone");
const fileHint = document.getElementById("fileHint");
const startBtn = document.getElementById("startBtn");
const outputSelect = document.getElementById("outputSelect");
const languagesInput = document.getElementById("languagesInput");
const statusText = document.getElementById("statusText");
const messageText = document.getElementById("messageText");
const progressBar = document.getElementById("progressBar");
const downloads = document.getElementById("downloads");
const docxLink = document.getElementById("docxLink");
const pptxLink = document.getElementById("pptxLink");
const manifestLink = document.getElementById("manifestLink");
const errorBox = document.getElementById("errorBox");
const pagesNoticeMissing = document.getElementById("pagesNoticeMissing");
const pagesNoticeBeta = document.getElementById("pagesNoticeBeta");

const apiBase = extractApiBase();
let selectedFile = null;
let pollTimer = null;

initModeTabs({ active: "extract" });

function apiUrl(path) {
  if (!apiBase) {
    throw new Error("Extract API не настроен");
  }
  return `${apiBase}${path}`;
}

function setError(text) {
  if (!text) {
    errorBox.hidden = true;
    errorBox.textContent = "";
    return;
  }
  errorBox.hidden = false;
  errorBox.textContent = text;
}

function onFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    setError("Нужен файл PDF");
    return;
  }
  selectedFile = file;
  fileHint.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} МБ)`;
  dropZone.classList.add("has-file");
  startBtn.disabled = !apiBase;
  statusText.textContent = apiBase ? "Готово к распознаванию" : "API не подключён";
  setError("");
  downloads.hidden = true;
}

fileInput.addEventListener("change", () => {
  if (fileInput.files?.[0]) onFile(fileInput.files[0]);
});

dropZone.addEventListener("click", (event) => {
  if (event.target === fileInput) return;
  fileInput.click();
});

dropZone.addEventListener("keydown", (event) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    fileInput.click();
  }
});

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("drag");
});

dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag"));

dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("drag");
  if (e.dataTransfer.files?.[0]) onFile(e.dataTransfer.files[0]);
});

async function pollJob(jobId) {
  const res = await fetch(apiUrl(`/api/v1/jobs/${jobId}`));
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function wireDownloadLink(link, url, filename) {
  link.hidden = false;
  link.href = url;
  link.onclick = async (event) => {
    event.preventDefault();
    try {
      setError("");
      statusText.textContent = `Скачивание ${filename}…`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(objectUrl);
      statusText.textContent = "Готово";
    } catch (err) {
      setError(`Не удалось скачать: ${err.message}`);
    }
  };
}

function showDownloads(jobId, outputs) {
  downloads.hidden = false;
  if (outputs.includes("docx")) {
    wireDownloadLink(docxLink, apiUrl(`/api/v1/jobs/${jobId}/download.docx`), "output.docx");
  }
  if (outputs.includes("pptx")) {
    wireDownloadLink(pptxLink, apiUrl(`/api/v1/jobs/${jobId}/download.pptx`), "output.pptx");
  }
  manifestLink.hidden = false;
  manifestLink.href = apiUrl(`/api/v1/jobs/${jobId}/manifest.json`);
  manifestLink.onclick = null;
}

startBtn.addEventListener("click", async () => {
  if (!selectedFile || !apiBase) return;
  startBtn.disabled = true;
  setError("");
  downloads.hidden = true;
  docxLink.hidden = pptxLink.hidden = manifestLink.hidden = true;
  progressBar.hidden = false;
  progressBar.value = 0;
  statusText.textContent = "Загрузка…";
  messageText.textContent = "";

  const form = new FormData();
  form.append("file", selectedFile);
  form.append("output", outputSelect.value);
  form.append("languages", languagesInput.value.trim() || "ru,en");

  try {
    const createRes = await fetch(apiUrl("/api/v1/jobs"), { method: "POST", body: form });
    if (!createRes.ok) {
      const err = await createRes.json().catch(() => ({}));
      const detail = err.detail;
      throw new Error(
        typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join(", ") : createRes.statusText,
      );
    }
    const { id } = await createRes.json();
    statusText.textContent = "Распознавание…";

    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      try {
        const meta = await pollJob(id);
        const pct = Math.round((meta.progress || 0) * 100);
        progressBar.value = pct;
        messageText.textContent = meta.message || "";
        statusText.textContent =
          meta.status === "running"
            ? `Обработка… ${pct}%`
            : meta.status === "queued"
              ? "В очереди…"
              : meta.status;

        if (meta.status === "done") {
          clearInterval(pollTimer);
          pollTimer = null;
          statusText.textContent = "Готово — скачайте файл";
          progressBar.value = 100;
          showDownloads(id, meta.outputs || ["docx"]);
          startBtn.disabled = false;
        } else if (meta.status === "failed") {
          clearInterval(pollTimer);
          pollTimer = null;
          setError(meta.error || "Ошибка конвертации");
          statusText.textContent = "Ошибка";
          startBtn.disabled = false;
        }
      } catch (err) {
        clearInterval(pollTimer);
        pollTimer = null;
        setError(String(err));
        startBtn.disabled = false;
      }
    }, 2000);
  } catch (err) {
    setError(String(err));
    statusText.textContent = "Ошибка загрузки";
    startBtn.disabled = false;
    progressBar.hidden = true;
  }
});

async function initApiStatus() {
  if (isGitHubPages() && !apiBase) {
    if (pagesNoticeMissing) pagesNoticeMissing.hidden = false;
    startBtn.disabled = true;
    statusText.textContent = "Сервер Extract не подключён";
    return;
  }

  if (apiBase && (isPublicExtractBeta() || isGitHubPages()) && pagesNoticeBeta) {
    pagesNoticeBeta.hidden = false;
  }

  if (!apiBase) {
    return;
  }

  try {
    const res = await fetch(`${apiBase}/health`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    statusText.textContent = "Выберите PDF";
  } catch (err) {
    setError(`API недоступен (${apiBase}): ${err.message}`);
    statusText.textContent = "Нет связи с сервером";
    startBtn.disabled = true;
  }
}

initApiStatus();
