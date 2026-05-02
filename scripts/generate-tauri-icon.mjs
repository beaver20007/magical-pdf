import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { execFileSync } from "node:child_process";
import { deflateSync } from "node:zlib";

const root = resolve(import.meta.dirname, "..");
const iconDir = resolve(root, "src-tauri/icons");
const size = 1024;
const bytesPerPixel = 4;
const raw = Buffer.alloc((size * bytesPerPixel + 1) * size);
const colors = {
  ink: [21, 21, 21, 255],
  green: [118, 245, 138, 255],
  greenDark: [30, 167, 101, 255],
  sky: [200, 240, 255, 255],
  lavender: [239, 224, 255, 255],
  yellow: [255, 241, 106, 255],
  paper: [255, 255, 255, 255],
  paperWarm: [248, 255, 251, 255],
  white: [255, 255, 255, 255],
};

for (let y = 0; y < size; y += 1) {
  const rowStart = y * (size * bytesPerPixel + 1);
  raw[rowStart] = 0;

  for (let x = 0; x < size; x += 1) {
    const offset = rowStart + 1 + x * bytesPerPixel;
    const nx = x / (size - 1);
    const ny = y / (size - 1);
    const skyGlow = Math.max(0, 1 - Math.hypot(nx - 0.18, ny - 0.18) * 1.55);
    const lavenderGlow = Math.max(0, 1 - Math.hypot(nx - 0.82, ny - 0.76) * 1.35);
    const greenGlow = Math.max(0, 1 - Math.hypot(nx - 0.24, ny - 0.84) * 1.5);

    let r = Math.round(255 - 45 * skyGlow - 16 * greenGlow - 16 * lavenderGlow);
    let g = Math.round(255 - 15 * lavenderGlow - 3 * skyGlow);
    let b = Math.round(255 - 14 * greenGlow - 31 * skyGlow);
    let a = 255;

    raw[offset] = clampChannel(r);
    raw[offset + 1] = clampChannel(g);
    raw[offset + 2] = clampChannel(b);
    raw[offset + 3] = a;
  }
}

fillRoundedRect(560, 206, 176, 160, 30, colors.sky);
fillRoundedRect(596, 242, 176, 160, 30, colors.lavender);
fillCircle(178, 168, 44, colors.green);
fillCircle(850, 824, 58, colors.yellow);

fillRoundedRect(248, 148, 500, 708, 46, [21, 21, 21, 245]);
fillRoundedRect(270, 170, 456, 664, 32, colors.paper);
fillTriangle([596, 170], [726, 300], [596, 300], colors.paperWarm);
strokeLine(596, 174, 596, 300, 8, colors.ink);
strokeLine(600, 300, 724, 300, 8, colors.ink);

fillRoundedRect(326, 346, 326, 52, 24, [21, 21, 21, 165]);
fillRoundedRect(326, 454, 262, 44, 22, [21, 21, 21, 95]);
fillRoundedRect(326, 552, 318, 44, 22, [21, 21, 21, 95]);
fillRoundedRect(326, 662, 316, 116, 52, colors.green);
drawPdfLetters(374, 694, colors.ink);
strokeLine(330, 816, 664, 816, 30, colors.yellow);

drawRotatedCapsule(678, 242, 720, 722, 28, colors.ink);
drawRotatedCapsule(696, 294, 728, 654, 10, colors.yellow);
fillCircle(674, 210, 50, colors.ink);
fillCircle(674, 210, 30, colors.white);
fillCircle(674, 210, 16, colors.green);

drawSparkle(810, 188, 62, colors.green);
drawSparkle(202, 292, 44, colors.sky);
drawSparkle(782, 734, 42, colors.yellow);

await mkdir(iconDir, { recursive: true });
const sourceIcon = resolve(iconDir, "icon.png");
await writeFile(sourceIcon, encodePng(size, size, raw));
await writeFile(resolve(root, "public/app-icon.png"), encodePng(size, size, raw));
await generateMacIcons(sourceIcon);

function setPixel(x, y, color) {
  if (x < 0 || y < 0 || x >= size || y >= size) return;
  const offset = y * (size * bytesPerPixel + 1) + 1 + x * bytesPerPixel;
  const alpha = color[3] / 255;
  raw[offset] = Math.round(color[0] * alpha + raw[offset] * (1 - alpha));
  raw[offset + 1] = Math.round(color[1] * alpha + raw[offset + 1] * (1 - alpha));
  raw[offset + 2] = Math.round(color[2] * alpha + raw[offset + 2] * (1 - alpha));
  raw[offset + 3] = Math.max(raw[offset + 3], color[3]);
}

function clampChannel(value) {
  return Math.max(0, Math.min(255, value));
}

function fillRoundedRect(x, y, width, height, radius, color) {
  for (let py = y; py < y + height; py += 1) {
    for (let px = x; px < x + width; px += 1) {
      const dx = px < x + radius ? x + radius - px : px > x + width - radius ? px - (x + width - radius) : 0;
      const dy = py < y + radius ? y + radius - py : py > y + height - radius ? py - (y + height - radius) : 0;
      if (Math.hypot(dx, dy) <= radius) setPixel(px, py, color);
    }
  }
}

function fillTriangle(a, b, c, color) {
  const minX = Math.floor(Math.min(a[0], b[0], c[0]));
  const maxX = Math.ceil(Math.max(a[0], b[0], c[0]));
  const minY = Math.floor(Math.min(a[1], b[1], c[1]));
  const maxY = Math.ceil(Math.max(a[1], b[1], c[1]));
  const area = edge(a, b, c);
  for (let y = minY; y <= maxY; y += 1) {
    for (let x = minX; x <= maxX; x += 1) {
      const p = [x, y];
      const w0 = edge(b, c, p);
      const w1 = edge(c, a, p);
      const w2 = edge(a, b, p);
      if ((area >= 0 && w0 >= 0 && w1 >= 0 && w2 >= 0) || (area < 0 && w0 <= 0 && w1 <= 0 && w2 <= 0)) {
        setPixel(x, y, color);
      }
    }
  }
}

function edge(a, b, c) {
  return (c[0] - a[0]) * (b[1] - a[1]) - (c[1] - a[1]) * (b[0] - a[0]);
}

function strokeLine(x1, y1, x2, y2, width, color) {
  const minX = Math.floor(Math.min(x1, x2) - width);
  const maxX = Math.ceil(Math.max(x1, x2) + width);
  const minY = Math.floor(Math.min(y1, y2) - width);
  const maxY = Math.ceil(Math.max(y1, y2) + width);
  for (let y = minY; y <= maxY; y += 1) {
    for (let x = minX; x <= maxX; x += 1) {
      if (distanceToSegment(x, y, x1, y1, x2, y2) <= width / 2) setPixel(x, y, color);
    }
  }
}

function drawRotatedCapsule(x1, y1, x2, y2, width, color) {
  strokeLine(x1, y1, x2, y2, width, color);
  fillCircle(x1, y1, width / 2, color);
  fillCircle(x2, y2, width / 2, color);
}

function fillCircle(cx, cy, radius, color) {
  for (let y = Math.floor(cy - radius); y <= cy + radius; y += 1) {
    for (let x = Math.floor(cx - radius); x <= cx + radius; x += 1) {
      if (Math.hypot(x - cx, y - cy) <= radius) setPixel(x, y, color);
    }
  }
}

function drawSparkle(cx, cy, radius, color) {
  strokeLine(cx, cy - radius, cx, cy + radius, Math.max(10, radius * 0.12), color);
  strokeLine(cx - radius, cy, cx + radius, cy, Math.max(10, radius * 0.12), color);
  strokeLine(cx - radius * 0.46, cy - radius * 0.46, cx + radius * 0.46, cy + radius * 0.46, Math.max(6, radius * 0.07), color);
  strokeLine(cx - radius * 0.46, cy + radius * 0.46, cx + radius * 0.46, cy - radius * 0.46, Math.max(6, radius * 0.07), color);
  fillCircle(cx, cy, Math.max(8, radius * 0.16), color);
}

function drawPdfLetters(x, y, color) {
  fillRoundedRect(x, y, 26, 72, 6, color);
  fillRoundedRect(x, y, 66, 22, 6, color);
  fillRoundedRect(x, y + 32, 58, 20, 6, color);
  fillRoundedRect(x + 44, y + 14, 22, 34, 6, color);

  fillRoundedRect(x + 88, y, 26, 72, 6, color);
  fillRoundedRect(x + 88, y, 56, 22, 6, color);
  fillRoundedRect(x + 88, y + 50, 56, 22, 6, color);
  fillRoundedRect(x + 126, y + 12, 24, 48, 6, color);

  fillRoundedRect(x + 184, y, 26, 72, 6, color);
  fillRoundedRect(x + 184, y, 66, 22, 6, color);
  fillRoundedRect(x + 184, y + 32, 54, 20, 6, color);
}

function distanceToSegment(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const lengthSq = dx * dx + dy * dy;
  const t = lengthSq === 0 ? 0 : Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / lengthSq));
  const x = x1 + t * dx;
  const y = y1 + t * dy;
  return Math.hypot(px - x, py - y);
}

function encodePng(width, height, data) {
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  return Buffer.concat([
    signature,
    chunk("IHDR", Buffer.concat([
      uint32(width),
      uint32(height),
      Buffer.from([8, 6, 0, 0, 0]),
    ])),
    chunk("IDAT", deflateSync(data)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

function chunk(type, data) {
  const typeBuffer = Buffer.from(type);
  return Buffer.concat([
    uint32(data.length),
    typeBuffer,
    data,
    uint32(crc32(Buffer.concat([typeBuffer, data]))),
  ]);
}

function uint32(value) {
  const buffer = Buffer.alloc(4);
  buffer.writeUInt32BE(value >>> 0);
  return buffer;
}

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) {
      crc = crc & 1 ? (crc >>> 1) ^ 0xedb88320 : crc >>> 1;
    }
  }
  return (crc ^ 0xffffffff) >>> 0;
}

async function generateMacIcons(sourceIcon) {
  const iconsetDir = resolve(iconDir, "icon.iconset");
  await rm(iconsetDir, { recursive: true, force: true });
  await mkdir(iconsetDir, { recursive: true });

  const iconSizes = [
    ["16", 16],
    ["16@2x", 32],
    ["32", 32],
    ["32@2x", 64],
    ["128", 128],
    ["128@2x", 256],
    ["256", 256],
    ["256@2x", 512],
    ["512", 512],
    ["512@2x", 1024],
  ];

  for (const [name, pixelSize] of iconSizes) {
    const baseName = name.includes("@2x")
      ? `icon_${name.replace("@2x", "x" + name.split("@")[0] + "@2x")}.png`
      : `icon_${name}x${name}.png`;
    execFileSync("sips", ["-z", String(pixelSize), String(pixelSize), sourceIcon, "--out", resolve(iconsetDir, baseName)], {
      stdio: "ignore",
    });
  }

  execFileSync("sips", ["-z", "32", "32", sourceIcon, "--out", resolve(iconDir, "32x32.png")], { stdio: "ignore" });
  execFileSync("sips", ["-z", "128", "128", sourceIcon, "--out", resolve(iconDir, "128x128.png")], { stdio: "ignore" });
  execFileSync("sips", ["-z", "256", "256", sourceIcon, "--out", resolve(iconDir, "128x128@2x.png")], { stdio: "ignore" });
  await writeIcns([
    ["icp4", resolve(iconsetDir, "icon_16x16.png")],
    ["icp5", resolve(iconsetDir, "icon_32x32.png")],
    ["icp6", resolve(iconsetDir, "icon_32x32@2x.png")],
    ["ic07", resolve(iconsetDir, "icon_128x128.png")],
    ["ic08", resolve(iconsetDir, "icon_256x256.png")],
    ["ic09", resolve(iconsetDir, "icon_512x512.png")],
    ["ic10", resolve(iconsetDir, "icon_512x512@2x.png")],
  ], resolve(iconDir, "icon.icns"));
}

async function writeIcns(entries, outputPath) {
  const chunks = [];
  for (const [type, filePath] of entries) {
    const data = await readFile(filePath);
    chunks.push(Buffer.concat([Buffer.from(type), uint32(data.length + 8), data]));
  }

  const body = Buffer.concat(chunks);
  await writeFile(outputPath, Buffer.concat([Buffer.from("icns"), uint32(body.length + 8), body]));
}
