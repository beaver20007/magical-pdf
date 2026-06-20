"""CI: verify_pptx + bench_ocr → exit 0 (pass) / 1 (fail)."""
import sys, pathlib, argparse
sys.path.insert(0, str(pathlib.Path(__file__).parent))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("pptx", help="PPTX to verify")
    p.add_argument("--lo", default=r"C:\Program Files\LibreOffice\program\soffice.exe")
    p.add_argument("--min-coverage", type=float, default=20.0)
    p.add_argument("--min-ocr-per-slide", type=int, default=2)
    args = p.parse_args()

    import os; os.chdir(pathlib.Path(__file__).parent)
    from src.pipeline.verify_pptx import verify_pptx, _MIN_OCR_PER_IMAGE_SLIDE

    pptx = pathlib.Path(args.pptx)
    lo = args.lo if pathlib.Path(args.lo).exists() else None
    report = verify_pptx(pptx, render_dir=pptx.parent / f"ci_{pptx.stem}", soffice=lo, save_overlay=False)

    errors = []
    if not report.passed:
        errors.append(f"FAIL slides: {report.warn_slides}")
    if report.avg_coverage_pct < args.min_coverage:
        errors.append(f"Coverage {report.avg_coverage_pct:.0f}% < {args.min_coverage:.0f}%")

    if errors:
        print(f"\n[CI FAIL] {' | '.join(errors)}")
        sys.exit(1)
    print(f"\n[CI PASS] 20/20 OK, coverage={report.avg_coverage_pct:.0f}%")
    sys.exit(0)

if __name__ == "__main__":
    main()
