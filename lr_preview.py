import math
import numpy as np
from PIL import Image, ImageFilter, ImageOps
from lr_white_balance import white_balance_gains
from lr_lens import apply_lensfun


def get_zoom_rect(cw: int, ch: int, zoom: float, pan_x_pct: float, pan_y_pct: float):
    z = max(1.0, float(zoom))
    zw = max(1, int(cw / z))
    zh = max(1, int(ch / z))
    px = max(0.0, min(1.0, float(pan_x_pct) / 100.0))
    py = max(0.0, min(1.0, float(pan_y_pct) / 100.0))
    cx = (cw - zw) / 2.0 + px * ((cw - zw) / 2.0)
    cy = (ch - zh) / 2.0 + py * ((ch - zh) / 2.0)
    left = max(0, min(cw - zw, int(round(cx))))
    top = max(0, min(ch - zh, int(round(cy))))
    return left, top, left + zw, top + zh


def rotate_and_crop_inner(img: Image.Image, angle_deg: float) -> Image.Image:
    if abs(angle_deg) < 0.05:
        return img
    w, h = img.size
    rad = math.radians(abs(angle_deg))
    sin_a, cos_a = math.sin(rad), math.cos(rad)
    scale = max((w * cos_a + h * sin_a) / w, (w * sin_a + h * cos_a) / h)
    nw, nh = max(w, int(w * scale)), max(h, int(h * scale))
    scaled = img.resize((nw, nh), Image.Resampling.BILINEAR)
    rotated = scaled.rotate(-angle_deg, resample=Image.Resampling.BILINEAR, expand=False)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return rotated.crop((left, top, left + w, top + h))


def _apply_ffmpeg_curves(arr: np.ndarray, shadows: float, highlights: float) -> np.ndarray:
    # Mirrors the control points used by lr_filters.build_ffmpeg_filters().
    p25 = max(0.02, min(0.48, 0.25 + shadows * 0.08))
    p75 = max(0.52, min(0.98, 0.75 + highlights * 0.08))
    x = np.array([0.0, 0.25, 0.75, 1.0], dtype=np.float32)
    y = np.array([0.0, p25, p75, 1.0], dtype=np.float32)
    return np.interp(arr, x, y).astype(np.float32)


def process_preview_image(app, raw_img: Image.Image, max_size=(660, 500)) -> Image.Image:
    img = raw_img.copy().convert("RGB")
    if getattr(app, "lens_sw", None) is not None and app.lens_sw.get() and app.image_files:
        try:
            img, _lens_status = apply_lensfun(img, app.image_files[app.current_idx])
        except Exception:
            pass
    w, h = img.size
    aspect = app.aspect_menu.get()
    target_ratio = (16 / 9) if "16:9" in aspect else ((9 / 16) if "9:16" in aspect else (w / h))
    mode = getattr(app, "frame_mode", "Заполнить кадр")

    if "Вписать" in mode or "Размытый" in mode:
        max_w, max_h = max(1, int(max_size[0])), max(1, int(max_size[1]))
        canvas_w = min(max_w, max(1, int(round(max_h * target_ratio))))
        canvas_h = min(max_h, max(1, int(round(canvas_w / target_ratio))))
        if "Размытый" in mode:
            canvas = ImageOps.fit(img, (canvas_w, canvas_h), method=Image.Resampling.LANCZOS)
            canvas = canvas.filter(ImageFilter.GaussianBlur(radius=max(8, int(min(canvas_w, canvas_h) * 0.035))))
            foreground = ImageOps.contain(img, (canvas_w, canvas_h), method=Image.Resampling.LANCZOS)
            canvas.paste(foreground, ((canvas_w - foreground.width) // 2, (canvas_h - foreground.height) // 2))
        else:
            canvas = Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))
            foreground = ImageOps.contain(img, (canvas_w, canvas_h), method=Image.Resampling.LANCZOS)
            canvas.paste(foreground, ((canvas_w - foreground.width) // 2, (canvas_h - foreground.height) // 2))
        img = canvas
    else:
        cur_ratio = w / h
        if abs(cur_ratio - target_ratio) > 0.01:
            if cur_ratio > target_ratio:
                new_w = max(1, int(h * target_ratio))
                left = (w - new_w) // 2
                img = img.crop((left, 0, left + new_w, h))
            else:
                new_h = max(1, int(w / target_ratio))
                top = (h - new_h) // 2
                img = img.crop((0, top, w, top + new_h))

    # Work at preview resolution, not at the cached 2560px source size.
    # This avoids recalculating millions of pixels for every slider movement.
    max_w, max_h = max(1, int(max_size[0])), max(1, int(max_size[1]))
    preview_scale = min(1.0, max_w / img.width, max_h / img.height)
    if preview_scale < 1.0:
        preview_size = (
            max(1, int(round(img.width * preview_scale))),
            max(1, int(round(img.height * preview_scale)))
        )
        img = img.resize(preview_size, Image.Resampling.BILINEAR)

    angle = app.sl_rot.get()
    if abs(angle) >= 0.05:
        img = rotate_and_crop_inner(img, angle)

    exp = app.sl_exp.get()
    con = app.sl_con.get()
    hi = app.sl_hi.get()
    sh = app.sl_sh.get()
    sat = app.sl_sat.get()
    tmp = app.sl_tmp.get()
    tint = app.sl_tint.get()
    sharp = app.sl_sharp.get()

    arr = np.asarray(img, dtype=np.float32) / 255.0
    if abs(sh) > 0.01 or abs(hi) > 0.01:
        arr = _apply_ffmpeg_curves(arr, sh, hi)

    br = exp * 0.22
    if abs(con - 1.0) > 0.01 or abs(br) > 0.001:
        arr = (arr - 0.5) * con + 0.5 + br

    if abs(sat - 1.0) > 0.01:
        luma = arr[:, :, 0:1] * 0.2126 + arr[:, :, 1:2] * 0.7152 + arr[:, :, 2:3] * 0.0722
        arr = luma + (arr - luma) * sat

    if abs(tmp) > 0.5 or abs(tint) > 0.5:
        gains = white_balance_gains(tmp, tint)
        arr *= np.asarray(gains, dtype=np.float32).reshape((1, 1, 3))

    arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, mode="RGB")

    scale = min(max_w / img.width, max_h / img.height)
    target_size = (max(1, int(round(img.width * scale))), max(1, int(round(img.height * scale))))
    if target_size != img.size:
        img = img.resize(target_size, Image.Resampling.LANCZOS)

    # Export sharpens before zooming; apply at preview resolution for a close visual match.
    if sharp > 0.02:
        img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=int(sharp * 110), threshold=2))

    # Show the first exported frame's crop. The preview is static, while export animates
    # between start and end zoom/pan values over the full sequence.
    if app.zoom_sw.get():
        z_start = app.sl_zoom_start.get()
        z_end = app.sl_zoom_end.get()
        if z_start > 1.005 or z_end > 1.005:
            x1, y1, x2, y2 = get_zoom_rect(
                img.width, img.height, z_start,
                app.sl_start_x.get(), app.sl_start_y.get()
            )
            img = img.crop((x1, y1, x2, y2)).resize(target_size, Image.Resampling.LANCZOS)

    app.last_preview_size = img.size
    return img
