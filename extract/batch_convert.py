#!/usr/bin/env python3
"""
batch_convert.py — batch PDF -> PPTX conversion CLI.

Usage:
    python batch_convert.py --input /path/to/pdfs --output /path/to/output
    python batch_convert.py --input single.pdf --output /path/to/output --workers 2
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.pipeline.ingest import load_pdf
from src.pipeline.native_extract import extract_native_pdf
from src.pipeline.emit_pptx_slides import emit_pptx_slides


def _count_words(pptx_path: Path) -> int:
    """Count words in PPTX text boxes without extra deps."""
    try:
        import zipfile
        import re

        word_count = 0
        with zipfile.ZipFile(pptx_path) as z:
            for name in z.namelist():
                if name.startswith("ppt/slides/slide") and name.endswith(".xml"):
                    xml = z.read(name).decode("utf-8", errors="ignore")
                    # Strip XML tags, split on whitespace
                    text = re.sub(r"<[^>]+>", " ", xml)
                    word_count += len(text.split())
        return word_count
    except Exception:
        return 0


def _process_one(
    pdf_path: Path,
    output_dir: Path,
    dpi: int,
    use_cache: bool,
) -> dict:
    """Process a single PDF. Returns result dict."""
    t0 = time.time()
    out_path = output_dir / (pdf_path.stem + ".pptx")
    assets_dir = output_dir / "pptx_assets" / pdf_path.stem

    ir = load_pdf(pdf_path)
    extract_native_pdf(ir)
    emit_pptx_slides(ir, out_path, pdf_path, dpi=dpi, assets_dir=assets_dir)

    elapsed = time.time() - t0
    words = _count_words(out_path)
    size_kb = out_path.stat().st_size // 1024 if out_path.exists() else 0

    return {
        "file": pdf_path.name,
        "status": "OK",
        "words": words,
        "time": elapsed,
        "size_kb": size_kb,
        "error": "",
    }


def _process_one_safe(
    pdf_path: Path,
    output_dir: Path,
    dpi: int,
    use_cache: bool,
) -> dict:
    """Wrapper that catches all exceptions."""
    try:
        return _process_one(pdf_path, output_dir, dpi, use_cache)
    except Exception as exc:
        return {
            "file": pdf_path.name,
            "status": "ERROR",
            "words": 0,
            "time": 0.0,
            "size_kb": 0,
            "error": str(exc),
        }


def _worker_entry(args_tuple):
    """Top-level function for ProcessPoolExecutor (must be picklable)."""
    pdf_path, output_dir, dpi, use_cache = args_tuple
    return _process_one_safe(Path(pdf_path), Path(output_dir), dpi, use_cache)


def main():
    parser = argparse.ArgumentParser(
        description="Batch convert PDF slide decks to PPTX."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a folder containing PDF files, or a single PDF file.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output folder for PPTX files. Defaults to the same directory as input.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="OCR render DPI (default: 200).",
    )
    parser.add_argument(
        "--cache",
        type=lambda v: v.lower() not in ("0", "false", "no"),
        default=True,
        metavar="BOOL",
        help="Enable OCR tile cache (default: true).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Parallel worker processes (default: 1, max: 4).",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    workers = max(1, min(4, args.workers))

    # Collect PDFs
    if input_path.is_file():
        if input_path.suffix.lower() != ".pdf":
            print(f"ERROR: {input_path} is not a PDF file.", file=sys.stderr)
            sys.exit(1)
        pdf_files = [input_path]
        default_output = input_path.parent
    elif input_path.is_dir():
        pdf_files = sorted(input_path.glob("*.pdf"))
        default_output = input_path
    else:
        print(f"ERROR: {input_path} does not exist.", file=sys.stderr)
        sys.exit(1)

    if not pdf_files:
        print("No PDF files found.", file=sys.stderr)
        sys.exit(0)

    output_dir = Path(args.output) if args.output else default_output
    output_dir.mkdir(parents=True, exist_ok=True)

    total = len(pdf_files)
    results = [None] * total

    if workers == 1:
        for idx, pdf_path in enumerate(pdf_files, 1):
            print(f"Processing: {pdf_path.name} ({idx}/{total})")
            result = _process_one_safe(pdf_path, output_dir, args.dpi, args.cache)
            if result["status"] == "ERROR":
                print(f"  ERROR: {result['error']}")
            results[idx - 1] = result
    else:
        print(f"Using {workers} parallel workers.")
        task_args = [
            (str(p), str(output_dir), args.dpi, args.cache)
            for p in pdf_files
        ]
        # Map pdf path -> original index for ordered output
        path_to_idx = {str(p): i for i, p in enumerate(pdf_files)}

        with ProcessPoolExecutor(max_workers=workers) as executor:
            future_to_path = {
                executor.submit(_worker_entry, ta): ta[0] for ta in task_args
            }
            completed = 0
            for future in as_completed(future_to_path):
                completed += 1
                pdf_str = future_to_path[future]
                idx = path_to_idx[pdf_str]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        "file": Path(pdf_str).name,
                        "status": "ERROR",
                        "words": 0,
                        "time": 0.0,
                        "size_kb": 0,
                        "error": str(exc),
                    }
                print(
                    f"[{completed}/{total}] {result['status']}: {result['file']}"
                    + (f" — {result['error']}" if result["error"] else "")
                )
                results[idx] = result

    # Summary table
    print()
    print("-" * 80)
    col_file = max(len(r["file"]) for r in results)
    col_file = max(col_file, 20)
    header = (
        f"{'File':<{col_file}}  {'Status':<8}  {'Words':>7}  {'Time(s)':>8}  {'Size(KB)':>9}"
    )
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['file']:<{col_file}}  {r['status']:<8}  {r['words']:>7}  "
            f"{r['time']:>8.1f}  {r['size_kb']:>9}"
        )
        if r["error"]:
            print(f"  {'':>{col_file}}  Error: {r['error']}")
    print("-" * len(header))

    ok_count = sum(1 for r in results if r["status"] == "OK")
    err_count = total - ok_count
    total_time = sum(r["time"] for r in results)
    print(
        f"\nDone: {ok_count}/{total} converted successfully"
        + (f", {err_count} failed" if err_count else "")
        + f" — total time {total_time:.1f}s"
    )


if __name__ == "__main__":
    main()
