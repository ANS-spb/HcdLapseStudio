import customtkinter as ctk
from lr_widgets import add_help_badge, make_lr_slider

def build_right_panels(app, right_scroll):
    pad_x = 20
    p_base = ctk.CTkFrame(right_scroll, fg_color="#23252a", border_width=1, border_color="#2e383c", corner_radius=5)
    p_base.pack(fill="x", padx=pad_x, pady=(8, 5))
    h1 = ctk.CTkFrame(p_base, fg_color="#2a2f36", corner_radius=4, height=26)
    h1.pack(fill="x", padx=2, pady=2)
    ctk.CTkLabel(h1, text="  Формат кадра и горизонт", font=("Segoe UI", 11, "bold"), text_color="#f4f4f5").pack(side="left")
    ctk.CTkButton(h1, text="Сброс", width=48, height=20, font=("Segoe UI", 10), fg_color="#3b434d", command=app.reset_horizon).pack(side="right", padx=4)
    add_help_badge(h1, "Выбор пропорций, разрешения (до 4K), FPS и точное выравнивание заваленного горизонта.")

    g1 = ctk.CTkFrame(p_base, fg_color="transparent")
    g1.pack(fill="x", padx=8, pady=6)
    ctk.CTkLabel(g1, text="Пропорции:", font=("Segoe UI", 11)).grid(row=0, column=0, sticky="w", padx=2)
    app.aspect_menu = ctk.CTkOptionMenu(g1, width=120, height=26, fg_color="#2f353d", button_color="#3b434d", values=["Исходный", "16:9 (Горизонт)", "9:16 (Вертикаль)"], command=lambda _: app.refresh_preview())
    app.aspect_menu.set("Исходный")
    app.aspect_menu.grid(row=1, column=0, padx=2, pady=(2, 6), sticky="ew")

    ctk.CTkLabel(g1, text="Разрешение:", font=("Segoe UI", 11)).grid(row=0, column=1, sticky="w", padx=4)
    app.res_menu = ctk.CTkOptionMenu(g1, width=120, height=26, fg_color="#2f353d", button_color="#3b434d", values=["Нативное", "4K (2160p)", "2K (1440p)", "1080p (FHD)", "720p (HD)", "480p (SD)"], command=lambda _: app.update_stats())
    app.res_menu.set("1080p (FHD)")
    app.res_menu.grid(row=1, column=1, padx=4, pady=(2, 6), sticky="ew")

    ctk.CTkLabel(g1, text="FPS:", font=("Segoe UI", 11)).grid(row=0, column=2, sticky="w", padx=2)
    app.fps_entry = ctk.CTkEntry(g1, width=50, height=26, fg_color="#16181c", border_color="#3b434d")
    app.fps_entry.insert(0, "24")
    app.fps_entry.bind("<KeyRelease>", lambda _: app.update_stats())
    app.fps_entry.grid(row=1, column=2, padx=2, pady=(2, 6))
    g1.grid_columnconfigure((0, 1), weight=1)

    app.sl_rot, app.lbl_rot = make_lr_slider(
        p_base, "Выравнивание горизонта", -10.0, 10.0, 0.0, 200, "{:+.1f}°",
        lambda _: app.refresh_preview(),
        "Поворачивает кадр от -10.0° до +10.0° с шагом 0.1° и автоматически подрезает края без чёрных углов."
    )

    p_col = ctk.CTkFrame(right_scroll, fg_color="#23252a", border_width=1, border_color="#2e383c", corner_radius=5)
    p_col.pack(fill="x", padx=pad_x, pady=5)
    h2 = ctk.CTkFrame(p_col, fg_color="#2a2f36", corner_radius=4, height=26)
    h2.pack(fill="x", padx=2, pady=2)
    ctk.CTkLabel(h2, text="  Базовая цветокоррекция", font=("Segoe UI", 11, "bold"), text_color="#f4f4f5").pack(side="left")
    ctk.CTkButton(h2, text="Сброс", width=48, height=20, font=("Segoe UI", 10), fg_color="#3b434d", command=app.reset_color).pack(side="right", padx=4)
    add_help_badge(h2, "Быстрая проявка кадров. Все изменения сразу видны в окне предпросмотра слева.")

    app.sl_exp, _ = make_lr_slider(p_col, "Экспозиция", -1.0, 1.0, 0.0, 40, "{:+.2f}", lambda _: app.refresh_preview(), "Осветляет или затемняет весь кадр (от -1.0 до +1.0 ступени).")
    app.sl_con, _ = make_lr_slider(p_col, "Контрастность", 0.5, 1.8, 1.0, 26, "{:.2f}", lambda _: app.refresh_preview(), "Усиливает разницу между ночным небом и яркими всполохами.")
    app.sl_hi, _ = make_lr_slider(p_col, "Света (Highlights)", -1.0, 1.0, 0.0, 40, "{:+.2f}", lambda _: app.refresh_preview(), "Влево — приглушает слишком яркие участки (центр сияния, фонари), вправо — усиливает.")
    app.sl_sh, _ = make_lr_slider(p_col, "Тени (Shadows)", -1.0, 1.0, 0.0, 40, "{:+.2f}", lambda _: app.refresh_preview(), "Вправо — вытягивает детали из тёмной земли и переднего плана, влево — делает тени глубже.")
    app.sl_sat, _ = make_lr_slider(p_col, "Насыщенность", 0.0, 2.0, 1.0, 40, "{:.2f}", lambda _: app.refresh_preview(), "Усиливает изумрудные и фиолетовые оттенки сияния.")
    app.sl_tmp, _ = make_lr_slider(p_col, "Температура", -1.0, 1.0, 0.0, 40, "{:+.2f}", lambda _: app.refresh_preview(), "Баланс белого: влево — глубокий ночной синий, вправо — теплее.")
    app.sl_sharp, _ = make_lr_slider(p_col, "Резкость", 0.0, 2.0, 0.0, 40, "{:.2f}", lambda _: app.refresh_preview(), "Повышает микроконтраст и чёткость звёзд (0.00 — выключено).")

    p_zoom = ctk.CTkFrame(right_scroll, fg_color="#23252a", border_width=1, border_color="#2e383c", corner_radius=5)
    p_zoom.pack(fill="x", padx=pad_x, pady=5)
    h3 = ctk.CTkFrame(p_zoom, fg_color="#2a2f36", corner_radius=4, height=26)
    h3.pack(fill="x", padx=2, pady=2)
    app.zoom_sw = ctk.CTkSwitch(h3, text="Плавный зум и панорама", font=("Segoe UI", 11, "bold"), progress_color="#10b981", command=app.refresh_preview)
    app.zoom_sw.pack(side="left", padx=6)
    ctk.CTkButton(h3, text="Сброс", width=48, height=20, font=("Segoe UI", 10), fg_color="#3b434d", command=app.reset_zoom).pack(side="right", padx=4)
    add_help_badge(h3, "При включении на фото появляются зелёная рамка (Старт) и оранжевая рамка (Финиш). Их можно двигать ползунками или перетаскивать мышкой прямо на картинке!")

    app.sl_zoom_start, app.lbl_zoom_start = make_lr_slider(p_zoom, "Начальный зум (Старт)", 1.0, 1.6, 1.0, 30, "{:.2f}x", lambda _: app.refresh_preview(), "Приближение в самом начале ролика (зелёная рамка).")
    app.sl_start_x, app.lbl_start_x = make_lr_slider(p_zoom, "Старт сдвиг X", -100, 100, 0, 40, "{:+.0f}%", lambda _: app.refresh_preview(), "Положение зелёной рамки по горизонтали.")
    app.sl_start_y, app.lbl_start_y = make_lr_slider(p_zoom, "Старт сдвиг Y", -100, 100, 0, 40, "{:+.0f}%", lambda _: app.refresh_preview(), "Положение зелёной рамки по вертикали.")

    app.sl_zoom_end, app.lbl_zoom_end = make_lr_slider(p_zoom, "Конечный зум (Финиш)", 1.0, 1.6, 1.25, 30, "{:.2f}x", lambda _: app.refresh_preview(), "Приближение в самом конце ролика (оранжевая рамка).")
    app.sl_end_x, app.lbl_end_x = make_lr_slider(p_zoom, "Финиш сдвиг X", -100, 100, 0, 40, "{:+.0f}%", lambda _: app.refresh_preview(), "Положение оранжевой рамки по горизонтали.")
    app.sl_end_y, app.lbl_end_y = make_lr_slider(p_zoom, "Финиш сдвиг Y", -100, 100, 0, 40, "{:+.0f}%", lambda _: app.refresh_preview(), "Положение оранжевой рамки по вертикали.")
