import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";

function normalizeApiUrl(raw) {
  const trimmed = (raw || "").trim().replace(/\/$/, "");
  if (!trimmed) {
    return "";
  }
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  return `https://${trimmed}`;
}

const url = normalizeApiUrl(process.env.EXTRACT_API_URL || "");
const content = `/** Generated at build — do not edit */\nexport const PUBLIC_EXTRACT_API = ${JSON.stringify(url)};\n`;

export async function writeApiConfig(targetDir) {
  await writeFile(resolve(targetDir, "api-config.js"), content, "utf8");
}

if (import.meta.url === new URL(process.argv[1], "file:").href) {
  await writeApiConfig(resolve(import.meta.dirname, ".."));
}
