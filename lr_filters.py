import math
from lr_white_balance import white_balance_gains

def build_ffmpeg_filters(app, tw: int, th: int, fps: float, total_frames: int):
    angle = app.sl_rot.get()
    exp, con, sat = app.sl_exp.get(), app.sl_con.get(), app.sl_sat.get()
    tmp, tint = app.sl_tmp.get(), app.sl_tint.get()
    hi, sh, sharp = app.sl_hi.get(), app.sl_sh.get(), app.sl_sharp.get()

    use_zoom = bool(app.zoom_sw.get())
    z_start, z_end = app.sl_zoom_start.get(), app.sl_zoom_end.get()
    sx, sy = app.sl_start_x.get() / 100.0, app.sl_start_y.get() / 100.0
    ex, ey = app.sl_end_x.get() / 100.0, app.sl_end_y.get() / 100.0

    use_dn, dn_lvl = bool(app.denoise_sw.get()), int(app.sl_denoise.get())
    use_df, df_size = bool(app.deflicker_sw.get()), int(app.sl_deflicker.get())

    frame_mode = getattr(app, "frame_mode", "Заполнить кадр")
    if "Вписать" in frame_mode or "Размытый" in frame_mode:
        flts = [f"scale={tw}:{th}"]
    else:
        flts = [
            f"scale={tw}:{th}:force_original_aspect_ratio=increase",
            f"crop={tw}:{th}"
        ]

    if abs(angle) >= 0.05:
        rad = math.radians(abs(angle))
        sin_a, cos_a = math.sin(rad), math.cos(rad)
        sc = max((tw * cos_a + th * sin_a) / tw, (tw * sin_a + th * cos_a) / th)
        sw_rot = (int(tw * sc) // 2) * 2
        sh_rot = (int(th * sc) // 2) * 2
        rot_rad = math.radians(angle)
        flts.append(f"scale={sw_rot}:{sh_rot}")
        flts.append(f"rotate={rot_rad:.6f}:ow={tw}:oh={th}:c=black")

    if abs(sh) > 0.01 or abs(hi) > 0.01:
        p25 = max(0.02, min(0.48, 0.25 + sh * 0.08))
        p75 = max(0.52, min(0.98, 0.75 + hi * 0.08))
        flts.append(f"curves=all='0/0 0.25/{p25:.3f} 0.75/{p75:.3f} 1/1'")

    if abs(exp) > 0.01 or abs(con - 1.0) > 0.01 or abs(sat - 1.0) > 0.01:
        br = exp * 0.22
        flts.append(f"eq=brightness={br:.3f}:contrast={con:.3f}:saturation={sat:.3f}")
    if abs(tmp) > 0.5 or abs(tint) > 0.5:
        r_gain, g_gain, b_gain = white_balance_gains(tmp, tint)
        flts.append(f"colorchannelmixer=rr={r_gain:.6f}:gg={g_gain:.6f}:bb={b_gain:.6f}")

    if sharp > 0.02:
        flts.append(f"unsharp=5:5:{sharp * 0.85:.2f}:5:5:0.0")

    if use_dn:
        flts.append(f"hqdn3d={dn_lvl * 1.4:.1f}:{dn_lvl * 1.1:.1f}:4.0:3.0")

    if use_df:
        flts.append(f"deflicker=size={df_size}:mode=pm")

    if use_zoom and total_frames > 1 and (z_start > 1.005 or z_end > 1.005):
        denom = max(1, total_frames - 1)
        t_expr = f"(on/{denom})"
        z_expr = f"{z_start:.4f}+({z_end - z_start:.4f})*{t_expr}"
        pan_x_expr = f"({sx:.4f}+({ex - sx:.4f})*{t_expr})"
        pan_y_expr = f"({sy:.4f}+({ey - sy:.4f})*{t_expr})"
        x_expr = f"(iw-iw/zoom)/2+{pan_x_expr}*(iw-iw/zoom)/2"
        y_expr = f"(ih-ih/zoom)/2+{pan_y_expr}*(ih-ih/zoom)/2"
        flts.append(f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d=1:s={tw}x{th}:fps={fps}")

    return flts
