import re
import threading
from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image
import imageio_ffmpeg
from lr_ui import build_lr_interface
from lr_render import execute_render
from lr_raw import RAW_EXTS, load_any_image
from lr_preview import process_preview_image
from lr_mouse import setup_mouse_drag

ctk.set_appearance_mode("dark")

def natural_sort_key(path: Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', path.name)]

class TimelapseStudioApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Timelapse Studio Pro")
        self.geometry("1280x800")
        self.minsize(1120, 700)
        self.ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        self.desktop_path = Path.home() / "Desktop"
        self.save_dir = self.desktop_path
        self.photo_exts = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'} | RAW_EXTS
        self.image_files = []
        self.current_idx = 0
        self.thumb_cache = {}
        self.secret_clicks = 0
        self.last_preview_size = (660, 500)
        self.drag_target = None
        self.is_playing = False
        self.is_rendering = False
        self.cancel_requested = False
        self.current_proc = None
        build_lr_interface(self)
        setup_mouse_drag(self)

    def reset_horizon(self):
        self.sl_rot.set(0.0)
        self.lbl_rot.configure(text="+0.0°")
        self.refresh_preview()

    def reset_zoom(self):
        for sl, lbl, val, txt in [
            (self.sl_zoom_start, self.lbl_zoom_start, 1.0, "1.00x"),
            (self.sl_start_x, self.lbl_start_x, 0, "+0%"),
            (self.sl_start_y, self.lbl_start_y, 0, "+0%"),
            (self.sl_zoom_end, self.lbl_zoom_end, 1.25, "1.25x"),
            (self.sl_end_x, self.lbl_end_x, 0, "+0%"),
            (self.sl_end_y, self.lbl_end_y, 0, "+0%")
        ]:
            sl.set(val)
            lbl.configure(text=txt)
        self.refresh_preview()

    def on_secret_click(self):
        self.secret_clicks += 1
        self.secret_btn.configure(fg_color="#10b981", text_color="#ffffff")
        self.after(120, lambda: self.secret_btn.configure(fg_color="#23272e", text_color="#4b5563"))
        if self.secret_clicks >= 15:
            self.secret_clicks = 0
            overlay = ctk.CTkFrame(self, fg_color="#090a0d", corner_radius=0)
            overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            ctk.CTkLabel(overlay, text="МОЛОДЕЦ", font=("Bahnschrift", 92, "bold"), text_color="#34d399").place(relx=0.5, rely=0.5, anchor="center")
            self.after(2000, overlay.destroy)

    def reset_color(self):
        for sl, val in [(self.sl_exp, 0.0), (self.sl_con, 1.0), (self.sl_hi, 0.0), (self.sl_sh, 0.0), (self.sl_sat, 1.0), (self.sl_tmp, 0.0), (self.sl_sharp, 0.0)]:
            sl.set(val)
        self.refresh_preview()

    def select_save_dir(self):
        d = filedialog.askdirectory(initialdir=str(self.save_dir), title="Куда сохранять видео")
        if d:
            self.save_dir = Path(d)
            name = "Рабочий стол" if self.save_dir == self.desktop_path else self.save_dir.name
            self.save_dir_lbl.configure(text=name, text_color="#e4e4e7")

    def update_stats(self):
        n = len(self.image_files)
        if n == 0:
            self.count_lbl.configure(text="0 кадров  |  0.0 сек  |  ~0 МБ")
            return
        try:
            fps = float(self.fps_entry.get().replace(",", "."))
            if fps <= 0:
                fps = 24.0
        except ValueError:
            fps = 24.0
        dur = n / fps
        res = self.res_menu.get()
        mb_per_sec = 4.5 if "4K" in res else (2.2 if "2K" in res else (1.2 if "1080p" in res else 0.6))
        self.count_lbl.configure(text=f"{n} кадров  |  {dur:.1f} сек  |  ~{max(1, int(dur * mb_per_sec))} МБ")

    def select_folder(self):
        folder_str = filedialog.askdirectory(initialdir=str(self.desktop_path), title="Выберите папку с фото или RAW")
        if not folder_str:
            return
        folder = Path(folder_str)
        files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in self.photo_exts]
        files.sort(key=natural_sort_key)
        if not files:
            self.status_lbl.configure(text="В папке нет подходящих фото или RAW!", text_color="#facc15")
            return
        self.is_playing = False
        self.btn_play.configure(text="Play")
        self.image_files = files
        self.thumb_cache.clear()
        self.folder_lbl.configure(text=str(folder), text_color="#e4e4e7")
        self.update_stats()
        max_i = max(1, len(files) - 1)
        self.frame_slider.configure(from_=0, to=max_i, number_of_steps=max_i)
        self.frame_slider.set(0)
        self.show_frame(0)

    def refresh_preview(self):
        if self.image_files:
            self.show_frame(self.current_idx)

    def get_cached_thumb(self, idx: int) -> Image.Image:
        if idx in self.thumb_cache:
            return self.thumb_cache[idx]
        item = next(iter(self.image_files[idx:idx + 1]))
        raw = load_any_image(item)
        if raw.format == "JPEG":
            raw.draft("RGB", (680, 520))
        raw = raw.convert("RGB")
        raw.thumbnail((680, 520))
        if len(self.thumb_cache) > 300:
            self.thumb_cache.clear()
        self.thumb_cache[idx] = raw
        return raw

    def show_frame(self, idx: int):
        if not self.image_files:
            return
        idx = max(0, min(idx, len(self.image_files) - 1))
        self.current_idx = idx
        try:
            processed = process_preview_image(self, self.get_cached_thumb(idx))
            c_img = ctk.CTkImage(light_image=processed, dark_image=processed, size=processed.size)
            self.preview_box.configure(image=c_img, text="")
            self.frame_info.configure(text=f"{idx + 1} / {len(self.image_files)}")
        except Exception:
            self.preview_box.configure(image=None, text="Ошибка чтения кадра")

    def on_slider_move(self, val):
        if self.image_files:
            self.show_frame(int(val))

    def toggle_play(self):
        if not self.image_files:
            return
        self.is_playing = not self.is_playing
        self.btn_play.configure(text="Пауза" if self.is_playing else "Play")
        if self.is_playing:
            self._play_loop()

    def _play_loop(self):
        if not self.is_playing or not self.image_files:
            return
        nxt = (self.current_idx + 1) % len(self.image_files)
        self.frame_slider.set(nxt)
        self.show_frame(nxt)
        self.after(45, self._play_loop)

    def get_output_path(self, is_test: bool = False) -> Path:
        prefix = "timelapse_test" if is_test else "timelapse"
        c = 1
        while True:
            p = self.save_dir / f"{prefix} {c}.mp4"
            if not p.exists():
                return p
            c += 1

    def get_target_dimensions(self):
        aspect, res = self.aspect_menu.get(), self.res_menu.get()
        is_vert, is_horiz = "9:16" in aspect, "16:9" in aspect
        if "4K" in res:
            bw, bh = (2160, 3840) if is_vert else (3840, 2160)
        elif "2K" in res:
            bw, bh = (1440, 2560) if is_vert else (2560, 1440)
        elif "1080p" in res:
            bw, bh = (1080, 1920) if is_vert else (1920, 1080)
        elif "720p" in res:
            bw, bh = (720, 1280) if is_vert else (1280, 720)
        elif "480p" in res:
            bw, bh = (480, 854) if is_vert else (854, 480)
        else:
            with load_any_image(next(iter(self.image_files))) as im:
                iw, ih = im.size
            bw, bh = (iw, int(iw * 9 / 16)) if is_horiz else ((int(ih * 9 / 16), ih) if is_vert else (iw, ih))
        return (bw // 2) * 2, (bh // 2) * 2

    def start_render(self, is_test: bool = False):
        if self.is_rendering or not self.image_files:
            if not self.image_files:
                self.status_lbl.configure(text="Сначала импортируй папку с фото!", text_color="#facc15")
            return
        try:
            fps = float(self.fps_entry.get().replace(",", "."))
            if not (0 < fps <= 240):
                raise ValueError
        except ValueError:
            self.status_lbl.configure(text="Укажи FPS от 1 до 240!", text_color="#f87171")
            return
        self.is_playing = False
        self.btn_play.configure(text="Play")
        self.is_rendering = True
        self.cancel_requested = False
        self.btn_render.configure(state="disabled")
        self.btn_test.configure(state="disabled")
        self.btn_cancel.pack(side="right", padx=(6, 0))
        self.progress.set(0)
        self.status_lbl.configure(text="Подготовка кадров... (0%)", text_color="#38bdf8")
        threading.Thread(target=execute_render, args=(self, fps, is_test), daemon=True).start()

    def cancel_render(self):
        if self.is_rendering:
            self.cancel_requested = True
            self.status_lbl.configure(text="Отмена операции...", text_color="#facc15")
            if self.current_proc:
                try:
                    self.current_proc.terminate()
                except Exception:
                    pass

    def update_progress(self, val: float, txt: str):
        self.after(0, lambda: (self.progress.set(val), self.status_lbl.configure(text=txt, text_color="#38bdf8")))

    def finish_render(self, ok: bool, msg: str):
        self.is_rendering = False
        self.btn_cancel.pack_forget()
        self.progress.set(1 if ok else 0)
        self.btn_render.configure(state="normal")
        self.btn_test.configure(state="normal")
        self.status_lbl.configure(text=msg, text_color="#34d399" if ok else "#f87171")

if __name__ == "__main__":
    app = TimelapseStudioApp()
    app.mainloop()
