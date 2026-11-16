import webbrowser
import customtkinter as ctk
from lr_widgets import add_help_badge, make_lr_slider, make_aurora_logo
from lr_panels import build_right_panels

def build_lr_interface(app):
    app.configure(fg_color="#131518")
    app.grid_columnconfigure(0, weight=5)
    app.grid_columnconfigure(1, weight=4)
    app.grid_rowconfigure(2, weight=1)

    top = ctk.CTkFrame(app, height=48, fg_color="#1b1e23", border_width=1, border_color="#28353a", corner_radius=6)
    top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 0))

    make_aurora_logo(top)

    ctk.CTkButton(top, text="Импорт папки", height=30, font=("Segoe UI", 12, "bold"), fg_color="#0284c7", hover_color="#0369a1", command=app.select_folder).pack(side="left", padx=6, pady=8)
    app.folder_lbl = ctk.CTkLabel(top, text="Папка не выбрана", text_color="#9ca3af", font=("Segoe UI", 12))
    app.folder_lbl.pack(side="left", padx=10)

    app.count_lbl = ctk.CTkLabel(top, text="0 кадров  |  0.0 сек  |  ~0 МБ", font=("Segoe UI", 12, "bold"), text_color="#34d399")
    app.count_lbl.pack(side="right", padx=14)

    aurora_line = ctk.CTkFrame(app, height=2, fg_color="#10b981", corner_radius=0)
    aurora_line.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 5))

    left = ctk.CTkFrame(app, fg_color="#191b20", border_width=1, border_color="#28353a", corner_radius=6)
    left.grid(row=2, column=0, sticky="nsew", padx=(10, 5), pady=4)
    left.grid_rowconfigure(0, weight=1)
    left.grid_columnconfigure(0, weight=1)
    app.preview_box = ctk.CTkLabel(left, text="Нажмите «Импорт папки» сверху,\nчтобы загрузить серию снимков", fg_color="#0f1115", corner_radius=4, font=("Segoe UI", 13), text_color="#6b7280")
    app.preview_box.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 6))

    ctrl = ctk.CTkFrame(left, fg_color="#22252b", height=42, corner_radius=4)
    ctrl.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
    app.btn_play = ctk.CTkButton(ctrl, text="Play", width=75, height=28, fg_color="#059669", hover_color="#047857", font=("Segoe UI", 12, "bold"), command=app.toggle_play)
    app.btn_play.pack(side="left", padx=(8, 6), pady=6)

    app.frame_slider = ctk.CTkSlider(ctrl, from_=0, to=1, fg_color="#374151", progress_color="#10b981", button_color="#f4f4f5", command=app.on_slider_move)
    app.frame_slider.set(0)
    app.frame_slider.pack(side="left", fill="x", expand=True, padx=6)
    app.frame_info = ctk.CTkLabel(ctrl, text="0 / 0", width=75, font=("Segoe UI", 11, "bold"), text_color="#d1d5db")
    app.frame_info.pack(side="right", padx=8)

    right_container = ctk.CTkFrame(app, fg_color="#191b20", border_width=1, border_color="#28353a", corner_radius=6)
    right_container.grid(row=2, column=1, sticky="nsew", padx=(5, 10), pady=4)
    right_container.grid_rowconfigure(0, weight=1)
    right_container.grid_columnconfigure(0, weight=1)

    right_scroll = ctk.CTkScrollableFrame(right_container, fg_color="transparent")
    right_scroll.grid(row=0, column=0, sticky="nsew", padx=2, pady=(4, 0))

    build_right_panels(app, right_scroll)

    pad_x = 20
    p_fx = ctk.CTkFrame(right_scroll, fg_color="#23252a", border_width=1, border_color="#2e383c", corner_radius=5)
    p_fx.pack(fill="x", padx=pad_x, pady=(5, 10))
    h4 = ctk.CTkFrame(p_fx, fg_color="#2a2f36", corner_radius=4, height=26)
    h4.pack(fill="x", padx=2, pady=2)
    ctk.CTkLabel(h4, text="  Алгоритмы и чистка", font=("Segoe UI", 11, "bold"), text_color="#f4f4f5").pack(side="left")
    add_help_badge(h4, "Фильтры FFmpeg для ночной съемки: шумодав, дефликер, стабилизация и плавность.")

    dn_row = ctk.CTkFrame(p_fx, fg_color="transparent")
    dn_row.pack(fill="x", padx=10, pady=(6, 0))
    app.denoise_sw = ctk.CTkSwitch(dn_row, text="Ночной шумодав", font=("Segoe UI", 11, "bold"), progress_color="#10b981")
    app.denoise_sw.pack(side="left")
    add_help_badge(dn_row, "Фильтр hqdn3d: очищает цветное зерно на темном ночном небе, сохраняя звезды и резкость сияния.")
    app.sl_denoise, _ = make_lr_slider(p_fx, "Сила шумоподавления", 1, 10, 4, 9, "{}/10", None, "4–6 оптимально для ночного неба. Выше 7 может слегка замылить мелкие звезды.")
    ctk.CTkLabel(p_fx, text="* Внимание: шумодав замедляет скорость рендера!", font=("Segoe UI", 10, "bold"), text_color="#ef4444").pack(anchor="w", padx=12, pady=(0, 4))

    df_row = ctk.CTkFrame(p_fx, fg_color="transparent")
    df_row.pack(fill="x", padx=10, pady=(4, 0))
    app.deflicker_sw = ctk.CTkSwitch(df_row, text="Дефликер (убрать мерцание)", font=("Segoe UI", 11, "bold"), progress_color="#0284c7")
    app.deflicker_sw.pack(side="left")
    add_help_badge(df_row, "Выравнивает скачки яркости между соседними снимками.")
    app.sl_deflicker, _ = make_lr_slider(p_fx, "Окно сглаживания света", 2, 15, 5, 13, "{} к.", None, "Сколько соседних кадров анализируется для выравнивания яркости (5–7 оптимально).")

    st_row = ctk.CTkFrame(p_fx, fg_color="transparent")
    st_row.pack(fill="x", padx=10, pady=(4, 0))
    app.stab_sw = ctk.CTkSwitch(st_row, text="Стабилизация кадров", font=("Segoe UI", 11, "bold"), progress_color="#0284c7")
    app.stab_sw.pack(side="left")
    add_help_badge(st_row, "Двухпроходный анализ vidstab: убирает дрожание штатива от ветра.")
    app.sl_stab, _ = make_lr_slider(p_fx, "Сила стабилизации", 1, 10, 5, 9, "{}/10", None, "Чем выше значение, тем сильнее сглаживается тряска камеры.")

    in_row = ctk.CTkFrame(p_fx, fg_color="transparent")
    in_row.pack(fill="x", padx=10, pady=(4, 0))
    app.interp_sw = ctk.CTkSwitch(in_row, text="Интерполяция кадров", font=("Segoe UI", 11, "bold"), progress_color="#8b5cf6")
    app.interp_sw.pack(side="left")
    add_help_badge(in_row, "Дорисовывает промежуточные кадры для киношной плавности (1–3 легкий блендинг, 4–10 Optical Flow).")
    app.sl_interp, _ = make_lr_slider(p_fx, "Уровень плавности", 1, 10, 4, 9, "{}/10", None, "Значения 4–10 используют тяжелый просчет векторов движения.")
    ctk.CTkLabel(p_fx, text="* Внимание: сильно увеличивает время создания видео!", font=("Segoe UI", 10, "bold"), text_color="#ef4444").pack(anchor="w", padx=12, pady=(0, 8))

    dock = ctk.CTkFrame(right_container, fg_color="#1f2228", border_width=1, border_color="#2e383c", corner_radius=6)
    dock.grid(row=1, column=0, sticky="ew", padx=10, pady=(4, 10))

    save_row = ctk.CTkFrame(dock, fg_color="transparent")
    save_row.pack(fill="x", padx=10, pady=(8, 4))
    ctk.CTkButton(save_row, text="Папка сохранения...", width=130, height=26, font=("Segoe UI", 11, "bold"), fg_color="#2f353d", hover_color="#3b434d", command=app.select_save_dir).pack(side="left")
    app.save_dir_lbl = ctk.CTkLabel(save_row, text="Рабочий стол", font=("Segoe UI", 11), text_color="#9ca3af")
    app.save_dir_lbl.pack(side="left", padx=8)

    act_box = ctk.CTkFrame(dock, fg_color="transparent")
    act_box.pack(fill="x", padx=10, pady=4)
    app.btn_test = ctk.CTkButton(act_box, text="Тест (3 сек)", width=95, height=40, font=("Segoe UI", 12, "bold"), fg_color="#7c3aed", hover_color="#6d28d9", command=lambda: app.start_render(is_test=True))
    app.btn_test.pack(side="left", padx=(0, 6))

    app.btn_render = ctk.CTkButton(act_box, text="ЭКСПОРТ ТАЙМЛАПСА", height=40, font=("Segoe UI", 13, "bold"), fg_color="#059669", hover_color="#047857", command=lambda: app.start_render(is_test=False))
    app.btn_render.pack(side="left", fill="x", expand=True)

    app.btn_cancel = ctk.CTkButton(act_box, text="Отмена", width=78, height=40, font=("Segoe UI", 12, "bold"), fg_color="#dc2626", hover_color="#b91c1c", command=app.cancel_render)

    app.progress = ctk.CTkProgressBar(dock, progress_color="#10b981", fg_color="#272a30", height=10)
    app.progress.set(0)
    app.progress.pack(fill="x", padx=10, pady=(4, 2))
    app.status_lbl = ctk.CTkLabel(dock, text="Готов к работе", text_color="#34d399", font=("Segoe UI", 11), wraplength=340)
    app.status_lbl.pack(padx=10, pady=(0, 8))

    footer = ctk.CTkFrame(app, height=28, fg_color="#1b1e23", border_width=1, border_color="#28353a", corner_radius=6)
    footer.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))

    app.secret_btn = ctk.CTkButton(
        footer, text="•", width=16, height=16, corner_radius=8,
        fg_color="#23272e", hover_color="#2e343d", text_color="#4b5563",
        font=("Segoe UI", 10), command=app.on_secret_click
    )
    app.secret_btn.pack(side="left", padx=10, pady=4)

    url = "https" + "://t.me/Hcdrkk"
    author_link = ctk.CTkLabel(footer, text="автор: t.me/Hcdrkk", font=("Segoe UI", 12, "bold"), text_color="#d1d5db", cursor="hand2")
    author_link.pack(side="right", padx=16, pady=3)
    author_link.bind("\x3cButton-1\x3e", lambda _: webbrowser.open(url))
    author_link.bind("\x3cEnter\x3e", lambda _: author_link.configure(text_color="#34d399"))
    author_link.bind("\x3cLeave\x3e", lambda _: author_link.configure(text_color="#d1d5db"))
