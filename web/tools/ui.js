/**
 * Phase 6 — 9 PDF quick-wins via pdf-lib (client-side, no server).
 * Includes: file preview, pre-processing options, step-by-step progress.
 */
import { initModeTabs } from "../../nav.js";

initModeTabs({ active: "tools" });

const { PDFDocument, degrees, rgb, StandardFonts } = window.PDFLib;
const JSZip = window.JSZip;

// ── DOM refs ──────────────────────────────────────────────────────────────────
const toolGrid    = document.querySelector("#toolGrid");
const toolPanel   = document.querySelector("#toolPanel");
const statusText  = document.querySelector("#statusText");
const progressBar = document.querySelector("#progressBar");
const downloads   = document.querySelector("#downloads");
const downloadLink = document.querySelector("#downloadLink");
const errorBox    = document.querySelector("#errorBox");

// ── State ─────────────────────────────────────────────────────────────────────
let activeTool = null;

// ── helpers ───────────────────────────────────────────────────────────────────
function setStatus(msg, progress) {
  statusText.textContent = msg;
  if (progress != null) {
    progressBar.hidden = false;
    progressBar.value = Math.round(progress * 100);
  }
}
function setError(msg)  { errorBox.textContent = msg; errorBox.hidden = !msg; }

function resetOutput() {
  downloads.hidden = true;
  setError("");
  progressBar.hidden = true;
  progressBar.value = 0;
  setStatus("");
}

function showDownload(bytes, filename) {
  const blob = new Blob([bytes], { type: "application/pdf" });
  downloadLink.href = URL.createObjectURL(blob);
  downloadLink.download = filename;
  downloadLink.textContent = `↓ ${filename}`;
  downloads.hidden = false;
}

function showZipDownload(blob, filename) {
  downloadLink.href = URL.createObjectURL(blob);
  downloadLink.download = filename;
  downloadLink.textContent = `↓ ${filename}`;
  downloads.hidden = false;
}

async function readFile(file) {
  return new Promise((res, rej) => {
    const r = new FileReader();
    r.onload = () => res(r.result);
    r.onerror = () => rej(r.error);
    r.readAsArrayBuffer(file);
  });
}

function fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(2)} МБ`;
}

/** Reads a PDF and returns { pageCount, title, author } */
async function pdfInfo(file) {
  try {
    const buf = await readFile(file);
    const doc = await PDFDocument.load(buf, { ignoreEncryption: true });
    return {
      pageCount: doc.getPageCount(),
      title: doc.getTitle() || "",
      author: doc.getAuthor() || "",
      subject: doc.getSubject() || "",
      keywords: (doc.getKeywords() || []).join(", "),
    };
  } catch {
    return { pageCount: "?", title: "", author: "", subject: "", keywords: "" };
  }
}

/** Renders a single PDF page to a canvas data URL for thumbnail */
async function pdfThumbnail(file, pageIndex = 0, maxW = 120) {
  if (!window.pdfjsLib) return null;
  try {
    const buf = await readFile(file);
    const pdf = await window.pdfjsLib.getDocument({ data: buf }).promise;
    const page = await pdf.getPage(pageIndex + 1);
    const vp = page.getViewport({ scale: 1 });
    const scale = maxW / vp.width;
    const viewport = page.getViewport({ scale });
    const canvas = document.createElement("canvas");
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
    return canvas.toDataURL("image/jpeg", 0.7);
  } catch {
    return null;
  }
}

/** Build a "file info" chip: icon + name + size + page count */
function fileChip(name, size, pageCount) {
  return `<div class="file-chip">
    <span class="file-chip__icon">📄</span>
    <div>
      <div class="file-chip__name">${name}</div>
      <div class="file-chip__meta">${fmtSize(size)}${pageCount != null ? ` · ${pageCount} стр.` : ""}</div>
    </div>
  </div>`;
}

/** Build a preview grid of multiple files */
async function buildFilePreview(files, showPages = true) {
  const items = await Promise.all(Array.from(files).map(async f => {
    const pages = showPages ? (await pdfInfo(f)).pageCount : null;
    return fileChip(f.name, f.size, pages);
  }));
  return `<div class="file-preview-list">${items.join("")}</div>`;
}

// ── Page range parser ─────────────────────────────────────────────────────────
function parsePageRange(raw, total) {
  const indices = new Set();
  raw.split(",").forEach(part => {
    const m = part.trim().match(/^(\d+)(?:-(\d+))?$/);
    if (!m) return;
    const from = parseInt(m[1], 10) - 1;
    const to   = m[2] ? parseInt(m[2], 10) - 1 : from;
    for (let i = Math.max(0, from); i <= Math.min(total - 1, to); i++) indices.add(i);
  });
  return [...indices].sort((a, b) => a - b);
}

// ── Tool definitions ──────────────────────────────────────────────────────────
const TOOLS = {

  merge: {
    name: "Объединить PDF",
    async render() {
      return `
        <div class="panel-row">
          <label>PDF файлы <span class="label-hint">(выберите 2 или больше)</span></label>
          <input type="file" id="mergeFiles" accept=".pdf,application/pdf" multiple />
          <div id="mergePreview"></div>
        </div>
        <p class="field-hint" style="margin:0">Перетащите файлы для смены порядка.</p>
        <button class="run-btn" id="runBtn" disabled>Объединить</button>`;
    },
    bindEvents() {
      let mergeOrder = [];
      const thumbCache = new Map(); // file → dataURL

      async function renderThumb(file) {
        if (thumbCache.has(file)) return thumbCache.get(file);
        if (!window.pdfjsLib) return null;
        try {
          const buf = await readFile(file);
          const pdf = await window.pdfjsLib.getDocument({ data: buf }).promise;
          const page = await pdf.getPage(1);
          const vp = page.getViewport({ scale: 1 });
          const scale = 240 / Math.max(vp.width, vp.height);
          const viewport = page.getViewport({ scale });
          const canvas = document.createElement("canvas");
          canvas.width  = Math.round(viewport.width);
          canvas.height = Math.round(viewport.height);
          const ctx = canvas.getContext("2d", { alpha: false });
          ctx.fillStyle = "#fff";
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          await page.render({ canvasContext: ctx, viewport }).promise;
          const url = canvas.toDataURL("image/jpeg", 0.82);
          thumbCache.set(file, url);
          return url;
        } catch { return null; }
      }

      async function renderMergeGrid() {
        const container = document.querySelector("#mergePreview");
        container.innerHTML = "";
        let dragSrc = null;

        for (let idx = 0; idx < mergeOrder.length; idx++) {
          const f = mergeOrder[idx];
          const card = document.createElement("div");
          card.className = "merge-card";
          card.draggable = true;
          card.dataset.idx = idx;

          // Thumbnail placeholder, fills in async
          const thumb = document.createElement("div");
          thumb.className = "merge-card__thumb";
          thumb.innerHTML = `<span class="merge-card__spinner">…</span>`;

          const num = document.createElement("span");
          num.className = "merge-card__num";
          num.textContent = idx + 1;

          const lbl = document.createElement("span");
          lbl.className = "merge-card__name";
          lbl.textContent = f.name.replace(/\.pdf$/i, "");

          const meta = document.createElement("span");
          meta.className = "merge-card__meta";
          meta.textContent = fmtSize(f.size);

          card.appendChild(thumb);
          card.appendChild(num);
          card.appendChild(lbl);
          card.appendChild(meta);
          container.appendChild(card);

          // Load thumbnail async
          renderThumb(f).then(url => {
            if (url) {
              const img = document.createElement("img");
              img.src = url;
              thumb.innerHTML = "";
              thumb.appendChild(img);
            } else {
              thumb.innerHTML = `<span class="merge-card__fallback">📄</span>`;
            }
          });

          // Async page count
          (async () => {
            try {
              const buf = await readFile(f);
              const doc = await window.PDFLib.PDFDocument.load(buf, { ignoreEncryption: true });
              meta.textContent = `${fmtSize(f.size)} · ${doc.getPageCount()} стр.`;
            } catch {}
          })();
        }

        // Drag events on all cards
        container.querySelectorAll(".merge-card").forEach(card => {
          card.addEventListener("dragstart", e => {
            dragSrc = parseInt(card.dataset.idx, 10);
            card.classList.add("dragging");
            e.dataTransfer.effectAllowed = "move";
          });
          card.addEventListener("dragend", () => card.classList.remove("dragging"));
          card.addEventListener("dragover", e => { e.preventDefault(); card.classList.add("drag-target"); });
          card.addEventListener("dragleave", () => card.classList.remove("drag-target"));
          card.addEventListener("drop", e => {
            e.preventDefault();
            card.classList.remove("drag-target");
            const dropIdx = parseInt(card.dataset.idx, 10);
            if (dragSrc === dropIdx) return;
            const moved = mergeOrder.splice(dragSrc, 1)[0];
            mergeOrder.splice(dropIdx, 0, moved);
            renderMergeGrid();
          });
        });

        document.querySelector("#runBtn")._mergeOrder = mergeOrder;
      }

      document.querySelector("#mergeFiles").addEventListener("change", async e => {
        const files = Array.from(e.target.files);
        const runBtn = document.querySelector("#runBtn");
        if (files.length < 2) { runBtn.disabled = true; return; }
        mergeOrder = files;
        thumbCache.clear();
        renderMergeGrid();
        runBtn.disabled = false;
      });
    },
    async run() {
      const runBtn = document.querySelector("#runBtn");
      let files = runBtn._mergeOrder || Array.from(document.querySelector("#mergeFiles").files);
      if (files.length < 2) throw new Error("Выберите минимум 2 PDF файла.");
      if (document.querySelector("#mergeOrder").value === "desc") files = [...files].reverse();
      const merged = await PDFDocument.create();
      for (let i = 0; i < files.length; i++) {
        setStatus(`Добавляю ${files[i].name}… (${i + 1}/${files.length})`, (i + 0.5) / files.length);
        const buf = await readFile(files[i]);
        const src = await PDFDocument.load(buf);
        const pages = await merged.copyPages(src, src.getPageIndices());
        pages.forEach(p => merged.addPage(p));
      }
      setStatus("Сохранение…", 0.95);
      const bytes = await merged.save();
      showDownload(bytes, "merged.pdf");
      setStatus(`Готово! Объединено ${files.length} файлов, ${merged.getPageCount()} стр.`, 1);
    },
  },

  split: {
    name: "Разделить PDF",
    async render() {
      return `
        <div class="panel-row">
          <label>PDF файл</label>
          <input type="file" id="splitFile" accept=".pdf,application/pdf" />
          <div id="splitPreview"></div>
        </div>
        <div class="panel-row">
          <label>Режим разделения</label>
          <select id="splitMode">
            <option value="pages">Каждая страница — отдельный файл (ZIP)</option>
            <option value="range">Диапазон страниц (один файл)</option>
          </select>
        </div>
        <div id="splitRangeRow" class="panel-row" hidden>
          <label>Диапазон страниц <span class="label-hint">напр. 1-3, 7</span></label>
          <input type="text" id="splitRange" placeholder="1-3, 7, 10-12" />
        </div>
        <button class="run-btn" id="runBtn" disabled>Разделить</button>`;
    },
    bindEvents() {
      document.querySelector("#splitFile").addEventListener("change", async e => {
        const file = e.target.files[0];
        if (!file) return;
        document.querySelector("#splitPreview").innerHTML = "<p class='preview-loading'>Чтение…</p>";
        const info = await pdfInfo(file);
        document.querySelector("#splitPreview").innerHTML = fileChip(file.name, file.size, info.pageCount);
        document.querySelector("#runBtn").disabled = false;
      });
      document.querySelector("#splitMode").addEventListener("change", e => {
        document.querySelector("#splitRangeRow").hidden = e.target.value !== "range";
      });
    },
    async run() {
      const file = document.querySelector("#splitFile").files[0];
      if (!file) throw new Error("Выберите PDF файл.");
      const mode = document.querySelector("#splitMode").value;
      const buf = await readFile(file);
      const src = await PDFDocument.load(buf);
      const count = src.getPageCount();
      const stem = file.name.replace(/\.pdf$/i, "");

      if (mode === "range") {
        const rangeRaw = document.querySelector("#splitRange").value.trim();
        if (!rangeRaw) throw new Error("Введите диапазон страниц.");
        const indices = parsePageRange(rangeRaw, count);
        if (!indices.length) throw new Error("Диапазон не содержит страниц.");
        setStatus(`Извлечение ${indices.length} стр.…`, 0.3);
        const out = await PDFDocument.create();
        const pages = await out.copyPages(src, indices);
        pages.forEach(p => out.addPage(p));
        const bytes = await out.save();
        showDownload(bytes, `${stem}-range.pdf`);
        setStatus(`Готово! Извлечено ${indices.length} стр.`, 1);
      } else {
        const zip = new JSZip();
        for (let i = 0; i < count; i++) {
          setStatus(`Страница ${i + 1} / ${count}…`, i / count);
          const single = await PDFDocument.create();
          const [page] = await single.copyPages(src, [i]);
          single.addPage(page);
          const bytes = await single.save();
          zip.file(`${stem}-page-${String(i + 1).padStart(3, "0")}.pdf`, bytes);
        }
        setStatus("Создание ZIP…", 0.97);
        const blob = await zip.generateAsync({ type: "blob" });
        showZipDownload(blob, `${stem}-pages.zip`);
        setStatus(`Готово! ${count} страниц → ZIP.`, 1);
      }
    },
  },

  compress: {
    name: "Сжать PDF",
    async render() {
      return `
        <div class="panel-row">
          <label>PDF файл</label>
          <input type="file" id="compressFile" accept=".pdf,application/pdf" />
          <div id="compressPreview"></div>
        </div>
        <div class="panel-row">
          <label>Уровень оптимизации</label>
          <select id="compressLevel">
            <option value="meta">Только метаданные (безопасно)</option>
            <option value="streams" selected>Метаданные + объектные потоки</option>
            <option value="full">Максимум (метаданные + потоки + xref)</option>
          </select>
          <p class="field-hint">Pdf-lib оптимизирует структуру файла. Для уменьшения изображений используйте «Защитить» с качеством «Низкое».</p>
        </div>
        <button class="run-btn" id="runBtn" disabled>Сжать</button>`;
    },
    bindEvents() {
      document.querySelector("#compressFile").addEventListener("change", async e => {
        const file = e.target.files[0];
        if (!file) return;
        document.querySelector("#compressPreview").innerHTML = "<p class='preview-loading'>Чтение…</p>";
        const info = await pdfInfo(file);
        document.querySelector("#compressPreview").innerHTML = fileChip(file.name, file.size, info.pageCount);
        document.querySelector("#runBtn").disabled = false;
      });
    },
    async run() {
      const file = document.querySelector("#compressFile").files[0];
      if (!file) throw new Error("Выберите PDF файл.");
      const level = document.querySelector("#compressLevel").value;
      setStatus("Загрузка файла…", 0.1);
      const buf = await readFile(file);
      setStatus("Разбор структуры PDF…", 0.3);
      const doc = await PDFDocument.load(buf, { ignoreEncryption: true });
      doc.setTitle(""); doc.setAuthor(""); doc.setSubject("");
      doc.setKeywords([]); doc.setProducer(""); doc.setCreator("");
      setStatus("Оптимизация…", 0.7);
      const saveOpts = {};
      if (level === "streams" || level === "full") saveOpts.useObjectStreams = true;
      if (level === "full") saveOpts.addDefaultPage = false;
      const bytes = await doc.save(saveOpts);
      const origKb = (file.size / 1024).toFixed(0);
      const newKb  = (bytes.byteLength / 1024).toFixed(0);
      const diff   = file.size - bytes.byteLength;
      const diffStr = diff > 0 ? `−${fmtSize(diff)}` : `+${fmtSize(-diff)}`;
      const stem = file.name.replace(/\.pdf$/i, "");
      showDownload(bytes, `${stem}-compressed.pdf`);
      setStatus(`Готово! ${origKb} КБ → ${newKb} КБ (${diffStr}).`, 1);
    },
  },

  rotate: {
    name: "Повернуть страницы",
    async render() {
      return `
        <div class="panel-row">
          <label>PDF файл</label>
          <input type="file" id="rotateFile" accept=".pdf,application/pdf" />
          <div id="rotateFileChip"></div>
        </div>
        <div class="panel-row">
          <label>Угол поворота</label>
          <div class="angle-row">
            <label class="angle-opt"><input type="radio" name="rotAngle" value="90"  checked /><span>↻ 90°</span></label>
            <label class="angle-opt"><input type="radio" name="rotAngle" value="180"         /><span>↕ 180°</span></label>
            <label class="angle-opt"><input type="radio" name="rotAngle" value="270"         /><span>↺ 270°</span></label>
          </div>
        </div>
        <div class="panel-row">
          <label>Страницы <span class="label-hint">пусто = все</span></label>
          <input type="text" id="rotatePages" placeholder="Все или 1, 3-5, 7" />
        </div>
        <div id="rotateThumbs" class="rotate-thumbs" hidden></div>
        <button class="run-btn" id="runBtn" disabled>Повернуть</button>`;
    },
    bindEvents() {
      let cachedPages = []; // { canvas, origAngle }

      async function loadThumbs(file) {
        if (!window.pdfjsLib) return;
        const container = document.querySelector("#rotateThumbs");
        container.innerHTML = "<p class='preview-loading'>Рендер страниц…</p>";
        container.hidden = false;
        const buf = await readFile(file);
        const pdf = await window.pdfjsLib.getDocument({ data: buf }).promise;
        const count = Math.min(pdf.numPages, 12); // show up to 12 pages
        cachedPages = [];
        container.innerHTML = "";
        for (let i = 1; i <= count; i++) {
          const page   = await pdf.getPage(i);
          const vp     = page.getViewport({ scale: 1 });
          const scale  = 160 / Math.max(vp.width, vp.height);
          const viewport = page.getViewport({ scale });
          const canvas = document.createElement("canvas");
          canvas.width  = Math.round(viewport.width);
          canvas.height = Math.round(viewport.height);
          const ctx = canvas.getContext("2d", { alpha: false });
          ctx.fillStyle = "#fff";
          ctx.fillRect(0, 0, canvas.width, canvas.height);
          await page.render({ canvasContext: ctx, viewport }).promise;
          cachedPages.push({ canvas, origAngle: 0 });
        }
        if (pdf.numPages > 12) {
          const more = document.createElement("p");
          more.className = "preview-loading";
          more.textContent = `+ ещё ${pdf.numPages - 12} стр.`;
          container.appendChild(more);
        }
        renderThumbs();
      }

      function renderThumbs() {
        const container = document.querySelector("#rotateThumbs");
        if (!container || !cachedPages.length) return;
        const angle = parseInt(document.querySelector("[name='rotAngle']:checked")?.value ?? 90, 10);
        // Clear previous cards (keep the "+ ещё" node if present)
        const oldCards = container.querySelectorAll(".rot-card");
        oldCards.forEach(c => c.remove());
        cachedPages.forEach(({ canvas }, idx) => {
          const card = document.createElement("div");
          card.className = "rot-card";
          const preview = document.createElement("div");
          preview.className = "rot-card__preview";
          const img = document.createElement("img");
          img.src = canvas.toDataURL("image/jpeg", 0.8);
          img.style.transform = `rotate(${angle}deg)`;
          img.style.transition = "transform 0.25s ease";
          preview.appendChild(img);
          const lbl = document.createElement("span");
          lbl.className = "rot-card__lbl";
          lbl.textContent = `стр. ${idx + 1}`;
          card.appendChild(preview);
          card.appendChild(lbl);
          container.insertBefore(card, container.querySelector(".preview-loading") ?? null);
        });
      }

      document.querySelector("#rotateFile").addEventListener("change", async e => {
        const file = e.target.files[0];
        if (!file) return;
        document.querySelector("#rotateFileChip").innerHTML = "<p class='preview-loading'>Чтение…</p>";
        const info = await pdfInfo(file);
        document.querySelector("#rotateFileChip").innerHTML = fileChip(file.name, file.size, info.pageCount);
        document.querySelector("#runBtn").disabled = false;
        loadThumbs(file);
      });

      document.querySelectorAll("[name='rotAngle']").forEach(el =>
        el.addEventListener("change", renderThumbs));
    },
    async run() {
      const file = document.querySelector("#rotateFile").files[0];
      if (!file) throw new Error("Выберите PDF файл.");
      const angle = parseInt(document.querySelector("[name='rotAngle']:checked").value, 10);
      const pagesRaw = document.querySelector("#rotatePages").value.trim();
      setStatus("Загрузка…", 0.1);
      const buf = await readFile(file);
      const doc = await PDFDocument.load(buf);
      const count = doc.getPageCount();
      const indices = pagesRaw ? parsePageRange(pagesRaw, count) : Array.from({ length: count }, (_, i) => i);
      setStatus(`Поворот ${indices.length} стр. на ${angle}°…`, 0.5);
      for (const i of indices) {
        const page = doc.getPage(i);
        page.setRotation(degrees((page.getRotation().angle + angle) % 360));
      }
      setStatus("Сохранение…", 0.9);
      const bytes = await doc.save();
      const stem = file.name.replace(/\.pdf$/i, "");
      showDownload(bytes, `${stem}-rotated.pdf`);
      setStatus(`Готово! Повёрнуто ${indices.length} из ${count} стр. на ${angle}°.`, 1);
    },
  },

  img2pdf: {
    name: "Фото → PDF",
    async render() {
      return `
        <div class="panel-row">
          <label>Изображения JPEG / PNG <span class="label-hint">(можно несколько; перетащите для смены порядка)</span></label>
          <input type="file" id="imgFiles" accept="image/jpeg,image/png" multiple />
          <div id="imgPreview" class="img-thumb-grid"></div>
        </div>
        <div class="panel-row">
          <label>Размер страницы</label>
          <select id="imgPageSize">
            <option value="image">По размеру изображения</option>
            <option value="a4">A4 портрет (595×842 pt)</option>
            <option value="a4l">A4 альбом (842×595 pt)</option>
          </select>
        </div>
        <div class="panel-row">
          <label>Качество</label>
          <div class="angle-row" id="imgQualityRow">
            <label class="angle-opt"><input type="radio" name="imgQ" value="original" checked /><span>Оригинал</span></label>
            <label class="angle-opt"><input type="radio" name="imgQ" value="0.92" /><span>Высокое</span></label>
            <label class="angle-opt"><input type="radio" name="imgQ" value="0.75" /><span>Среднее</span></label>
            <label class="angle-opt"><input type="radio" name="imgQ" value="0.50" /><span>Низкое</span></label>
          </div>
          <p class="field-hint">Высокое/Среднее/Низкое — перекодирует в JPEG через Canvas. Оригинал — встраивает как есть.</p>
        </div>
        <button class="run-btn" id="runBtn" disabled>Создать PDF</button>`;
    },
    bindEvents() {
      // Mutable ordered array of files (FileList is read-only).
      let imgOrder = [];

      function renderThumbs() {
        const grid = document.querySelector("#imgPreview");
        grid.innerHTML = "";
        imgOrder.forEach((f, idx) => {
          const url = URL.createObjectURL(f);
          const wrap = document.createElement("div");
          wrap.className = "img-thumb";
          wrap.draggable = true;
          wrap.dataset.idx = idx;

          const img = document.createElement("img");
          img.src = url;
          img.alt = f.name;

          const lbl = document.createElement("span");
          lbl.textContent = f.name.replace(/\.[^.]+$/, "");

          const num = document.createElement("span");
          num.className = "img-thumb__num";
          num.textContent = idx + 1;

          wrap.appendChild(num);
          wrap.appendChild(img);
          wrap.appendChild(lbl);
          grid.appendChild(wrap);
        });

        // Drag-and-drop reorder
        let dragSrc = null;
        grid.querySelectorAll(".img-thumb").forEach(el => {
          el.addEventListener("dragstart", e => {
            dragSrc = parseInt(el.dataset.idx, 10);
            el.classList.add("dragging");
            e.dataTransfer.effectAllowed = "move";
          });
          el.addEventListener("dragend", () => el.classList.remove("dragging"));
          el.addEventListener("dragover", e => { e.preventDefault(); el.classList.add("drag-target"); });
          el.addEventListener("dragleave", () => el.classList.remove("drag-target"));
          el.addEventListener("drop", e => {
            e.preventDefault();
            el.classList.remove("drag-target");
            const dropIdx = parseInt(el.dataset.idx, 10);
            if (dragSrc === dropIdx) return;
            const moved = imgOrder.splice(dragSrc, 1)[0];
            imgOrder.splice(dropIdx, 0, moved);
            renderThumbs();
          });
        });
      }

      document.querySelector("#imgFiles").addEventListener("change", e => {
        imgOrder = Array.from(e.target.files);
        if (!imgOrder.length) { document.querySelector("#runBtn").disabled = true; return; }
        renderThumbs();
        document.querySelector("#runBtn").disabled = false;
        // Store ordered list on the button so run() can access it.
        document.querySelector("#runBtn")._imgOrder = imgOrder;
      });

      // Keep reference updated after reorder.
      document.querySelector("#imgPreview").addEventListener("drop", () => {
        document.querySelector("#runBtn")._imgOrder = imgOrder;
      });
    },
    async run() {
      const runBtn = document.querySelector("#runBtn");
      const files = runBtn._imgOrder || Array.from(document.querySelector("#imgFiles").files);
      if (!files.length) throw new Error("Выберите хотя бы одно изображение.");
      const pageSize = document.querySelector("#imgPageSize").value;
      const qualityVal = document.querySelector("[name='imgQ']:checked").value;
      const doc = await PDFDocument.create();
      const A4_W = 595.28, A4_H = 841.89;

      for (let i = 0; i < files.length; i++) {
        setStatus(`Обрабатываю ${files[i].name}… (${i + 1}/${files.length})`, (i + 0.5) / files.length);

        let buf;
        if (qualityVal === "original") {
          buf = await readFile(files[i]);
        } else {
          // Re-encode via Canvas at chosen quality.
          const quality = parseFloat(qualityVal);
          buf = await new Promise((res, rej) => {
            const imgEl = new Image();
            const objUrl = URL.createObjectURL(files[i]);
            imgEl.onload = () => {
              const c = document.createElement("canvas");
              c.width = imgEl.naturalWidth;
              c.height = imgEl.naturalHeight;
              c.getContext("2d").drawImage(imgEl, 0, 0);
              URL.revokeObjectURL(objUrl);
              c.toBlob(blob => blob.arrayBuffer().then(res).catch(rej), "image/jpeg", quality);
            };
            imgEl.onerror = rej;
            imgEl.src = objUrl;
          });
        }

        const isJpeg = qualityVal !== "original" || files[i].type === "image/jpeg";
        const img = isJpeg ? await doc.embedJpg(buf) : await doc.embedPng(buf);
        let pw, ph, ix = 0, iy = 0, iw = img.width, ih = img.height;
        if (pageSize === "a4") {
          pw = A4_W; ph = A4_H;
          const s = Math.min(A4_W / img.width, A4_H / img.height);
          iw = img.width * s; ih = img.height * s;
          ix = (A4_W - iw) / 2; iy = (A4_H - ih) / 2;
        } else if (pageSize === "a4l") {
          pw = A4_H; ph = A4_W;
          const s = Math.min(A4_H / img.width, A4_W / img.height);
          iw = img.width * s; ih = img.height * s;
          ix = (A4_H - iw) / 2; iy = (A4_W - ih) / 2;
        } else {
          pw = img.width; ph = img.height;
        }
        const page = doc.addPage([pw, ph]);
        page.drawImage(img, { x: ix, y: iy, width: iw, height: ih });
      }
      setStatus("Сохранение PDF…", 0.97);
      const bytes = await doc.save();
      showDownload(bytes, "images.pdf");
      setStatus(`Готово! ${files.length} изображений → PDF.`, 1);
    },
  },

  password: {
    name: "Защита паролем",
    async render() {
      return `
        <div class="panel-row">
          <label>PDF файл</label>
          <input type="file" id="passFile" accept=".pdf,application/pdf" />
          <div id="passPreview"></div>
        </div>
        <div class="panel-row">
          <label>Пароль пользователя <span class="label-hint">(для открытия)</span></label>
          <input type="password" id="userPass" placeholder="Пароль…" autocomplete="new-password" />
        </div>
        <div class="panel-row">
          <label>Пароль владельца <span class="label-hint">(для редактирования; пусто = совпадает)</span></label>
          <input type="password" id="ownerPass" placeholder="Пусто — будет совпадать" autocomplete="new-password" />
        </div>
        <div class="panel-row">
          <label>Разрешения</label>
          <div class="checkbox-group">
            <label><input type="checkbox" id="permPrint" checked /> Печать</label>
            <label><input type="checkbox" id="permCopy" /> Копирование текста</label>
            <label><input type="checkbox" id="permModify" /> Редактирование</label>
          </div>
        </div>
        <button class="run-btn" id="runBtn" disabled>Зашифровать</button>`;
    },
    bindEvents() {
      document.querySelector("#passFile").addEventListener("change", async e => {
        const file = e.target.files[0];
        if (!file) return;
        const info = await pdfInfo(file);
        document.querySelector("#passPreview").innerHTML = fileChip(file.name, file.size, info.pageCount);
        document.querySelector("#runBtn").disabled = false;
      });
    },
    async run() {
      const file = document.querySelector("#passFile").files[0];
      const userPass  = document.querySelector("#userPass").value;
      const ownerPass = document.querySelector("#ownerPass").value || userPass;
      if (!file) throw new Error("Выберите PDF файл.");
      if (!userPass) throw new Error("Введите пароль.");
      setStatus("Загрузка…", 0.2);
      const buf = await readFile(file);
      const doc = await PDFDocument.load(buf);
      setStatus("Шифрование…", 0.7);
      const bytes = await doc.save({
        userPassword: userPass,
        ownerPassword: ownerPass,
        permissions: {
          printing: document.querySelector("#permPrint").checked ? "highResolution" : "none",
          modifying: document.querySelector("#permModify").checked,
          copying: document.querySelector("#permCopy").checked,
          annotating: false, fillingForms: true,
          contentAccessibility: true, documentAssembly: false,
        },
      });
      const stem = file.name.replace(/\.pdf$/i, "");
      showDownload(bytes, `${stem}-protected.pdf`);
      setStatus("Готово! PDF зашифрован.", 1);
    },
  },

  metadata: {
    name: "Метаданные",
    async render() {
      return `
        <div class="panel-row">
          <label>PDF файл <span class="label-hint">(поля заполнятся автоматически)</span></label>
          <input type="file" id="metaFile" accept=".pdf,application/pdf" />
          <div id="metaPreview"></div>
        </div>
        <div class="panel-row"><label>Название</label><input type="text" id="metaTitle" placeholder="Название документа" /></div>
        <div class="panel-row"><label>Автор</label><input type="text" id="metaAuthor" placeholder="Имя автора" /></div>
        <div class="panel-row"><label>Тема</label><input type="text" id="metaSubject" placeholder="Тема / описание" /></div>
        <div class="panel-row"><label>Ключевые слова</label><input type="text" id="metaKeywords" placeholder="слово1, слово2" /></div>
        <button class="run-btn" id="runBtn" disabled>Применить</button>`;
    },
    bindEvents() {
      document.querySelector("#metaFile").addEventListener("change", async e => {
        const file = e.target.files[0];
        if (!file) return;
        const info = await pdfInfo(file);
        document.querySelector("#metaPreview").innerHTML = fileChip(file.name, file.size, info.pageCount);
        if (info.title)    document.querySelector("#metaTitle").value = info.title;
        if (info.author)   document.querySelector("#metaAuthor").value = info.author;
        if (info.subject)  document.querySelector("#metaSubject").value = info.subject;
        if (info.keywords) document.querySelector("#metaKeywords").value = info.keywords;
        document.querySelector("#runBtn").disabled = false;
      });
    },
    async run() {
      const file = document.querySelector("#metaFile").files[0];
      if (!file) throw new Error("Выберите PDF файл.");
      setStatus("Загрузка…", 0.2);
      const buf = await readFile(file);
      const doc = await PDFDocument.load(buf);
      const title    = document.querySelector("#metaTitle").value.trim();
      const author   = document.querySelector("#metaAuthor").value.trim();
      const subject  = document.querySelector("#metaSubject").value.trim();
      const keywords = document.querySelector("#metaKeywords").value.trim();
      if (title)    doc.setTitle(title);
      if (author)   doc.setAuthor(author);
      if (subject)  doc.setSubject(subject);
      if (keywords) doc.setKeywords(keywords.split(",").map(s => s.trim()));
      const bytes = await doc.save();
      const stem = file.name.replace(/\.pdf$/i, "");
      showDownload(bytes, `${stem}-meta.pdf`);
      setStatus("Метаданные обновлены.", 1);
    },
  },

  pagenums: {
    name: "Номера страниц",
    async render() {
      return `
        <div class="panel-row">
          <label>PDF файл</label>
          <input type="file" id="pnFile" accept=".pdf,application/pdf" />
          <div id="pnPreview"></div>
        </div>
        <div class="panel-row">
          <label>Положение</label>
          <div class="pos-grid">
            <label class="angle-opt"><input type="radio" name="pnPos" value="top-left"     /><span>↖ Сверху слева</span></label>
            <label class="angle-opt"><input type="radio" name="pnPos" value="top-center"   /><span>↑ Сверху по центру</span></label>
            <label class="angle-opt"><input type="radio" name="pnPos" value="top-right"    /><span>↗ Сверху справа</span></label>
            <label class="angle-opt"><input type="radio" name="pnPos" value="bottom-left"  /><span>↙ Снизу слева</span></label>
            <label class="angle-opt"><input type="radio" name="pnPos" value="bottom-center" checked /><span>↓ Снизу по центру</span></label>
            <label class="angle-opt"><input type="radio" name="pnPos" value="bottom-right" /><span>↘ Снизу справа</span></label>
          </div>
        </div>
        <div class="panel-row">
          <label>Формат <span class="label-hint">используй {n} = номер, {total} = всего</span></label>
          <input type="text" id="pnFormat" value="{n}" placeholder="{n} / {total}" />
        </div>
        <div class="panel-row">
          <label>Начать с номера</label>
          <input type="number" id="pnStart" value="1" min="1" style="width:100px" />
        </div>
        <button class="run-btn" id="runBtn" disabled>Добавить номера</button>`;
    },
    bindEvents() {
      document.querySelector("#pnFile").addEventListener("change", async e => {
        const file = e.target.files[0];
        if (!file) return;
        const info = await pdfInfo(file);
        document.querySelector("#pnPreview").innerHTML = fileChip(file.name, file.size, info.pageCount);
        document.querySelector("#runBtn").disabled = false;
      });
    },
    async run() {
      const file = document.querySelector("#pnFile").files[0];
      if (!file) throw new Error("Выберите PDF файл.");
      const pos    = document.querySelector("[name='pnPos']:checked").value;
      const fmt    = document.querySelector("#pnFormat").value || "{n}";
      const start  = parseInt(document.querySelector("#pnStart").value, 10) || 1;
      setStatus("Загрузка…", 0.1);
      const buf = await readFile(file);
      const doc = await PDFDocument.load(buf);
      const font = await doc.embedFont(StandardFonts.Helvetica);
      const fontSize = 11, margin = 24;
      const total = doc.getPageCount();
      setStatus(`Добавление номеров страниц…`, 0.3);
      for (let i = 0; i < total; i++) {
        const page = doc.getPage(i);
        const { width, height } = page.getSize();
        const label = fmt.replace("{n}", String(start + i)).replace("{total}", String(total));
        const tw = font.widthOfTextAtSize(label, fontSize);
        let x, y;
        const isTop = pos.startsWith("top");
        const align = pos.endsWith("left") ? "left" : pos.endsWith("right") ? "right" : "center";
        y = isTop ? height - margin - fontSize : margin;
        if (align === "left")        x = margin;
        else if (align === "right")  x = width - tw - margin;
        else                         x = (width - tw) / 2;
        page.drawText(label, { x, y, size: fontSize, font, color: rgb(0.35, 0.35, 0.35) });
        if (i % 5 === 0) setStatus(`Страница ${i + 1} / ${total}…`, 0.3 + 0.6 * (i / total));
      }
      const bytes = await doc.save();
      const stem = file.name.replace(/\.pdf$/i, "");
      showDownload(bytes, `${stem}-numbered.pdf`);
      setStatus(`Готово! Номера ${start}–${start + total - 1} добавлены.`, 1);
    },
  },

  watermark: {
    name: "Водяной знак",
    async render() {
      return `
        <div class="panel-row">
          <label>PDF файл</label>
          <input type="file" id="wmFile" accept=".pdf,application/pdf" />
          <div id="wmFileChip"></div>
        </div>
        <div class="wm-layout">
          <div class="wm-controls">
            <div class="panel-row">
              <label>Текст</label>
              <input type="text" id="wmText" value="КОНФИДЕНЦИАЛЬНО" placeholder="КОНФИДЕНЦИАЛЬНО" />
            </div>
            <div class="panel-row">
              <label>Размер шрифта</label>
              <input type="range" id="wmFontSize" min="12" max="120" value="52" step="2" />
              <span id="wmFontSizeVal" class="range-val">52 pt</span>
            </div>
            <div class="panel-row">
              <label>Прозрачность</label>
              <input type="range" id="wmOpacity" min="3" max="60" value="12" step="1" />
              <span id="wmOpacityVal" class="range-val">12%</span>
            </div>
            <div class="panel-row">
              <label>Угол наклона</label>
              <div class="angle-row">
                <label class="angle-opt"><input type="radio" name="wmAngle" value="-45" /><span>↙ −45°</span></label>
                <label class="angle-opt"><input type="radio" name="wmAngle" value="-35" /><span>↙ −35°</span></label>
                <label class="angle-opt"><input type="radio" name="wmAngle" value="0"   /><span>— 0°</span></label>
                <label class="angle-opt"><input type="radio" name="wmAngle" value="35"  checked /><span>↗ 35°</span></label>
                <label class="angle-opt"><input type="radio" name="wmAngle" value="45"  /><span>↗ 45°</span></label>
              </div>
            </div>
            <div class="panel-row">
              <label>Цвет</label>
              <div class="angle-row">
                <label class="angle-opt"><input type="radio" name="wmColor" value="gray"  checked /><span>Серый</span></label>
                <label class="angle-opt"><input type="radio" name="wmColor" value="red"         /><span>Красный</span></label>
                <label class="angle-opt"><input type="radio" name="wmColor" value="blue"        /><span>Синий</span></label>
              </div>
            </div>
          </div>
          <div class="wm-preview-wrap">
            <canvas id="wmCanvas" class="wm-canvas"></canvas>
            <p class="wm-canvas-hint">Предпросмотр</p>
          </div>
        </div>
        <button class="run-btn" id="runBtn" disabled>Добавить водяной знак</button>`;
    },
    bindEvents() {
      const canvas = document.querySelector("#wmCanvas");
      const ctx    = canvas.getContext("2d");
      const W = 240, H = 170;
      const dpr = window.devicePixelRatio || 1;
      canvas.width  = W * dpr;
      canvas.height = H * dpr;
      canvas.style.width  = W + "px";
      canvas.style.height = H + "px";
      ctx.scale(dpr, dpr);

      const COLOR_CSS = { gray: [110,110,110], red: [190,35,35], blue: [30,60,190] };
      const COLOR_PDF = { gray: rgb(0.43,0.43,0.43), red: rgb(0.75,0.14,0.14), blue: rgb(0.12,0.24,0.75) };

      function drawPreview() {
        const text    = document.querySelector("#wmText").value || "WATERMARK";
        const size    = parseInt(document.querySelector("#wmFontSize").value, 10);
        const opacity = parseInt(document.querySelector("#wmOpacity").value, 10) / 100;
        const angle   = parseInt(document.querySelector("[name='wmAngle']:checked")?.value ?? 35, 10);
        const colorKey = document.querySelector("[name='wmColor']:checked")?.value ?? "gray";
        const [r, g, b] = COLOR_CSS[colorKey];

        ctx.clearRect(0, 0, W, H);

        // Page shadow
        ctx.fillStyle = "rgba(0,0,0,0.08)";
        ctx.beginPath(); ctx.roundRect(7, 7, W - 10, H - 10, 6); ctx.fill();

        // Page background
        ctx.fillStyle = "#ffffff";
        ctx.beginPath(); ctx.roundRect(4, 4, W - 10, H - 10, 5); ctx.fill();
        ctx.strokeStyle = "#e0e4e0"; ctx.lineWidth = 1; ctx.stroke();

        // Content lines
        ctx.strokeStyle = "rgba(0,0,0,0.06)"; ctx.lineWidth = 1;
        for (let y = 24; y < H - 18; y += 12) {
          const len = y % 36 === 0 ? 0.6 : 0.85;
          ctx.beginPath(); ctx.moveTo(18, y); ctx.lineTo((W - 22) * len + 18, y); ctx.stroke();
        }

        // Watermark
        ctx.save();
        ctx.translate(W / 2 - 3, H / 2 - 3);
        ctx.rotate(-angle * Math.PI / 180);
        ctx.globalAlpha = Math.min(opacity * 2.5, 0.9); // boost for canvas preview
        ctx.fillStyle = `rgb(${r},${g},${b})`;
        const scaledSize = Math.max(10, Math.min(size * (W / 595), 44));
        ctx.font = `bold ${scaledSize}px Arial, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(text, 0, 0);
        ctx.restore();
      }

      // Live update
      ["#wmText","#wmFontSize","#wmOpacity"].forEach(sel =>
        document.querySelector(sel).addEventListener("input", drawPreview));
      document.querySelectorAll("[name='wmAngle'],[name='wmColor']").forEach(el =>
        el.addEventListener("change", drawPreview));

      // Value readouts
      document.querySelector("#wmOpacity").addEventListener("input", e =>
        (document.querySelector("#wmOpacityVal").textContent = `${e.target.value}%`));
      document.querySelector("#wmFontSize").addEventListener("input", e =>
        (document.querySelector("#wmFontSizeVal").textContent = `${e.target.value} pt`));

      // File chip
      document.querySelector("#wmFile").addEventListener("change", async e => {
        const file = e.target.files[0];
        if (!file) return;
        const info = await pdfInfo(file);
        document.querySelector("#wmFileChip").innerHTML = fileChip(file.name, file.size, info.pageCount);
        document.querySelector("#runBtn").disabled = false;
      });

      drawPreview();
    },
    async run() {
      const file = document.querySelector("#wmFile").files[0];
      if (!file) throw new Error("Выберите PDF файл.");
      const text     = document.querySelector("#wmText").value.trim() || "WATERMARK";
      const opacity  = parseInt(document.querySelector("#wmOpacity").value, 10) / 100;
      const fontSize = parseInt(document.querySelector("#wmFontSize").value, 10);
      const angle    = parseInt(document.querySelector("[name='wmAngle']:checked").value, 10);
      const colorKey = document.querySelector("[name='wmColor']:checked")?.value ?? "gray";
      const COLOR_PDF = { gray: rgb(0.43,0.43,0.43), red: rgb(0.75,0.14,0.14), blue: rgb(0.12,0.24,0.75) };
      setStatus("Загрузка…", 0.1);
      const buf = await readFile(file);
      const doc = await PDFDocument.load(buf);
      const font = await doc.embedFont(StandardFonts.HelveticaBold);
      const total = doc.getPageCount();
      setStatus("Нанесение водяного знака…", 0.3);
      for (let i = 0; i < total; i++) {
        const page = doc.getPage(i);
        const { width, height } = page.getSize();
        const tw = font.widthOfTextAtSize(text, fontSize);
        page.drawText(text, {
          x: (width - tw) / 2,
          y: (height - fontSize) / 2,
          size: fontSize,
          font,
          color: COLOR_PDF[colorKey],
          opacity,
          rotate: degrees(angle),
        });
        if (i % 5 === 0) setStatus(`Страница ${i + 1} / ${total}…`, 0.3 + 0.6 * (i / total));
      }
      const bytes = await doc.save();
      const stem = file.name.replace(/\.pdf$/i, "");
      showDownload(bytes, `${stem}-watermarked.pdf`);
      setStatus(`Готово! Водяной знак добавлен на ${total} стр.`, 1);
    },
  },
};

// ── Tool activation ───────────────────────────────────────────────────────────
toolGrid.querySelectorAll(".tool-card").forEach(card => {
  card.addEventListener("click", async () => {
    const id = card.dataset.tool;
    toolGrid.querySelectorAll(".tool-card").forEach(c => c.classList.toggle("active", c === card));
    activeTool = id;
    resetOutput();

    const tool = TOOLS[id];
    toolPanel.innerHTML = `<h2>${tool.name}</h2><div class="tool-fields">${await tool.render()}</div>`;
    toolPanel.hidden = false;

    tool.bindEvents?.();

    document.querySelector("#runBtn").addEventListener("click", async () => {
      resetOutput();
      progressBar.hidden = false;
      progressBar.value = 0;
      document.querySelector("#runBtn").disabled = true;
      try {
        await TOOLS[activeTool].run();
      } catch (err) {
        setError(err.message ?? String(err));
        setStatus("");
        progressBar.hidden = true;
      } finally {
        const btn = document.querySelector("#runBtn");
        if (btn) btn.disabled = false;
      }
    });

    toolPanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });
});
