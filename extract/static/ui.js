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

let selectedFile = null;
let pollTimer = null;

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
  if (!file || !file.name.toLowerCase().endsWith(".pdf")) return;
  selectedFile = file;
  fileHint.textContent = `${file.name} (${(file.size / 1024 / 1024).toFixed(1)} МБ)`;
  startBtn.disabled = false;
  statusText.textContent = "Готово к распознаванию";
  setError("");
  downloads.hidden = true;
}

fileInput.addEventListener("change", () => {
  if (fileInput.files?.[0]) onFile(fileInput.files[0]);
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
  const res = await fetch(`/api/v1/jobs/${jobId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function showDownloads(jobId, outputs) {
  downloads.hidden = false;
  if (outputs.includes("docx")) {
    docxLink.hidden = false;
    docxLink.href = `/api/v1/jobs/${jobId}/download.docx`;
  }
  if (outputs.includes("pptx")) {
    pptxLink.hidden = false;
    pptxLink.href = `/api/v1/jobs/${jobId}/download.pptx`;
  }
  manifestLink.hidden = false;
  manifestLink.href = `/api/v1/jobs/${jobId}/manifest.json`;
}

startBtn.addEventListener("click", async () => {
  if (!selectedFile) return;
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
    const createRes = await fetch("/api/v1/jobs", { method: "POST", body: form });
    if (!createRes.ok) {
      const err = await createRes.json().catch(() => ({}));
      throw new Error(err.detail || createRes.statusText);
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
          statusText.textContent = "Готово";
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
    statusText.textContent = "Ошибка";
    startBtn.disabled = false;
    progressBar.hidden = true;
  }
});
