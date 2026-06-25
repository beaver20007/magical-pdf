/**
 * Phase 6 — 9 PDF quick-wins via pdf-lib (client-side, no server).
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

// ── helpers ───────────────────────────────────────────────────────────────────
function setStatus(msg) { statusText.textContent = msg; }
function setError(msg)  { errorBox.textContent = msg; errorBox.hidden = !msg; }
function setProgress(v) { progressBar.hidden = v == null; if (v != null) progressBar.value = Math.round(v * 100); }

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

function resetOutput() {
  downloads.hidden = true;
  setError("");
  setProgress(null);
  setStatus("");
}

// ── Tool definitions ──────────────────────────────────────────────────────────
const TOOLS = {
  merge: {
    name: "Объединить PDF",
    render() {
      return `
        <div class="panel-row">
          <label>PDF файлы (выберите несколько)</label>
          <input type="file" id="mergeFiles" accept=".pdf,application/pdf" multiple />
        </div>
        <button class="run-btn" id="runBtn">Объединить</button>`;
    },
    async run() {
      const files = Array.from(document.querySelector("#mergeFiles").files);
      if (files.length < 2) throw new Error("Выберите минимум 2 PDF файла.");
      const merged = await PDFDocument.create();
      for (let i = 0; i < files.length; i++) {
        setStatus(`Добавляю ${files[i].name}…`);
        setProgress(i / files.length);
        const buf = await readFile(files[i]);
        const src = await PDFDocument.load(buf);
        const pages = await merged.copyPages(src, src.getPageIndices());
        pages.forEach(p => merged.addPage(p));
      }
      setProgress(0.95);
      const bytes = await merged.save();
      showDownload(bytes, "merged.pdf");
      setStatus(`Готово! Объединено ${files.length} файлов, ${merged.getPageCount()} стр.`);
    },
  },

  split: {
    name: "Разделить PDF",
    render() {
      return `
        <div class="panel-row">
          <label>PDF файл</label>
          <input type="file" id="splitFile" accept=".pdf,application/pdf" />
        </div>
        <button class="run-btn" id="runBtn">Разделить на страницы</button>`;
    },
    async run() {
      const file = document.querySelector("#splitFile").files[0];
      if (!file) throw new Error("Выберите PDF файл.");
      const buf = await readFile(file);
      const src = await PDFDocument.load(buf);
      const count = src.getPageCount();
      const zip = new JSZip();
      for (let i = 0; i < count; i++) {
        setStatus(`Страница ${i + 1} / ${count}…`);
        setProgress(i / count);
        const single = await PDFDocument.create();
        const [page] = await single.copyPages(src, [i]);
        single.addPage(page);
        const bytes = await single.save();
        zip.file(`page-${String(i + 1).padStart(3, "0")}.pdf`, bytes);
      }
      setProgress(0.97);
      const blob = await zip.generateAsync({ type: "blob" });
      const stem = file.name.replace(/\.pdf$/i, "");
      showZipDownload(blob, `${stem}-pages.zip`);
      setStatus(`Готово! ${count} страниц в ZIP.`);
    },
  },

  compress: {
    name: "Сжать PDF",
    render() {
      return `
        <div class="panel-row">
          <label>PDF файл</label>
          <input type="file" id="compressFile" accept=".pdf,application/pdf" />
          <p class="field-hint">Удаляет метаданные и неиспользуемые объекты. Для изображений используйте Защитить (Protect) с низким качеством.</p>
        </div>
        <button class="run-btn" id="runBtn">Сжать</button>`;
    },
    async run() {
      const file = document.querySelector("#compressFile").files[0];
      if (!file) throw new Error("Выберите PDF файл.");
      setStatus("Загрузка…");
      const buf = await readFile(file);
      const doc = await PDFDocument.load(buf, { ignoreEncryption: true });
      doc.setTitle("");
      doc.setAuthor("");
      doc.setSubject("");
      doc.setKeywords([]);
      doc.setProducer("");
      doc.setCreator("");
      setProgress(0.8);
      const bytes = await doc.save({ useObjectStreams: true });
      const origKb = (file.size / 1024).toFixed(0);
      const newKb  = (bytes.byteLength / 1024).toFixed(0);
      const stem = file.name.replace(/\.pdf$/i, "");
      showDownload(bytes, `${stem}-compressed.pdf`);
      setStatus(`Готово! ${origKb} КБ → ${newKb} КБ.`);
    },
  },

  rotate: {
    name: "Повернуть страницы",
    render() {
      return `
        <div class="panel-row">
          <label>PDF файл</label>
          <input type="file" id="rotateFile" accept=".pdf,application/pdf" />
        </div>
        <div class="panel-row">
          <label>Угол поворота</label>
          <select id="rotateAngle">
            <option value="90">90° по часовой</option>
            <option value="180">180°</option>
            <option value="270">270° (90° против часовой)</option>
          </select>
        </div>
        <div class="panel-row">
          <label>Страницы</label>
          <input type="text" id="rotatePages" placeholder="Все или 1, 3-5, 7" />
        </div>
        <button class="run-btn" id="runBtn">Повернуть</button>`;
    },
    async run() {
      const file = document.querySelector("#rotateFile").files[0];
      if (!file) throw new Error("Выберите PDF файл.");
      const angle = parseInt(document.querySelector("#rotateAngle").value, 10);
      const pagesRaw = document.querySelector("#rotatePages").value.trim();
      const buf = await readFile(file);
      const doc = await PDFDocument.load(buf);
      const count = doc.getPageCount();
      const indices = pagesRaw ? parsePageRange(pagesRaw, count) : Array.from({ length: count }, (_, i) => i);
      for (const i of indices) {
        const page = doc.getPage(i);
        page.setRotation(degrees((page.getRotation().angle + angle) % 360));
      }
      const bytes = await doc.save();
      const stem = file.name.replace(/\.pdf$/i, "");
      showDownload(bytes, `${stem}-rotated.pdf`);
      setStatus(`Повёрнуто ${indices.length} стр. на ${angle}°.`);
    },
  },

  img2pdf: {
    name: "Фото → PDF",
    render() {
      return `
        <div class="panel-row">
          <label>Изображения JPEG / PNG (можно несколько)</label>
          <input type="file" id="imgFiles" accept="image/jpeg,image/png" multiple />
          <p class="field-hint">Каждое изображение — отдельная страница. Порядок — как в списке файлов.</p>
        </div>
        <button class="run-btn" id="runBtn">Создать PDF</button>`;
    },
    async run() {
      const files = Array.from(document.querySelector("#imgFiles").files);
      if (!files.length) throw new Error("Выберите хотя бы одно изображение.");
      const doc = await PDFDocument.create();
      for (let i = 0; i < files.length; i++) {
        setStatus(`Добавляю ${files[i].name}…`);
        setProgress(i / files.length);
        const buf = await readFile(files[i]);
        const isJpeg = files[i].type === "image/jpeg";
        const img = isJpeg ? await doc.embedJpg(buf) : await doc.embedPng(buf);
        const page = doc.addPage([img.width, img.height]);
        page.drawImage(img, { x: 0, y: 0, width: img.width, height: img.height });
      }
      const bytes = await doc.save();
      showDownload(bytes, "images.pdf");
      setStatus(`Готово! ${files.length} изображений → PDF.`);
    },
  },

  password: {
    name: "Защита паролем",
    render() {
      return `
        <div class="panel-row">
          <label>PDF файл</label>
          <input type="file" id="passFile" accept=".pdf,application/pdf" />
        </div>
        <div class="panel-row">
          <label>Пароль пользователя (открыть)</label>
          <input type="password" id="userPass" placeholder="Введите пароль…" autocomplete="new-password" />
        </div>
        <div class="panel-row">
          <label>Пароль владельца (редактирование)</label>
          <input type="password" id="ownerPass" placeholder="Оставьте пустым — будет = паролю пользователя" autocomplete="new-password" />
        </div>
        <button class="run-btn" id="runBtn">Зашифровать</button>`;
    },
    async run() {
      const file = document.querySelector("#passFile").files[0];
      const userPass  = document.querySelector("#userPass").value;
      const ownerPass = document.querySelector("#ownerPass").value || userPass;
      if (!file) throw new Error("Выберите PDF файл.");
      if (!userPass) throw new Error("Введите пароль.");
      const buf = await readFile(file);
      const doc = await PDFDocument.load(buf);
      const bytes = await doc.save({
        userPassword: userPass,
        ownerPassword: ownerPass,
        permissions: {
          printing: "highResolution",
          modifying: false,
          copying: false,
          annotating: false,
          fillingForms: false,
          contentAccessibility: true,
          documentAssembly: false,
        },
      });
      const stem = file.name.replace(/\.pdf$/i, "");
      showDownload(bytes, `${stem}-protected.pdf`);
      setStatus("Готово! PDF зашифрован.");
    },
  },

  metadata: {
    name: "Метаданные",
    render() {
      return `
        <div class="panel-row">
          <label>PDF файл</label>
          <input type="file" id="metaFile" accept=".pdf,application/pdf" />
        </div>
        <div class="panel-row">
          <label>Название</label>
          <input type="text" id="metaTitle" placeholder="Название документа" />
        </div>
        <div class="panel-row">
          <label>Автор</label>
          <input type="text" id="metaAuthor" placeholder="Имя автора" />
        </div>
        <div class="panel-row">
          <label>Тема</label>
          <input type="text" id="metaSubject" placeholder="Тема / описание" />
        </div>
        <div class="panel-row">
          <label>Ключевые слова</label>
          <input type="text" id="metaKeywords" placeholder="слово1, слово2" />
        </div>
        <button class="run-btn" id="runBtn">Применить</button>`;
    },
    async run() {
      const file = document.querySelector("#metaFile").files[0];
      if (!file) throw new Error("Выберите PDF файл.");
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
      setStatus("Метаданные обновлены.");
    },
  },

  pagenums: {
    name: "Номера страниц",
    render() {
      return `
        <div class="panel-row">
          <label>PDF файл</label>
          <input type="file" id="pnFile" accept=".pdf,application/pdf" />
        </div>
        <div class="panel-row">
          <label>Начать с номера</label>
          <input type="number" id="pnStart" value="1" min="1" />
        </div>
        <div class="panel-row">
          <label>Положение</label>
          <select id="pnPos">
            <option value="bottom-center">Снизу по центру</option>
            <option value="bottom-right">Снизу справа</option>
            <option value="top-center">Сверху по центру</option>
          </select>
        </div>
        <button class="run-btn" id="runBtn">Добавить номера</button>`;
    },
    async run() {
      const file = document.querySelector("#pnFile").files[0];
      if (!file) throw new Error("Выберите PDF файл.");
      const start = parseInt(document.querySelector("#pnStart").value, 10) || 1;
      const pos   = document.querySelector("#pnPos").value;
      const buf = await readFile(file);
      const doc = await PDFDocument.load(buf);
      const font = await doc.embedFont(StandardFonts.Helvetica);
      const fontSize = 11;
      const margin = 24;
      for (let i = 0; i < doc.getPageCount(); i++) {
        const page = doc.getPage(i);
        const { width, height } = page.getSize();
        const label = String(start + i);
        const tw = font.widthOfTextAtSize(label, fontSize);
        let x, y;
        if (pos === "bottom-center") { x = (width - tw) / 2; y = margin; }
        else if (pos === "bottom-right") { x = width - tw - margin; y = margin; }
        else { x = (width - tw) / 2; y = height - margin - fontSize; }
        page.drawText(label, { x, y, size: fontSize, font, color: rgb(0.3, 0.3, 0.3) });
      }
      const bytes = await doc.save();
      const stem = file.name.replace(/\.pdf$/i, "");
      showDownload(bytes, `${stem}-numbered.pdf`);
      setStatus(`Добавлены номера страниц (${start}–${start + doc.getPageCount() - 1}).`);
    },
  },

  watermark: {
    name: "Водяной знак",
    render() {
      return `
        <div class="panel-row">
          <label>PDF файл</label>
          <input type="file" id="wmFile" accept=".pdf,application/pdf" />
        </div>
        <div class="panel-row">
          <label>Текст водяного знака</label>
          <input type="text" id="wmText" placeholder="КОНФИДЕНЦИАЛЬНО" value="КОНФИДЕНЦИАЛЬНО" />
        </div>
        <div class="panel-row">
          <label>Прозрачность (0.05 – 0.5)</label>
          <input type="number" id="wmOpacity" value="0.12" min="0.05" max="0.5" step="0.01" />
        </div>
        <button class="run-btn" id="runBtn">Добавить водяной знак</button>`;
    },
    async run() {
      const file = document.querySelector("#wmFile").files[0];
      if (!file) throw new Error("Выберите PDF файл.");
      const text    = document.querySelector("#wmText").value.trim() || "WATERMARK";
      const opacity = parseFloat(document.querySelector("#wmOpacity").value) || 0.12;
      const buf = await readFile(file);
      const doc = await PDFDocument.load(buf);
      const font = await doc.embedFont(StandardFonts.HelveticaBold);
      const fontSize = 52;
      for (let i = 0; i < doc.getPageCount(); i++) {
        const page = doc.getPage(i);
        const { width, height } = page.getSize();
        const tw = font.widthOfTextAtSize(text, fontSize);
        page.drawText(text, {
          x: (width - tw) / 2,
          y: (height - fontSize) / 2,
          size: fontSize,
          font,
          color: rgb(0.4, 0.4, 0.4),
          opacity,
          rotate: degrees(35),
        });
      }
      const bytes = await doc.save();
      const stem = file.name.replace(/\.pdf$/i, "");
      showDownload(bytes, `${stem}-watermarked.pdf`);
      setStatus("Водяной знак добавлен на все страницы.");
    },
  },
};

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

// ── Tool activation ───────────────────────────────────────────────────────────
let activeTool = null;

toolGrid.querySelectorAll(".tool-card").forEach(card => {
  card.addEventListener("click", () => {
    const id = card.dataset.tool;
    toolGrid.querySelectorAll(".tool-card").forEach(c => c.classList.toggle("active", c === card));
    activeTool = id;
    resetOutput();
    const tool = TOOLS[id];
    toolPanel.innerHTML = `<h2>${tool.name}</h2>${tool.render()}`;
    toolPanel.hidden = false;
    document.querySelector("#runBtn").addEventListener("click", async () => {
      resetOutput();
      document.querySelector("#runBtn").disabled = true;
      setProgress(0.05);
      try {
        await TOOLS[activeTool].run();
        setProgress(null);
      } catch (err) {
        setError(err.message ?? String(err));
        setStatus("");
        setProgress(null);
      } finally {
        const btn = document.querySelector("#runBtn");
        if (btn) btn.disabled = false;
      }
    });
  });
});
