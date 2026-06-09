import { cp, copyFile, mkdir, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { writeApiConfig } from "./generate-api-config.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const dist = resolve(root, "dist");
const files = ["index.html", "styles.css", "app.js", "nav.js", "api-config.js"];

await rm(dist, { recursive: true, force: true });
await mkdir(dist, { recursive: true });

for (const file of files) {
  await copyFile(resolve(root, file), resolve(dist, file));
}

await cp(resolve(root, "vendor"), resolve(dist, "vendor"), { recursive: true });
await cp(resolve(root, "public"), dist, { recursive: true });
await cp(resolve(root, "public"), resolve(dist, "public"), { recursive: true });

const extractDist = resolve(dist, "extract");
await mkdir(extractDist, { recursive: true });
await copyFile(resolve(root, "web/extract/index.html"), resolve(extractDist, "index.html"));

const extractStatic = resolve(root, "extract/static");
for (const file of ["ui.css", "ui.js", "nav.js", "api-config.js"]) {
  await copyFile(resolve(extractStatic, file), resolve(extractDist, file));
}

await writeApiConfig(dist);
await writeApiConfig(extractDist);
