#!/usr/bin/env python3
"""Trial conversion — PDF → DOCX/PPTX (local quality)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline.convert import convert_pdf  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert scanned PDF to editable DOCX/PPTX")
    parser.add_argument("input", type=Path, help="Input PDF")
    parser.add_argument("-o", "--output", type=Path, help="Output DOCX")
    parser.add_argument("--pptx", type=Path, help="Output PPTX (landscape slides)")
    parser.add_argument("--manifest", type=Path, help="manifest.json path")
    parser.add_argument("--languages", default="ru,en")
    parser.add_argument("--layout", choices=["layout", "both", "visual", "flow"], default="layout")
    args = parser.parse_args()

    if not args.output and not args.pptx:
        parser.error("Specify -o DOCX and/or --pptx")

    manifest = args.manifest or (args.output or args.pptx).with_suffix(".manifest.json")
    assets = manifest.parent / "assets"

    def on_progress(p: float, msg: str) -> None:
        print(f"  [{int(p * 100):3d}%] {msg}", flush=True)

    langs = [x.strip() for x in args.languages.split(",") if x.strip()]
    print(f"Input: {args.input}")
    convert_pdf(
        args.input,
        output_docx=args.output,
        output_pptx=args.pptx,
        manifest_path=manifest,
        assets_dir=assets,
        languages=langs,
        layout_mode=args.layout,
        progress_callback=on_progress,
        validation_report_path=(args.output or args.pptx).with_suffix(".validation.txt"),
    )
    print(f"Done. Manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
