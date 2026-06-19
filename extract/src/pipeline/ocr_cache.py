"""OCR tile cache backed by JSON files keyed by image content hash."""
import hashlib, json
from pathlib import Path

def _cache_key(img, psm_key):
    raw = img.tobytes()
    h = hashlib.sha256(raw[:8192]).hexdigest()[:16]
    return h + '_' + psm_key

def load_ocr_cache(img, psm_key, assets_dir):
    if not assets_dir: return None
    d = Path(assets_dir) / '.ocr_cache'
    if not d.exists(): return None
    f = d / (_cache_key(img, psm_key) + '.json')
    if not f.exists(): return None
    try:
        data = json.loads(f.read_text(encoding='utf-8'))
        from src.pipeline.emit_pptx_slides import OcrWord
        return [OcrWord(**w) for w in data]
    except Exception:
        return None

def save_ocr_cache(img, psm_key, words, assets_dir):
    if not assets_dir: return
    d = Path(assets_dir) / '.ocr_cache'
    d.mkdir(exist_ok=True)
    f = d / (_cache_key(img, psm_key) + '.json')
    try:
        f.write_text(json.dumps([w._asdict() for w in words]), encoding='utf-8')
    except Exception:
        pass
