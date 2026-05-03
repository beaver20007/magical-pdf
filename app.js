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
let selectedFiles = [];
let outputPdfUrl = null;
let outputJpegsUrl = null;
let outputPdfBlob = null;
let outputJpegsBlob = null;

fileInput.addEventListener("change", () => {
  if (fileInput.files?.length) {
    selectFiles(Array.from(fileInput.files));
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
  const files = Array.from(event.dataTransfer?.files || []);
  if (files.length) {
    selectFiles(files);
  }
});

convertPdfButton.addEventListener("click", async () => {
  if (selectedFiles.length !== 1) return;

  setBusy(true);
  resetOutput();
  previewGrid.replaceChildren();

  try {
    const pdfBytes = await selectedFiles[0].arrayBuffer();
    const jpegPages = await renderPdfToJpegs(pdfBytes, selectedFiles[0]);
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
  if (!selectedFiles.length) return;

  setBusy(true);
  resetOutput();
  previewGrid.replaceChildren();

  try {
    const jpegPages = await renderFilesToJpegs(selectedFiles);
    outputJpegsBlob = await buildJpegArchive(jpegPages);
    outputJpegsUrl = URL.createObjectURL(outputJpegsBlob);
    downloadJpegsButton.disabled = false;
    setStatus(
      `JPEG архив готов: ${selectedFiles.length} PDF, ${jpegPages.length} стр., ${formatFileSize(outputJpegsBlob.size)}. Нажмите "↓ Скачать".`,
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

  const safeName = selectedFiles[0].name.replace(/\.pdf$/i, "");
  await downloadBlob(outputPdfBlob, outputPdfUrl, `${safeName}-скан.pdf`);
});

downloadJpegsButton.addEventListener("click", async () => {
  if (!outputJpegsBlob || !outputJpegsUrl) return;

  const safeName = selectedFiles.length === 1
    ? selectedFiles[0].name.replace(/\.pdf$/i, "")
    : "magical-pdf";
  await downloadBlob(outputJpegsBlob, outputJpegsUrl, `${safeName}-страницы-jpeg.zip`);
});

function selectFiles(files) {
  const pdfFiles = files.filter(isPdfFile);

  if (!pdfFiles.length) {
    setStatus("Выберите один или несколько файлов PDF.", 0);
    return;
  }

  selectedFiles = pdfFiles;
  selectedFile = pdfFiles[0];
  resetOutput();
  previewGrid.replaceChildren();
  dropZone.classList.add("has-file");
  dropTitle.textContent = pdfFiles.length === 1 ? "PDF выбран" : `Выбрано PDF: ${pdfFiles.length}`;
  dropHint.textContent = pdfFiles.length === 1
    ? "Теперь выберите действие ниже"
    : "Можно создать JPEG-страницы для всех выбранных файлов";
  selectedFileInfo.hidden = false;
  selectedFileInfo.textContent = getSelectedFilesLabel(pdfFiles);
  convertPdfButton.disabled = pdfFiles.length !== 1;
  exportJpegsButton.disabled = false;

  if (pdfFiles.length === 1) {
    setStatus(`Файл выбран: ${pdfFiles[0].name}. Теперь нажмите "Создать страницы JPEG" или "Создать новый PDF".`, 0);
  } else {
    setStatus(`Выбрано PDF: ${pdfFiles.length}. Для нескольких файлов доступно пакетное создание JPEG-страниц.`, 0);
  }
}

function isPdfFile(file) {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

function getSelectedFilesLabel(files) {
  if (files.length === 1) {
    return `${files[0].name} (${formatFileSize(files[0].size)})`;
  }

  const totalSize = files.reduce((sum, file) => sum + file.size, 0);
  const previewNames = files.slice(0, 3).map((file) => file.name).join(", ");
  const extraCount = files.length > 3 ? ` и ещё ${files.length - 3}` : "";
  return `${files.length} PDF (${formatFileSize(totalSize)}): ${previewNames}${extraCount}`;
}

function getSafeBaseName(filename) {
  return filename
    .replace(/\.pdf$/i, "")
    .trim()
    .replace(/[\\/:*?"<>|]+/g, "-")
    .replace(/\s+/g, " ")
    || "document";
}

function getRenderStatus(file, batch, pageNumber, pageCount) {
  if (batch.fileCount === 1) {
    return `Рендеринг JPEG: стр. ${pageNumber} из ${pageCount}`;
  }

  return `PDF ${batch.fileIndex + 1} из ${batch.fileCount}: ${file.name}, стр. ${pageNumber} из ${pageCount}`;
}

async function renderFilesToJpegs(files) {
  const allPages = [];

  for (let fileIndex = 0; fileIndex < files.length; fileIndex += 1) {
    const file = files[fileIndex];
    setStatus(`Открытие PDF ${fileIndex + 1} из ${files.length}: ${file.name}`, 0);
    const pdfBytes = await file.arrayBuffer();
    const pages = await renderPdfToJpegs(pdfBytes, file, {
      fileIndex,
      fileCount: files.length,
    });
    allPages.push(...pages);
  }

  return allPages;
}

async function renderPdfToJpegs(pdfBytes, file, batch = { fileIndex: 0, fileCount: 1 }) {
  const pdf = await pdfjsLib.getDocument({ data: pdfBytes }).promise;
  const pages = [];
  const { dpi, jpegQuality } = getQualityPreset();
  const scale = dpi / 72;
  const safeFileName = getSafeBaseName(file.name);

  for (let pageNumber = 1; pageNumber <= pdf.numPages; pageNumber += 1) {
    const progressBase = batch.fileCount === 1 ? 0 : (batch.fileIndex / batch.fileCount) * 70;
    const progressStep = batch.fileCount === 1 ? 60 : 70 / batch.fileCount;
    setStatus(
      getRenderStatus(file, batch, pageNumber, pdf.numPages),
      progressBase + (pageNumber / pdf.numPages) * progressStep,
    );

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
      fileName: file.name,
      safeFileName,
      fileIndex: batch.fileIndex,
    });
    addPreview(dataUrl, pageNumber, canvas.width, canvas.height, file.name);
    setStatus(
      getRenderStatus(file, batch, pageNumber, pdf.numPages),
      progressBase + (pageNumber / pdf.numPages) * progressStep,
    );
  }

  return pages;
}

async function buildJpegArchive(jpegPages) {
  const zip = new JSZip();

  for (let index = 0; index < jpegPages.length; index += 1) {
    const jpegPage = jpegPages[index];
    const pageName = String(jpegPage.pageNumber).padStart(3, "0");
    const filename = selectedFiles.length === 1
      ? `${jpegPage.safeFileName}-page-${pageName}.jpg`
      : `${String(jpegPage.fileIndex + 1).padStart(2, "0")}-${jpegPage.safeFileName}/${jpegPage.safeFileName}-page-${pageName}.jpg`;
    zip.file(filename, jpegPage.base64, { base64: true });
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

function addPreview(dataUrl, pageNumber, pixelWidth, pixelHeight, fileName) {
  const figure = document.createElement("figure");
  figure.className = "page-card";

  const image = document.createElement("img");
  image.src = dataUrl;
  image.alt = `Страница ${pageNumber}`;

  const caption = document.createElement("figcaption");
  const title = document.createElement("strong");
  title.textContent = selectedFiles.length === 1
    ? `Страница ${pageNumber}`
    : `${fileName} — стр. ${pageNumber}`;
  const meta = document.createElement("span");
  meta.textContent = `${pixelWidth} x ${pixelHeight} px`;

  caption.append(title, meta);
  figure.append(image, caption);
  previewGrid.append(figure);
}

function setBusy(isBusy) {
  convertPdfButton.disabled = isBusy || selectedFiles.length !== 1;
  exportJpegsButton.disabled = isBusy || !selectedFiles.length;
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
