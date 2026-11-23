"""Optional Lensfun correction helpers.

Requires optional packages: lensfunpy and opencv-python.
If either package or a matching EXIF profile is unavailable, the source image
is returned unchanged.
"""
from pathlib import Path
from PIL import Image
import numpy as np

def _metadata(path):
    path = Path(path)
    make = model = lens = lens_make = None
    focal = aperture = distance = 0.0
    if path.suffix.lower() in {".arw", ".raw", ".cr2", ".cr3", ".nef", ".dng", ".orf", ".rw2", ".raf", ".pef"}:
        try:
            import rawpy
            with rawpy.imread(str(path)) as raw:
                md = raw.metadata
                make = getattr(md, "make", None)
                model = getattr(md, "model", None)
                lens = getattr(md, "lens", None)
                focal = float(getattr(md, "focal_len", 0) or 0)
                aperture = float(getattr(md, "aperture", 0) or 0)
        except Exception:
            pass
    else:
        try:
            from PIL.ExifTags import TAGS
            with Image.open(path) as im:
                exif = {TAGS.get(k, k): v for k, v in im.getexif().items()}
            make, model = exif.get("Make"), exif.get("Model")
            lens = exif.get("LensModel")
            lens_make = exif.get("LensMake")
            def _ratio(v):
                try:
                    return float(v[0]) / float(v[1]) if isinstance(v, tuple) else float(v)
                except Exception:
                    return 0.0
            focal = _ratio(exif.get("FocalLength", 0))
            aperture = _ratio(exif.get("FNumber", 0))
        except Exception:
            pass
    return make, model, lens_make, lens, focal, aperture, distance

def apply_lensfun(image: Image.Image, path):
    """Return (corrected_image, status)."""
    try:
        import cv2
        import lensfunpy
    except Exception:
        return image, "Lensfun недоступен: установите lensfunpy и opencv-python"
    make, model, lens_make, lens_name, focal, aperture, distance = _metadata(path)
    if not make or not model or not lens_name or not focal:
        return image, "В EXIF нет данных камеры/объектива"
    try:
        db = lensfunpy.Database()
        cameras = db.find_cameras(str(make), str(model))
        if not cameras:
            return image, "Профиль камеры не найден"
        lenses = db.find_lenses(cameras[0], str(lens_make or ""), str(lens_name))
        if not lenses:
            lenses = db.find_lenses(cameras[0], None, str(lens_name))
        if not lenses:
            return image, "Профиль объектива не найден"
        w, h = image.size
        modifier = lensfunpy.Modifier(lenses[0], cameras[0].crop_factor, w, h)
        modifier.initialize(float(focal), float(aperture or 0), float(distance or 1000), 1.0)
        maps = modifier.apply_subpixel_geometry_distortion()
        src = np.asarray(image.convert("RGB"))
        if maps is not None and getattr(maps, "ndim", 0) == 4 and maps.shape[2] == 3:
            channels = []
            for c in range(3):
                mx = np.asarray(maps[:, :, c, 0], dtype=np.float32)
                my = np.asarray(maps[:, :, c, 1], dtype=np.float32)
                channels.append(cv2.remap(src[:, :, c], mx, my, cv2.INTER_LANCZOS4,
                                          borderMode=cv2.BORDER_CONSTANT, borderValue=0))
            corrected = np.stack(channels, axis=2)
        else:
            geom = modifier.apply_geometry_distortion()
            if geom is None:
                return image, "Профиль не содержит коррекцию геометрии"
            mx = np.asarray(geom[:, :, 0], dtype=np.float32)
            my = np.asarray(geom[:, :, 1], dtype=np.float32)
            corrected = cv2.remap(src, mx, my, cv2.INTER_LANCZOS4,
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        # Lensfun color/vignetting methods vary by version; apply when exposed.
        try:
            modifier.apply_color_modification(corrected)
        except Exception:
            pass
        try:
            modifier.apply_vignetting(corrected, float(aperture or 0), float(distance or 1000), float(focal))
        except Exception:
            pass
        return Image.fromarray(corrected.astype(np.uint8), "RGB"), "Коррекция объектива применена"
    except Exception as exc:
        return image, f"Ошибка Lensfun: {str(exc)[:90]}"
