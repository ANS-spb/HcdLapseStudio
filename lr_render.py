import os
import time
import subprocess
import tempfile
from pathlib import Path
from lr_raw import RAW_EXTS, prepare_raw_frames
from lr_filters import build_ffmpeg_filters
from lr_lens import apply_lensfun
from PIL import Image, ImageOps

def prepare_frame_layout(app, frame_paths, tmp_dir: Path, tw: int, th: int):
    """Prepare contain/blur canvas frames before FFmpeg."""
    mode = getattr(app, "frame_mode", "Заполнить кадр")
    if not ("Вписать" in mode or "Размытый" in mode):
        return frame_paths
    prepared = []
    for idx, src in enumerate(frame_paths):
        if app.cancel_requested:
            raise RuntimeError("Рендер отменен пользователем")
        with Image.open(src) as source:
            img = source.convert("RGB")
            if "Размытый" in mode:
                canvas = ImageOps.fit(img, (tw, th), method=Image.Resampling.LANCZOS)
                canvas = canvas.filter(ImageFilter.GaussianBlur(radius=max(12, int(min(tw, th) * 0.035))))
                foreground = ImageOps.contain(img, (tw, th), method=Image.Resampling.LANCZOS)
                canvas.paste(foreground, ((tw - foreground.width) // 2, (th - foreground.height) // 2))
            else:
                canvas = Image.new("RGB", (tw, th), (0, 0, 0))
                foreground = ImageOps.contain(img, (tw, th), method=Image.Resampling.LANCZOS)
                canvas.paste(foreground, ((tw - foreground.width) // 2, (th - foreground.height) // 2))
            dst = tmp_dir / f"layout_{idx:06d}.jpg"
            canvas.save(dst, "JPEG", quality=95)
            prepared.append(dst)
        if idx % 25 == 0:
            app.update_progress((idx + 1) / max(1, len(frame_paths)) * 0.05,
                                f"Подготовка размещения кадров: {idx + 1}/{len(frame_paths)}")
    return prepared


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
    full_cmd = [exe, "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats"] + args
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
        details = [line for line in err_lines if "error" in line.lower() or "invalid" in line.lower()
                   or "failed" in line.lower() or "no such" in line.lower()]
        useful = details[-3:] if details else err_lines[-3:]
        raise RuntimeError(" | ".join(useful) if useful else "Ошибка FFmpeg")

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
            # Lensfun correction is applied to source frames before FFmpeg filters.
            if getattr(app, "lens_enabled", False):
                corrected_frames = []
                for idx, src in enumerate(frames_to_use):
                    if app.cancel_requested:
                        raise RuntimeError("Рендер отменен пользователем")
                    try:
                        with Image.open(src) as im:
                            fixed, _status = apply_lensfun(im.convert("RGB"), raw_list[idx])
                            if fixed is im:
                                corrected_frames.append(src)
                            else:
                                dst = tmp_p / f"lens_{idx:05d}.jpg"
                                fixed.save(dst, "JPEG", quality=96)
                                corrected_frames.append(dst)
                    except Exception:
                        corrected_frames.append(src)
                    if idx % 10 == 0:
                        app.update_progress(raw_share + (idx + 1) / max(1, len(frames_to_use)) * 0.05,
                                            f"Коррекция объектива: {idx + 1}/{len(frames_to_use)}")
                frames_to_use = corrected_frames

            frames_to_use = prepare_frame_layout(app, frames_to_use, tmp_p, tw, th)
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
            cmd = ([app.ffmpeg_exe, "-y", "-i", str(src_vid)] if src_vid else base_in)
            audio = getattr(app, "audio_settings", {}) or {}
            video_duration = out_frames / (fps * (2 if use_interp and interp_lvl >= 4 else 1))
            if audio.get("silence"):
                cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
                audio_filter = f"atrim=duration={video_duration:.6f}"
                has_audio = True
            elif audio.get("path"):
                cmd += ["-i", audio["path"]]
                start = max(0.0, float(audio.get("trim_start", 0.0)))
                end = max(0.0, float(audio.get("trim_end", 0.0)))
                parts = [f"atrim=start={start:.3f}" + (f":end={end:.3f}" if end > start else ""),
                         "asetpts=PTS-STARTPTS"]
                delay_ms = int(max(0.0, float(audio.get("delay", 0.0))) * 1000)
                if delay_ms:
                    parts.append(f"adelay={delay_ms}|{delay_ms}")
                parts.extend([f"volume={max(0.0, float(audio.get('volume', 1.0))):.3f}", "apad",
                              f"atrim=duration={video_duration:.6f}"])
                audio_filter = ",".join(parts)
                has_audio = True
            else:
                has_audio = False
            cmd += ["-vf", vf]
            if has_audio:
                cmd += ["-map", "0:v:0", "-map", "1:a:0", "-af", audio_filter,
                        "-c:a", "aac", "-b:a", "192k", "-t", f"{video_duration:.6f}"]
            cmd += ["-c:v", "libx264", "-crf", "17", "-preset", "veryfast", str(out_file)]
            run_ffmpeg_tracked(app, cmd, out_frames, p_start, 1.0, label)

        app.after(0, lambda: app.finish_render(True, f"Готово! Сохранено:\n{out_file.name}"))
    except Exception as e:
        if out_file.exists():
            try:
                out_file.unlink()
            except Exception:
                pass
        app.after(0, lambda: app.finish_render(False, str(e)[:110]))
