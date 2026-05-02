import { createServer } from "node:http";
import { createWriteStream } from "node:fs";
import { mkdir, stat } from "node:fs/promises";
import { extname, join, normalize, resolve } from "node:path";
import { homedir } from "node:os";
import { pipeline } from "node:stream/promises";
import { createReadStream } from "node:fs";

const root = resolve(import.meta.dirname, "..");
const downloadsDir = join(homedir(), "Downloads");
const port = Number(process.env.PORT || 5173);
const host = "127.0.0.1";

const mimeTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".pdf": "application/pdf",
  ".zip": "application/zip",
};

const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url, `http://${host}:${port}`);

    if (request.method === "POST" && url.pathname === "/save") {
      await savePostedFile(request, response, url);
      return;
    }

    if (request.method !== "GET" && request.method !== "HEAD") {
      send(response, 405, "Метод не поддерживается");
      return;
    }

    await serveStatic(url.pathname, request.method, response);
  } catch (error) {
    console.error(error);
    send(response, 500, "Ошибка сервера");
  }
});

server.listen(port, host, () => {
  console.log(`Magical PDF: http://${host}:${port}/`);
  console.log(`Сохранение файлов: ${downloadsDir}`);
});

async function serveStatic(pathname, method, response) {
  const requestedPath = pathname === "/" ? "/index.html" : decodeURIComponent(pathname);
  const filePath = normalize(resolve(root, `.${requestedPath}`));

  if (!filePath.startsWith(root)) {
    send(response, 403, "Доступ запрещён");
    return;
  }

  try {
    const fileStat = await stat(filePath);
    if (!fileStat.isFile()) {
      send(response, 404, "Файл не найден");
      return;
    }

    response.writeHead(200, {
      "Content-Type": mimeTypes[extname(filePath)] || "application/octet-stream",
      "Content-Length": fileStat.size,
    });

    if (method === "HEAD") {
      response.end();
      return;
    }

    await pipeline(createReadStream(filePath), response);
  } catch (error) {
    if (error.code === "ENOENT") {
      send(response, 404, "Файл не найден");
      return;
    }
    throw error;
  }
}

async function savePostedFile(request, response, url) {
  const filename = sanitizeFilename(url.searchParams.get("filename") || "result.bin");
  await mkdir(downloadsDir, { recursive: true });
  const targetPath = await uniquePath(join(downloadsDir, filename));
  await pipeline(request, createWriteStream(targetPath));
  const fileStat = await stat(targetPath);

  response.writeHead(200, { "Content-Type": "application/json; charset=utf-8" });
  response.end(JSON.stringify({ path: targetPath, size: fileStat.size }));
}

async function uniquePath(filePath) {
  const extension = extname(filePath);
  const basePath = filePath.slice(0, filePath.length - extension.length);

  for (let index = 0; index < 1000; index += 1) {
    const candidate = index === 0 ? filePath : `${basePath}-${index + 1}${extension}`;
    try {
      await stat(candidate);
    } catch (error) {
      if (error.code === "ENOENT") {
        return candidate;
      }
      throw error;
    }
  }

  throw new Error("Не удалось подобрать имя файла");
}

function sanitizeFilename(filename) {
  return filename.replace(/[/:\\?%*"<>|]/g, "_").trim() || "result.bin";
}

function send(response, status, message) {
  response.writeHead(status, { "Content-Type": "text/plain; charset=utf-8" });
  response.end(message);
}
