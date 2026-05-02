import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const outDir = resolve(root, "design/icon-concepts");

await mkdir(outDir, { recursive: true });

const concepts = [
  {
    file: "01-wand-document.svg",
    title: "Wand Document",
    svg: svgWrap(`
      <defs>
        <linearGradient id="bg" x1="80" y1="80" x2="944" y2="944" gradientUnits="userSpaceOnUse">
          <stop stop-color="#0f766e"/>
          <stop offset="1" stop-color="#133f5f"/>
        </linearGradient>
        <linearGradient id="paper" x1="286" y1="142" x2="738" y2="850" gradientUnits="userSpaceOnUse">
          <stop stop-color="#ffffff"/>
          <stop offset="1" stop-color="#eaf4f2"/>
        </linearGradient>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="26" stdDeviation="34" flood-color="#062a32" flood-opacity=".32"/>
        </filter>
      </defs>
      <rect width="1024" height="1024" rx="210" fill="url(#bg)"/>
      <path d="M316 130h276l130 132v610H316z" fill="url(#paper)" filter="url(#shadow)"/>
      <path d="M592 130v132h130z" fill="#cfe8e4"/>
      <rect x="364" y="408" width="300" height="44" rx="22" fill="#9ab0b9"/>
      <rect x="364" y="490" width="250" height="44" rx="22" fill="#b4c4ca"/>
      <rect x="364" y="572" width="284" height="44" rx="22" fill="#b4c4ca"/>
      <rect x="366" y="692" width="260" height="106" rx="34" fill="#e33343"/>
      <text x="496" y="766" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="62" font-weight="800" fill="#fff">PDF</text>
      <g transform="rotate(-35 612 356)">
        <rect x="580" y="206" width="72" height="476" rx="36" fill="#171923"/>
        <rect x="596" y="226" width="40" height="436" rx="20" fill="#fff7be"/>
        <rect x="582" y="204" width="68" height="84" rx="34" fill="#fff"/>
      </g>
      <path d="M744 190l20 52 52 20-52 20-20 52-20-52-52-20 52-20z" fill="#ffd84d"/>
      <path d="M238 284l14 36 36 14-36 14-14 36-14-36-36-14 36-14z" fill="#ffd84d"/>
      <path d="M756 640l13 34 34 13-34 13-13 34-13-34-34-13 34-13z" fill="#ffd84d"/>
    `),
  },
  {
    file: "02-spark-scan.svg",
    title: "Spark Scan",
    svg: svgWrap(`
      <defs>
        <linearGradient id="bg" x1="94" y1="92" x2="930" y2="930" gradientUnits="userSpaceOnUse">
          <stop stop-color="#172026"/>
          <stop offset=".55" stop-color="#0f766e"/>
          <stop offset="1" stop-color="#f2b84b"/>
        </linearGradient>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="28" stdDeviation="30" flood-color="#071b21" flood-opacity=".36"/>
        </filter>
      </defs>
      <rect width="1024" height="1024" rx="210" fill="url(#bg)"/>
      <g filter="url(#shadow)">
        <path d="M276 168h342l134 136v552H276z" fill="#fbf8ef"/>
        <path d="M618 168v136h134z" fill="#eadfc9"/>
        <path d="M330 402h366" stroke="#96a7ad" stroke-width="42" stroke-linecap="round"/>
        <path d="M330 508h320" stroke="#b9c4c8" stroke-width="42" stroke-linecap="round"/>
        <path d="M330 614h362" stroke="#b9c4c8" stroke-width="42" stroke-linecap="round"/>
        <path d="M306 724h420" stroke="#0f766e" stroke-width="54" stroke-linecap="round"/>
        <path d="M306 724h420" stroke="#ffffff" stroke-width="14" stroke-linecap="round" stroke-dasharray="38 36" opacity=".75"/>
      </g>
      <g transform="translate(626 166) rotate(39)">
        <rect x="-32" y="4" width="64" height="458" rx="32" fill="#111827"/>
        <rect x="-14" y="30" width="28" height="398" rx="14" fill="#ffd84d"/>
        <circle cx="0" cy="0" r="48" fill="#ffffff"/>
        <circle cx="0" cy="0" r="26" fill="#f2b84b"/>
      </g>
      <rect x="344" y="250" width="232" height="102" rx="30" fill="#e33343"/>
      <text x="460" y="321" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="64" font-weight="900" fill="#fff">PDF</text>
      <path d="M784 210l20 52 52 20-52 20-20 52-20-52-52-20 52-20z" fill="#fff7be"/>
      <path d="M206 258l14 36 36 14-36 14-14 36-14-36-36-14 36-14z" fill="#fff7be"/>
    `),
  },
  {
    file: "03-red-pdf-magic.svg",
    title: "Red PDF Magic",
    svg: svgWrap(`
      <defs>
        <linearGradient id="bg" x1="120" y1="80" x2="904" y2="944" gradientUnits="userSpaceOnUse">
          <stop stop-color="#f7fafc"/>
          <stop offset="1" stop-color="#d7ebe7"/>
        </linearGradient>
        <linearGradient id="red" x1="284" y1="144" x2="760" y2="864" gradientUnits="userSpaceOnUse">
          <stop stop-color="#ff4b5c"/>
          <stop offset="1" stop-color="#ba1f33"/>
        </linearGradient>
        <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="24" stdDeviation="28" flood-color="#10242c" flood-opacity=".28"/>
        </filter>
      </defs>
      <rect width="1024" height="1024" rx="210" fill="url(#bg)"/>
      <path d="M306 136h340l124 126v626H306z" fill="url(#red)" filter="url(#shadow)"/>
      <path d="M646 136v126h124z" fill="#ff8791"/>
      <text x="536" y="550" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="176" font-weight="900" fill="#fff">PDF</text>
      <path d="M360 660h332" stroke="#ffffff" stroke-width="36" stroke-linecap="round" opacity=".72"/>
      <path d="M408 734h236" stroke="#ffffff" stroke-width="32" stroke-linecap="round" opacity=".52"/>
      <g transform="translate(696 230) rotate(42)">
        <rect x="-26" y="12" width="52" height="402" rx="26" fill="#172026"/>
        <rect x="-9" y="44" width="18" height="326" rx="9" fill="#ffd84d"/>
        <circle cx="0" cy="0" r="42" fill="#0f766e"/>
        <circle cx="0" cy="0" r="20" fill="#fff7be"/>
      </g>
      <path d="M224 250l24 62 62 24-62 24-24 62-24-62-62-24 62-24z" fill="#0f766e"/>
      <path d="M790 694l18 48 48 18-48 18-18 48-18-48-48-18 48-18z" fill="#f2b84b"/>
    `),
  },
  {
    file: "04-minimal-magic-pdf.svg",
    title: "Minimal Magic PDF",
    svg: svgWrap(`
      <defs>
        <linearGradient id="bg" x1="92" y1="92" x2="932" y2="932" gradientUnits="userSpaceOnUse">
          <stop stop-color="#10242c"/>
          <stop offset="1" stop-color="#0f766e"/>
        </linearGradient>
      </defs>
      <rect width="1024" height="1024" rx="210" fill="url(#bg)"/>
      <circle cx="512" cy="512" r="322" fill="#f8fbfb"/>
      <circle cx="512" cy="512" r="278" fill="#e33343"/>
      <text x="512" y="566" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="176" font-weight="900" fill="#ffffff">PDF</text>
      <path d="M292 668c132-68 301-80 460-8" fill="none" stroke="#fff7be" stroke-width="38" stroke-linecap="round"/>
      <g transform="translate(628 178) rotate(38)">
        <rect x="-24" y="0" width="48" height="434" rx="24" fill="#172026"/>
        <rect x="-8" y="34" width="16" height="340" rx="8" fill="#ffd84d"/>
        <circle cx="0" cy="0" r="38" fill="#fff"/>
      </g>
      <path d="M732 222l20 52 52 20-52 20-20 52-20-52-52-20 52-20z" fill="#ffd84d"/>
      <path d="M286 260l13 34 34 13-34 13-13 34-13-34-34-13 34-13z" fill="#ffd84d"/>
    `),
  },
];

for (const concept of concepts) {
  await writeFile(resolve(outDir, concept.file), concept.svg);
}

await writeFile(resolve(outDir, "preview.html"), preview(concepts));

function svgWrap(content) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024" role="img">${content}</svg>\n`;
}

function preview(items) {
  const cards = items
    .map(
      (item) => `
        <figure>
          <img src="./${item.file}" alt="${item.title}">
          <figcaption>${item.title}</figcaption>
        </figure>
      `,
    )
    .join("");

  return `<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Magic PDF Icon Concepts</title>
  <style>
    body { margin: 0; font-family: system-ui, sans-serif; background: #f4f6f8; color: #172026; }
    main { max-width: 1180px; margin: 0 auto; padding: 32px; }
    h1 { margin: 0 0 22px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 18px; }
    figure { margin: 0; padding: 18px; background: white; border: 1px solid #dce4ea; border-radius: 10px; }
    img { display: block; width: 100%; aspect-ratio: 1; }
    figcaption { margin-top: 12px; font-weight: 700; }
  </style>
</head>
<body>
  <main>
    <h1>Magic PDF Icon Concepts</h1>
    <section class="grid">${cards}</section>
  </main>
</body>
</html>
`;
}
