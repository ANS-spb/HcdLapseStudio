import os
import time
import subprocess
import tempfile
from pathlib import Path
from lr_raw import RAW_EXTS, prepare_raw_frames
from lr_filters import build_ffmpeg_filters

def format_eta(seconds: float) -> str:
    if seconds < 0 or seconds > 36000:
        return "расчет..."
    s = int(seconds)
    if s < 60:
        return f"~{s} сек"
    m, sec = divmod(s, 60)
    return f"~{m} мин {sec} сек"

def run_ffmpeg_tracked(app, cmd, expected_frames: int, p_start: float, p_end: float, stage_text: str):
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    exe, *args = cmd
    full_cmd = [exe, "-progress", "pipe:1", "-nostats"] + args
    proc = subprocess.Popen(
        full_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        universal_newlines=True, encoding="utf-8", errors="ignore", bufsize=1, creationflags=flags
    )
    app.current_proc = proc
    err_lines = []
    start_t = time.time()

    for line in proc.stdout:
        if app.cancel_requested:
            proc.terminate()
            raise RuntimeError("Рендер отменен пользователем")
        clean = line.strip()
        if clean:
            err_lines.append(clean)
        if clean.startswith("frame="):
            try:
                _, val_str = clean.split("=", 1)
                cur_f = int(val_str.strip())
                if expected_frames > 0 and cur_f > 0:
                    ratio = min(1.0, cur_f / expected_frames)
                    val = p_start + (p_end - p_start) * ratio
                    pct = int(val * 100)
                    elapsed = time.time() - start_t
                    if cur_f >= 3 and elapsed > 0.5:
                        rem_sec = (expected_frames - cur_f) / max(0.1, cur_f / elapsed)
                        eta_str = f" | осталось {format_eta(rem_sec)}"
                    else:
                        eta_str = " | расчет времени..."
                    app.update_progress(val, f"{stage_text}: {pct}%{eta_str}")
            except ValueError:
                pass

    proc.wait()
    app.current_proc = None
    if app.cancel_requested:
        raise RuntimeError("Рендер отменен пользователем")
    if proc.returncode != 0:
        raise RuntimeError(err_lines.pop() if err_lines else "Ошибка FFmpeg")

def execute_render(app, fps: float, is_test: bool = False):
    out_file = app.get_output_path(is_test=is_test)
    try:
        tw, th = app.get_target_dimensions()
        raw_list = list(app.image_files)[:max(10, int(fps * 3))] if is_test else list(app.image_files)
        raw_share = 0.45 if any(p.suffix.lower() in RAW_EXTS for p in raw_list) else 0.0

        use_stab, stab_lvl = bool(app.stab_sw.get()), int(app.sl_stab.get())
        use_interp, interp_lvl = bool(app.interp_sw.get()), int(app.sl_interp.get())

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_p = Path(tmpdir)
            frames_to_use = prepare_raw_frames(app, raw_list, tmp_p, raw_share, format_eta)
            total_frames = len(frames_to_use)

            lst = tmp_p / "frames.txt"
            dur = 1.0 / fps
            last_img = None
            with open(lst, "w", encoding="utf-8") as f:
                for img in frames_to_use:
                    sp = str(img.resolve()).replace("\\", "/").replace("'", "'\\''")
                    f.write(f"file '{sp}'\nduration {dur:.6f}\n")
                    last_img = sp
                if last_img:
                    f.write(f"file '{last_img}'\n")

            base_flts = build_ffmpeg_filters(app, tw, th, fps, total_frames)
            base_in = [app.ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", str(lst)]
            src_vid = None
            trf = tmp_p / "transforms.trf"
            rem_share = 1.0 - raw_share

            if use_stab:
                draft = tmp_p / "draft.mp4"
                p1, p2 = raw_share + rem_share * 0.35, raw_share + rem_share * 0.55
                run_ffmpeg_tracked(app, base_in + ["-vf", ",".join(base_flts + ["format=yuv420p"]), "-c:v", "libx264", "-crf", "15", "-preset", "fast", "-r", str(fps), str(draft)], total_frames, raw_share, p1, "Подготовка кадров")
                trf_esc = str(trf).replace("\\", "/").replace(":", "\\:")
                run_ffmpeg_tracked(app, [app.ffmpeg_exe, "-y", "-i", str(draft), "-vf", f"vidstabdetect=shakiness={stab_lvl}:accuracy=15:result='{trf_esc}'", "-f", "null", "-"], total_frames, p1, p2, "Анализ стабилизации")
                src_vid = draft

            final_flts = []
            if use_stab and src_vid:
                trf_esc = str(trf).replace("\\", "/").replace(":", "\\:")
                final_flts.append(f"vidstabtransform=input='{trf_esc}':smoothing={stab_lvl * 3}:zoom=1:optzoom=1")
            else:
                final_flts.extend(base_flts)

            out_frames = total_frames * 2 if (use_interp and interp_lvl >= 4) else total_frames
            if use_interp:
                t_fps = fps * 2 if interp_lvl >= 4 else fps
                if interp_lvl <= 3:
                    final_flts.append(f"minterpolate=fps={t_fps}:mi_mode=blend")
                else:
                    mb = 16 if interp_lvl <= 7 else 8
                    final_flts.append(f"minterpolate=fps={t_fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1:mb_size={mb}")

            final_flts.append("format=yuv420p")
            vf = ",".join(final_flts)
            p_start = (raw_share + rem_share * 0.55) if use_stab else raw_share
            label = "Тест-рендер" if is_test else "Экспорт видео"
            cmd = ([app.ffmpeg_exe, "-y", "-i", str(src_vid)] if src_vid else base_in) + ["-vf", vf, "-c:v", "libx264", "-crf", "17", "-preset", "medium", str(out_file)]
            run_ffmpeg_tracked(app, cmd, out_frames, p_start, 1.0, label)

        app.after(0, lambda: app.finish_render(True, f"Готово! Сохранено:\n{out_file.name}"))
    except Exception as e:
        if out_file.exists():
            try:
                out_file.unlink()
            except Exception:
                pass
        app.after(0, lambda: app.finish_render(False, str(e)[:110]))
