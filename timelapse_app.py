import re
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
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
    # Сортируем полный относительный путь: сначала папки, затем файлы внутри них.
    return [(0, int(t)) if t.isdigit() else (1, t.lower()) for t in re.split(r'(\d+)', path.as_posix())]

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
        self._preview_resize_job = None
        self._preview_update_job = None
        self._last_preview_target = None
        self.drag_target = None
        self.is_playing = False
        self.is_rendering = False
        self.cancel_requested = False
        self.current_proc = None
        build_lr_interface(self)
        setup_mouse_drag(self)
        # Отслеживаем размер панели, а не самой картинки: размер изображения не
        # должен менять минимальную ширину колонок и запускать цикл перерисовки.
        self.preview_area.bind("<Configure>", self._on_preview_resize)

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
        for sl, val in [(self.sl_exp, 0.0), (self.sl_con, 1.0), (self.sl_hi, 0.0), (self.sl_sh, 0.0), (self.sl_sat, 1.0), (self.sl_tmp, 0.0), (self.sl_tint, 0.0), (self.sl_sharp, 0.0)]:
            sl.set(val)
        self.ent_tmp.delete(0, "end")
        self.ent_tmp.insert(0, "+0 K")
        self.ent_tint.delete(0, "end")
        self.ent_tint.insert(0, "+0 ")
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
        # tkinter.askdirectory не умеет выбирать несколько папок за один раз,
        # поэтому предлагаем добавлять папки по очереди.
        first = filedialog.askdirectory(
            initialdir=str(self.desktop_path),
            title="Выберите первую папку с фото или RAW"
        )
        if not first:
            return

        folders = [Path(first)]
        while messagebox.askyesno(
            "Добавить папку",
            "Добавить ещё одну папку с фотографиями?",
            parent=self
        ):
            next_folder = filedialog.askdirectory(
                initialdir=str(folders[-1]),
                title="Выберите следующую папку"
            )
            if not next_folder:
                break
            candidate = Path(next_folder)
            # Не добавляем один и тот же каталог повторно.
            try:
                candidate_key = str(candidate.resolve()).lower()
                existing = {str(item.resolve()).lower() for item in folders}
            except Exception:
                candidate_key = str(candidate).lower()
                existing = {str(item).lower() for item in folders}
            if candidate_key not in existing:
                folders.append(candidate)

        include_subfolders = messagebox.askyesno(
            "Импорт подпапок",
            "Искать фотографии и во вложенных подпапках?\n\n"
            "Да — искать во всех подпапках\n"
            "Нет — только непосредственно в выбранных папках",
            parent=self
        )
        ignore_raw = messagebox.askyesno(
            "Импорт RAW",
            "Игнорировать RAW-файлы?\n\n"
            "Да — загрузить только готовые изображения (JPEG, PNG, TIFF и т.д.)\n"
            "Нет — загрузить готовые изображения и RAW-файлы",
            parent=self
        )

        self.status_lbl.configure(
            text=f"Поиск изображений в {len(folders)} папках...",
            text_color="#38bdf8"
        )
        self.update_idletasks()

        found = {}
        for folder in folders:
            candidates = folder.rglob("*") if include_subfolders else folder.iterdir()
            try:
                for item in candidates:
                    try:
                        if not item.is_file():
                            continue
                        ext = item.suffix.lower()
                        if ext not in self.photo_exts:
                            continue
                        if ignore_raw and ext in RAW_EXTS:
                            continue
                        # resolve() предотвращает дубли, если выбраны вложенные папки.
                        key = str(item.resolve()).lower()
                        found[key] = item
                    except (OSError, PermissionError):
                        continue
            except (OSError, PermissionError):
                continue

        files = list(found.values())
        files.sort(key=natural_sort_key)

        if not files:
            self.status_lbl.configure(
                text="В выбранных папках нет подходящих изображений!",
                text_color="#facc15"
            )
            return

        self.is_playing = False
        self.btn_play.configure(text="Play")
        self.image_files = files
        self.thumb_cache.clear()
        if len(folders) == 1:
            folder_text = str(folders[0])
        else:
            folder_text = f"{len(folders)} папки: " + ", ".join(f.name for f in folders)
        self.folder_lbl.configure(text=folder_text, text_color="#e4e4e4")
        self.update_stats()
        max_i = max(1, len(files) - 1)
        self.frame_slider.configure(from_=0, to=max_i, number_of_steps=max_i)
        self.frame_slider.set(0)
        self.show_frame(0)
        self.status_lbl.configure(
            text=f"Загружено кадров: {len(files)}",
            text_color="#34d399"
        )

    def refresh_preview(self):
        # Объединяем частые события от ползунков: показываем только последнее
        # значение после короткой паузы, вместо пересчёта на каждое микродвижение.
        if not self.image_files:
            return
        if self._preview_update_job is not None:
            try:
                self.after_cancel(self._preview_update_job)
            except Exception:
                pass
        self._preview_update_job = self.after(70, self._run_scheduled_preview)

    def _run_scheduled_preview(self):
        self._preview_update_job = None
        if self.image_files:
            self.show_frame(self.current_idx)

    def _get_preview_target_size(self):
        # Размер именно внутренней области слева, а не всего окна приложения.
        width = self.preview_box.winfo_width() - 20
        height = self.preview_box.winfo_height() - 20
        if width < 100 or height < 100:
            return (660, 500)
        return (width, height)

    def _on_preview_resize(self, event=None):
        # Configure может приходить сериями во время разворачивания окна.
        # Объединяем события и пересчитываем изображение только после паузы.
        size = self._get_preview_target_size()
        if size == self._last_preview_target:
            return
        self._last_preview_target = size
        if self._preview_resize_job is not None:
            try:
                self.after_cancel(self._preview_resize_job)
            except Exception:
                pass
        if self.image_files:
            self._preview_resize_job = self.after(250, self._refresh_preview_for_resize)

    def _refresh_preview_for_resize(self):
        self._preview_resize_job = None
        if self.image_files:
            self.show_frame(self.current_idx)

    def get_cached_thumb(self, idx: int) -> Image.Image:
        if idx in self.thumb_cache:
            return self.thumb_cache[idx]
        item = self.image_files[idx]
        raw = load_any_image(item).convert("RGB")
        # Храним достаточно крупный исходник для больших окон, но не полный RAW.
        raw.thumbnail((2560, 2560), Image.Resampling.LANCZOS)
        if len(self.thumb_cache) >= 8:
            self.thumb_cache.pop(next(iter(self.thumb_cache)))
        self.thumb_cache[idx] = raw.copy()
        return raw

    def show_frame(self, idx: int):
        if not self.image_files:
            return
        idx = max(0, min(idx, len(self.image_files) - 1))
        self.current_idx = idx
        try:
            target_size = self._get_preview_target_size()
            processed = process_preview_image(self, self.get_cached_thumb(idx), max_size=target_size)
            c_img = ctk.CTkImage(light_image=processed, dark_image=processed, size=processed.size)
            self.preview_box.configure(image=c_img, text="")
            self._main_preview_image = c_img
            self.frame_info.configure(text=f"{idx + 1} / {len(self.image_files)}")
        except Exception as exc:
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

    def select_audio_file(self):
        path = filedialog.askopenfilename(
            title="Выберите аудиофайл",
            filetypes=[("Аудио", "*.mp3 *.wav *.m4a *.aac *.flac *.ogg"), ("Все файлы", "*.*")]
        )
        if path:
            self.audio_path = Path(path)
            self.audio_silence_sw.deselect()
            self.audio_file_lbl.configure(text=self.audio_path.name, text_color="#e4e4e7")

    def clear_audio_file(self):
        self.audio_path = None
        self.audio_file_lbl.configure(text="Аудио не выбрано", text_color="#a1a1aa")

    def on_audio_silence_toggle(self):
        # Пустая дорожка и выбранная музыка взаимоисключаются.
        if self.audio_silence_sw.get() and getattr(self, "audio_path", None):
            self.clear_audio_file()

    def _collect_audio_settings(self):
        def number(widget, default, minimum=0.0):
            try:
                value = float(widget.get().replace(",", "."))
                return max(minimum, value)
            except Exception:
                return default
        return {
            "path": str(self.audio_path) if getattr(self, "audio_path", None) else None,
            "trim_start": number(self.audio_trim_start, 0.0),
            "trim_end": number(self.audio_trim_end, 0.0),
            "delay": number(self.audio_delay, 0.0),
            "volume": number(self.audio_volume, 100.0) / 100.0,
            "silence": bool(self.audio_silence_sw.get()),
        }

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
        self.audio_settings = self._collect_audio_settings()
        self.lens_enabled = bool(self.lens_sw.get())
        if self.audio_settings["path"] and self.audio_settings["trim_end"] and self.audio_settings["trim_end"] <= self.audio_settings["trim_start"]:
            self.status_lbl.configure(text="Конец обрезки аудио должен быть больше начала!", text_color="#f87171")
            return
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
        self.status_lbl.configure(text=msg[:220], text_color="#34d399" if ok else "#f87171")

if __name__ == "__main__":
    app = TimelapseStudioApp()
    app.mainloop()
