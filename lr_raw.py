import io
import time
from pathlib import Path
from PIL import Image
import rawpy

RAW_EXTS = {'.arw', '.raw', '.cr2', '.cr3', '.nef', '.dng', '.orf', '.rw2', '.raf', '.pef'}

def load_any_image(path: Path) -> Image.Image:
    if path.suffix.lower() in RAW_EXTS:
        with rawpy.imread(str(path)) as raw:
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    return Image.open(io.BytesIO(thumb.data))
                if thumb.format == rawpy.ThumbFormat.BITMAP:
                    return Image.fromarray(thumb.data)
            except Exception:
                pass
            rgb = raw.postprocess(use_camera_wb=True, half_size=True, no_auto_bright=True)
            return Image.fromarray(rgb)
    return Image.open(path)

def prepare_raw_frames(app, frames_list, tmp_dir: Path, p_end: float, format_eta_fn):
    if not any(p.suffix.lower() in RAW_EXTS for p in frames_list):
        return frames_list

    total = len(frames_list)
    converted = []
    start_t = time.time()

    for idx, src_path in enumerate(frames_list):
        if app.cancel_requested:
            raise RuntimeError("Рендер отменен пользователем")

        if src_path.suffix.lower() in RAW_EXTS:
            out_jpg = tmp_dir / f"raw_conv_{idx:05d}.jpg"
            with rawpy.imread(str(src_path)) as raw:
                rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=8)
            Image.fromarray(rgb).save(out_jpg, format="JPEG", quality=96)
            converted.append(out_jpg)
        else:
            converted.append(src_path)

        ratio = (idx + 1) / total
        val = p_end * ratio
        pct = int(val * 100)
        elapsed = time.time() - start_t
        if idx >= 1 and elapsed > 0.3:
            rem = (total - (idx + 1)) / ((idx + 1) / elapsed)
            eta = f" | осталось {format_eta_fn(rem)}"
        else:
            eta = " | расчет..."
        app.update_progress(val, f"Проявка RAW: {pct}%{eta}")

    return converted
