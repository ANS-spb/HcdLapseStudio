import math
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

def get_zoom_rect(cw: int, ch: int, zoom: float, pan_x_pct: float, pan_y_pct: float):
    z = max(1.0, zoom)
    zw = int(cw / z)
    zh = int(ch / z)
    px = max(-1.0, min(1.0, pan_x_pct / 100.0))
    py = max(-1.0, min(1.0, pan_y_pct / 100.0))
    cx = (cw - zw) / 2.0 + px * ((cw - zw) / 2.0)
    cy = (ch - zh) / 2.0 + py * ((ch - zh) / 2.0)
    cx = max(0, min(cw - zw, int(cx)))
    cy = max(0, min(ch - zh, int(cy)))
    return cx, cy, cx + zw, cy + zh

def rotate_and_crop_inner(img: Image.Image, angle_deg: float) -> Image.Image:
    if abs(angle_deg) < 0.05:
        return img
    w, h = img.size
    rad = math.radians(abs(angle_deg))
    sin_a, cos_a = math.sin(rad), math.cos(rad)
    # Точный коэффициент увеличения для вписанного прямоугольника без чёрных углов
    scale = max((w * cos_a + h * sin_a) / w, (w * sin_a + h * cos_a) / h)
    nw, nh = int(w * scale), int(h * scale)
    scaled = img.resize((nw, nh), Image.Resampling.BILINEAR)
    rotated = scaled.rotate(-angle_deg, resample=Image.Resampling.BILINEAR, expand=False)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return rotated.crop((left, top, left + w, top + h))

def process_preview_image(app, raw_img: Image.Image) -> Image.Image:
    img = raw_img.copy()
    w, h = img.size
    aspect = app.aspect_menu.get()
    target_ratio = (16 / 9) if "16:9" in aspect else ((9 / 16) if "9:16" in aspect else (w / h))
    cur_ratio = w / h

    if abs(cur_ratio - target_ratio) > 0.01:
        if cur_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            img = img.crop((0, top, w, top + new_h))

    # Выравнивание горизонта
    angle = app.sl_rot.get()
    if abs(angle) >= 0.05:
        img = rotate_and_crop_inner(img, angle)

    exp = app.sl_exp.get()
    con = app.sl_con.get()
    hi = app.sl_hi.get()
    sh = app.sl_sh.get()
    sat = app.sl_sat.get()
    tmp = app.sl_tmp.get()
    sharp = app.sl_sharp.get()

    if any(abs(v) > 0.01 for v in (exp, con - 1.0, hi, sh, sat - 1.0, tmp)):
        arr = np.asarray(img, dtype=np.float32) / 255.0

        if abs(sh) > 0.01 or abs(hi) > 0.01:
            sh_mask = (1.0 - arr) ** 2
            hi_mask = arr ** 2
            arr = arr + sh * 0.28 * sh_mask * arr * 2.0 + hi * 0.28 * hi_mask * (1.0 - arr) * 2.0
            arr = np.clip(arr, 0.0, 1.0)

        br = exp * 0.22
        if abs(con - 1.0) > 0.01 or abs(br) > 0.001:
            arr = (arr - 0.5) * con + 0.5 + br

        if abs(sat - 1.0) > 0.01:
            luma = arr[:, :, 0:1] * 0.2126 + arr[:, :, 1:2] * 0.7152 + arr[:, :, 2:3] * 0.0722
            arr = luma + (arr - luma) * sat

        if abs(tmp) > 0.01:
            arr[:, :, 0] += tmp * 0.14
            arr[:, :, 2] -= tmp * 0.14

        arr = np.clip(arr * 255.0, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr)

    img.thumbnail((660, 500))
    if sharp > 0.02:
        img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=int(sharp * 110), threshold=2))

    cw, ch = img.size
    app.last_preview_size = (cw, ch)
    if app.zoom_sw.get():
        draw = ImageDraw.Draw(img, "RGBA")
        sx1, sy1, sx2, sy2 = get_zoom_rect(cw, ch, app.sl_zoom_start.get(), app.sl_start_x.get(), app.sl_start_y.get())
        ex1, ey1, ex2, ey2 = get_zoom_rect(cw, ch, app.sl_zoom_end.get(), app.sl_end_x.get(), app.sl_end_y.get())

        scx, scy = (sx1 + sx2) // 2, (sy1 + sy2) // 2
        ecx, ecy = (ex1 + ex2) // 2, (ey1 + ey2) // 2

        draw.line([(scx, scy), (ecx, ecy)], fill=(255, 255, 255, 190), width=2)
        draw.rectangle([sx1, sy1, sx2 - 1, sy2 - 1], outline=(52, 211, 153, 255), width=2)
        draw.ellipse([scx - 5, scy - 5, scx + 5, scy + 5], fill=(52, 211, 153, 255))
        draw.text((sx1 + 6, sy1 + 4), "СТАРТ", fill=(52, 211, 153, 255))

        draw.rectangle([ex1, ey1, ex2 - 1, ey2 - 1], outline=(251, 146, 60, 255), width=2)
        draw.ellipse([ecx - 5, ecy - 5, ecx + 5, ecy + 5], fill=(251, 146, 60, 255))
        draw.text((ex1 + 6, ey2 - 16), "ФИНИШ", fill=(251, 146, 60, 255))

    return img
