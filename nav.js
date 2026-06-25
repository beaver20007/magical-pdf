/** Shared URLs for Protect / Extract across web, GitHub Pages, and local API. */

import { PUBLIC_EXTRACT_API } from "./api-config.js";

const GITHUB_PAGES_HOST = "beaver20007.github.io";
const REPO_SLUG = "magical-pdf";

export function isGitHubPages() {
  return location.hostname === GITHUB_PAGES_HOST;
}

/** Absolute site root URL, e.g. https://beaver20007.github.io/magical-pdf/ */
export function siteRoot() {
  if (isGitHubPages()) {
    const match = location.pathname.match(new RegExp(`^(/${REPO_SLUG}/)`));
    const path = match ? match[1] : `/${REPO_SLUG}/`;
    return new URL(path, location.origin).href;
  }
  if (location.pathname.includes("/extract")) {
    return new URL("../", location.href).href;
  }
  return new URL("./", location.href).href;
}

export function protectHref() {
  if (location.port === "8765") {
    return "http://127.0.0.1:5173/";
  }
  return siteRoot();
}

export function extractHref() {
  if (location.port === "8765") {
    return "/";
  }
  return new URL("extract/", siteRoot()).href;
}

function normalizeApiBase(value) {
  const trimmed = (value || "").trim().replace(/\/$/, "");
  if (!trimmed) {
    return null;
  }
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  return `https://${trimmed}`;
}

/**
 * Extract jobs API base URL, or null when no API is configured.
 * Override: ?api=http://127.0.0.1:8766
 * Port 8765 is reserved by SSH tunnel on this machine; Extract uses 8766.
 */
export function extractApiBase() {
  const custom = new URLSearchParams(location.search).get("api");
  if (custom) {
    return normalizeApiBase(custom);
  }
  if (location.port === "8766") {
    return "";
  }
  if (isGitHubPages()) {
    return normalizeApiBase(PUBLIC_EXTRACT_API);
  }
  return "http://127.0.0.1:8766";
}

/** Remote beta API (GitHub Pages → cloud), not localhost. */
export function isPublicExtractBeta() {
  const base = extractApiBase();
  if (!base) {
    return false;
  }
  try {
    const host = new URL(base).hostname;
    return host !== "127.0.0.1" && host !== "localhost";
  } catch {
    return false;
  }
}

export function initModeTabs({ active }) {
  const protect = document.querySelector("#tabProtect");
  const extract = document.querySelector("#tabExtract");
  if (protect) protect.href = protectHref();
  if (extract) extract.href = extractHref();
  if (protect) protect.classList.toggle("active", active === "protect");
  if (extract) extract.classList.toggle("active", active === "extract");
}
