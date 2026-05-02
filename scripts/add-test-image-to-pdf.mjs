import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import vm from "node:vm";

const root = resolve(import.meta.dirname, "..");
const sourcePdfPath = "/Users/petrtsvetkov/Downloads/Встреча по печам .pdf";
const imagePath = "/Users/petrtsvetkov/Downloads/Claude.jpeg";
const outputPdfPath = "/Users/petrtsvetkov/Downloads/Встреча по печам -с картинкой.pdf";

const pdfLibCode = await readFile(resolve(root, "vendor/pdf-lib.min.js"), "utf8");
const sandbox = {
  exports: {},
  module: { exports: {} },
  ArrayBuffer,
  DataView,
  Int8Array,
  Uint8Array,
  Uint8ClampedArray,
  Int16Array,
  Uint16Array,
  Int32Array,
  Uint32Array,
  Promise,
  setTimeout,
  clearTimeout,
  TextDecoder,
  TextEncoder,
};
vm.createContext(sandbox);
vm.runInContext(pdfLibCode, sandbox);

const PDFLib = sandbox.exports;
const sourcePdfBytes = await readFile(sourcePdfPath);
const imageBytes = await readFile(imagePath);
const pdfDoc = await PDFLib.PDFDocument.load(sourcePdfBytes);
const image = await pdfDoc.embedJpg(imageBytes);
const firstPage = pdfDoc.getPages()[0];
const { width, height } = firstPage.getSize();

const imageWidth = Math.min(width * 0.34, 170);
const imageHeight = imageWidth * (image.height / image.width);
const x = width - imageWidth - 36;
const y = 36;

firstPage.drawImage(image, {
  x,
  y,
  width: imageWidth,
  height: imageHeight,
});

firstPage.drawRectangle({
  x: x - 6,
  y: y - 6,
  width: imageWidth + 12,
  height: imageHeight + 12,
  borderColor: PDFLib.rgb(0.05, 0.45, 0.42),
  borderWidth: 1.2,
});

const outputBytes = await pdfDoc.save();
await writeFile(outputPdfPath, outputBytes);

console.log(JSON.stringify({
  outputPdfPath,
  pages: pdfDoc.getPageCount(),
  bytes: outputBytes.length,
}));
