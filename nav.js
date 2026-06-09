/** Shared URLs for Protect / Extract across web, GitHub Pages, and local API. */

import { PUBLIC_EXTRACT_API } from "./api-config.js";

const GITHUB_PAGES_HOST = "beaver20007.github.io";
const REPO_SLUG = "magical-pdf";

export function isGitHubPages() {
  return location.hostname === GITHUB_PAGES_HOST;
}

/** Site root, e.g. /magical-pdf/ on GitHub Pages or / locally. */
export function siteRoot() {
  if (isGitHubPages()) {
    const match = location.pathname.match(new RegExp(`^(/${REPO_SLUG}/)`));
    return match ? match[1] : `/${REPO_SLUG}/`;
  }
  if (location.pathname.includes("/extract")) {
    return new URL("../", location.href).pathname;
  }
  return new URL("./", location.href).pathname;
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
  return new URL("extract/", siteRoot()).pathname;
}

/**
 * Extract jobs API base URL, or null when no API is configured.
 * Override: ?api=http://127.0.0.1:8765
 */
export function extractApiBase() {
  const custom = new URLSearchParams(location.search).get("api");
  if (custom) {
    return custom.replace(/\/$/, "");
  }
  if (location.port === "8765") {
    return "";
  }
  if (isGitHubPages()) {
    return PUBLIC_EXTRACT_API || null;
  }
  return "http://127.0.0.1:8765";
}

/** Remote beta API (GitHub Pages → cloud), not localhost. */
export function isPublicExtractBeta() {
  const base = extractApiBase();
  if (!base) {
    return false;
  }
  try {
    const host = new URL(base, location.origin).hostname;
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
