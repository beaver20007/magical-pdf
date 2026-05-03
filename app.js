import * as pdfjsLib from "./vendor/pdf.min.mjs";

const fileInput = document.querySelector("#fileInput");
const dropZone = document.querySelector("#dropZone");
const dropTitle = document.querySelector("#dropTitle");
const dropHint = document.querySelector("#dropHint");
const selectedFileInfo = document.querySelector("#selectedFileInfo");
const qualityPresetSelect = document.querySelector("#qualityPresetSelect");
const convertPdfButton = document.querySelector("#convertPdfButton");
const exportJpegsButton = document.querySelector("#exportJpegsButton");
const downloadPdfButton = document.querySelector("#downloadPdfButton");
const downloadJpegsButton = document.querySelector("#downloadJpegsButton");
const statusText = document.querySelector("#statusText");
const progressBar = document.querySelector("#progressBar");
const previewGrid = document.querySelector("#previewGrid");
const { PDFLib, JSZip } = globalThis;

pdfjsLib.GlobalWorkerOptions.workerSrc =
  "./vendor/pdf.worker.min.mjs";

let selectedFile = null;
let outputPdfUrl = null;
let outputJpegsUrl = null;
let outputPdfBlob = null;
let outputJpegsBlob = null;

fileInput.addEventListener("change", () => {
  if (fileInput.files?.[0]) {
    selectFile(fileInput.files[0]);
  }
});

for (const eventName of ["dragenter", "dragover"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("drag-over");
  });
}

for (const eventName of ["dragleave", "drop"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("drag-over");
  });
}

dropZone.addEventListener("drop", (event) => {
  const file = event.dataTransfer?.files?.[0];
  if (file) {
    selectFile(file);
  }
});

convertPdfButton.addEventListener("click", async () => {
  if (!selectedFile) return;

  setBusy(true);
  resetOutput();
  previewGrid.replaceChildren();

  try {
    const pdfBytes = await selectedFile.arrayBuffer();
    const jpegPages = await renderPdfToJpegs(pdfBytes);
    const outputBytes = await buildPdfFromJpegs(jpegPages);
    outputPdfBlob = new Blob([outputBytes], { type: "application/pdf" });
    outputPdfUrl = URL.createObjectURL(outputPdfBlob);
    downloadPdfButton.disabled = false;
    setStatus(
      `Новый PDF готов: ${jpegPages.length} стр., ${formatFileSize(outputPdfBlob.size)}. Нажмите "↓ Скачать".`,
      100,
    );
  } catch (error) {
    console.error(error);
    setStatus("Не удалось преобразовать PDF. Проверьте файл и настройки.", 0);
  } finally {
    setBusy(false);
  }
});

exportJpegsButton.addEventListener("click", async () => {
  if (!selectedFile) return;

  setBusy(true);
  resetOutput();
  previewGrid.replaceChildren();

  try {
    const pdfBytes = await selectedFile.arrayBuffer();
    const jpegPages = await renderPdfToJpegs(pdfBytes);
    outputJpegsBlob = await buildJpegArchive(jpegPages);
    outputJpegsUrl = URL.createObjectURL(outputJpegsBlob);
    downloadJpegsButton.disabled = false;
    setStatus(
      `JPEG архив готов: ${jpegPages.length} стр., ${formatFileSize(outputJpegsBlob.size)}. Нажмите "↓ Скачать".`,
      100,
    );
  } catch (error) {
    console.error(error);
    setStatus("Не удалось подготовить JPEG страницы. Проверьте файл и настройки.", 0);
  } finally {
    setBusy(false);
  }
});

downloadPdfButton.addEventListener("click", async () => {
  if (!outputPdfBlob || !outputPdfUrl) return;

  const safeName = selectedFile.name.replace(/\.pdf$/i, "");
  await downloadBlob(outputPdfBlob, outputPdfUrl, `${safeName}-скан.pdf`);
});

downloadJpegsButton.addEventListener("click", async () => {
  if (!outputJpegsBlob || !outputJpegsUrl) return;

  const safeName = selectedFile.name.replace(/\.pdf$/i, "");
  await downloadBlob(outputJpegsBlob, outputJpegsUrl, `${safeName}-страницы-jpeg.zip`);
});

function selectFile(file) {
  if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
    setStatus("Выберите файл PDF.", 0);
    return;
  }

  selectedFile = file;
  resetOutput();
  previewGrid.replaceChildren();
  dropZone.classList.add("has-file");
  dropTitle.textContent = "PDF выбран";
  dropHint.textContent = "Теперь выберите действие ниже";
  selectedFileInfo.hidden = false;
  selectedFileInfo.textContent = `${file.name} (${formatFileSize(file.size)})`;
  convertPdfButton.disabled = false;
  exportJpegsButton.disabled = false;
  setStatus(`Файл выбран: ${file.name}. Теперь нажмите "Создать страницы JPEG" или "Создать новый PDF".`, 0);
}

async function renderPdfToJpegs(pdfBytes) {
  const pdf = await pdfjsLib.getDocument({ data: pdfBytes }).promise;
  const pages = [];
  const { dpi, jpegQuality } = getQualityPreset();
  const scale = dpi / 72;

  for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
    setStatus(`Рендеринг JPEG: стр. ${pageNumber} из ${pdf.numPages}`, pageNumber);

    const page = await pdf.getPage(pageNumber);
    const viewport = page.getViewport({ scale });
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d", { alpha: false });
    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);

    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    await page.render({ canvasContext: context, viewport }).promise;

    const dataUrl = canvas.toDataURL("image/jpeg", jpegQuality);
    pages.push({
      dataUrl,
      base64: dataUrl.split(",")[1],
      pixelWidth: canvas.width,
      pixelHeight: canvas.height,
      widthPt: viewport.width / scale,
      heightPt: viewport.height / scale,
      pageNumber,
    });
    addPreview(dataUrl, pageNumber, canvas.width, canvas.height);
    setStatus(
      `Рендеринг JPEG: стр. ${pageNumber} из ${pdf.numPages}`,
      (pageNumber / pdf.numPages) * 60,
    );
  }

  return pages;
}

async function buildJpegArchive(jpegPages) {
  const zip = new JSZip();
  const safeName = selectedFile.name.replace(/\.pdf$/i, "");

  for (let index = 0; index < jpegPages.length; index += 1) {
    const jpegPage = jpegPages[index];
    const pageName = String(jpegPage.pageNumber).padStart(3, "0");
    zip.file(`${safeName}-page-${pageName}.jpg`, jpegPage.base64, { base64: true });
    setStatus(
      `Упаковка JPEG: стр. ${index + 1} из ${jpegPages.length}`,
      75 + ((index + 1) / jpegPages.length) * 25,
    );
  }

  return zip.generateAsync({ type: "blob", compression: "STORE" });
}

async function buildPdfFromJpegs(jpegPages) {
  const { PDFDocument } = PDFLib;
  const outputPdf = await PDFDocument.create();

  for (let index = 0; index < jpegPages.length; index += 1) {
    const jpegPage = jpegPages[index];
    setStatus(`Сборка PDF: стр. ${index + 1} из ${jpegPages.length}`, 60);

    const jpgImage = await outputPdf.embedJpg(jpegPage.dataUrl);
    const page = outputPdf.addPage([jpegPage.widthPt, jpegPage.heightPt]);
    page.drawImage(jpgImage, {
      x: 0,
      y: 0,
      width: jpegPage.widthPt,
      height: jpegPage.heightPt,
    });
    setStatus(
      `Сборка PDF: стр. ${index + 1} из ${jpegPages.length}`,
      60 + ((index + 1) / jpegPages.length) * 40,
    );
  }

  return outputPdf.save();
}

function addPreview(dataUrl, pageNumber, pixelWidth, pixelHeight) {
  const figure = document.createElement("figure");
  figure.className = "page-card";

  const image = document.createElement("img");
  image.src = dataUrl;
  image.alt = `Страница ${pageNumber}`;

  const caption = document.createElement("figcaption");
  const title = document.createElement("strong");
  title.textContent = `Страница ${pageNumber}`;
  const meta = document.createElement("span");
  meta.textContent = `${pixelWidth} x ${pixelHeight} px`;

  caption.append(title, meta);
  figure.append(image, caption);
  previewGrid.append(figure);
}

function setBusy(isBusy) {
  convertPdfButton.disabled = isBusy || !selectedFile;
  exportJpegsButton.disabled = isBusy || !selectedFile;
  fileInput.disabled = isBusy;
  qualityPresetSelect.disabled = isBusy;
}

function resetOutput() {
  if (outputPdfUrl) {
    URL.revokeObjectURL(outputPdfUrl);
  }
  if (outputJpegsUrl) {
    URL.revokeObjectURL(outputJpegsUrl);
  }
  outputPdfUrl = null;
  outputJpegsUrl = null;
  outputPdfBlob = null;
  outputJpegsBlob = null;
  downloadPdfButton.disabled = true;
  downloadJpegsButton.disabled = true;
}

async function downloadBlob(blob, url, filename) {
  if (!blob.size) {
    setStatus("Файл не создан: размер результата 0 байт. Попробуйте создать PDF ещё раз.", 0);
    return;
  }

  if (isCapacitorApp()) {
    try {
      await shareBlobFromMobileApp(blob, filename);
      setStatus(`Файл готов: ${filename}. Выберите место сохранения в меню iOS.`, 100);
      return;
    } catch (error) {
      console.warn("Не удалось открыть меню iOS для сохранения.", error);
      setStatus("Не удалось сохранить файл через iOS. Попробуйте ещё раз.", 0);
      return;
    }
  }

  if (isTauriApp()) {
    try {
      const bytes = Array.from(new Uint8Array(await blob.arrayBuffer()));
      const savedPath = await window.__TAURI__.core.invoke("save_file", {
        filename,
        data: bytes,
      });
      setStatus(`Файл сохранён: ${savedPath}`, 100);
      return;
    } catch (error) {
      const message = String(error);
      if (message.includes("Сохранение отменено")) {
        setStatus("Сохранение отменено.", 100);
        return;
      }
      console.warn("Не удалось сохранить через macOS-приложение.", error);
      setStatus("Не удалось сохранить файл. Попробуйте выбрать другое место.", 0);
      return;
    }
  }

  if ("showSaveFilePicker" in window) {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: filename,
        types: [
          {
            description: filename.endsWith(".pdf") ? "PDF файл" : "ZIP архив",
            accept: {
              [blob.type || "application/octet-stream"]: [
                filename.endsWith(".pdf") ? ".pdf" : ".zip",
              ],
            },
          },
        ],
      });
      const writable = await handle.createWritable();
      await writable.write(new Uint8Array(await blob.arrayBuffer()));
      await writable.close();
      setStatus(`Файл сохранён: ${filename}, ${formatFileSize(blob.size)}.`, 100);
      return;
    } catch (error) {
      if (error.name === "AbortError") {
        setStatus("Сохранение отменено.", 100);
        return;
      }
      console.warn("Не удалось сохранить через системный диалог.", error);
      setStatus("Не удалось выбрать место сохранения, пробую запасной способ.", 100);
      await waitForStatusPaint();
    }
  }

  if (isLocalHttpApp()) {
    try {
      const response = await fetch(`/save?filename=${encodeURIComponent(filename)}`, {
        method: "POST",
        headers: {
          "Content-Type": blob.type || "application/octet-stream",
        },
        body: blob,
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const result = await response.json();
      setStatus(
        `Файл сохранён в Загрузки: ${filename}, ${formatFileSize(result.size)}.`,
        100,
      );
      return;
    } catch (error) {
      console.warn("Локальное сохранение через сервер недоступно.", error);
    }
  }

  const href = url;
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  link.rel = "noopener";
  link.style.display = "none";
  document.body.append(link);
  link.click();
  link.remove();
  setStatus(`Скачивание запрошено: ${filename}, ${formatFileSize(blob.size)}.`, 100);
}

async function shareBlobFromMobileApp(blob, filename) {
  const plugins = window.Capacitor?.Plugins;
  const filesystem = plugins?.Filesystem;
  const share = plugins?.Share;

  if (!filesystem || !share) {
    throw new Error("Capacitor Filesystem или Share недоступен");
  }

  const base64Data = await blobToBase64(blob);
  const writeResult = await filesystem.writeFile({
    path: filename,
    data: base64Data,
    directory: "DOCUMENTS",
    recursive: true,
  });

  const fileUri = writeResult.uri || writeResult.path;
  await share.share({
    title: "Magical PDF",
    text: "Готовый файл Magical PDF",
    url: fileUri,
    dialogTitle: "Сохранить или отправить файл",
  });
}

function blobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      resolve(result.includes(",") ? result.split(",")[1] : result);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

function isLocalHttpApp() {
  return (
    window.location.protocol === "http:" &&
    ["127.0.0.1", "localhost"].includes(window.location.hostname)
  );
}

function isTauriApp() {
  return Boolean(window.__TAURI__?.core?.invoke);
}

function isCapacitorApp() {
  return window.Capacitor?.isNativePlatform?.() === true;
}

function waitForStatusPaint() {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

function setStatus(message, progress) {
  statusText.textContent = message;
  progressBar.value = clamp(progress, 0, 100);
}

function clamp(value, min, max) {
  if (Number.isNaN(value)) return min;
  return Math.min(Math.max(value, min), max);
}

function getQualityPreset() {
  const presets = {
    low: { dpi: 150, jpegQuality: 0.82 },
    medium: { dpi: 300, jpegQuality: 0.9 },
    high: { dpi: 600, jpegQuality: 0.96 },
  };

  return presets[qualityPresetSelect.value] ?? presets.medium;
}

function formatFileSize(bytes) {
  if (bytes < 1024) {
    return `${bytes} байт`;
  }

  const units = ["КБ", "МБ", "ГБ"];
  let size = bytes / 1024;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }

  return `${size.toFixed(size >= 10 ? 1 : 2)} ${units[unitIndex]}`;
}
