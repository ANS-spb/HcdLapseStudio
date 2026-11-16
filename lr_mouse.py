from lr_preview import get_zoom_rect

def setup_mouse_drag(app):
    def _coords(event):
        bw = app.preview_box.winfo_width()
        bh = app.preview_box.winfo_height()
        iw, ih = app.last_preview_size
        return event.x - (bw - iw) / 2.0, event.y - (bh - ih) / 2.0, iw, ih

    def on_press(event):
        if not app.image_files or not app.zoom_sw.get():
            return
        mx, my, cw, ch = _coords(event)
        sx1, sy1, sx2, sy2 = get_zoom_rect(cw, ch, app.sl_zoom_start.get(), app.sl_start_x.get(), app.sl_start_y.get())
        ex1, ey1, ex2, ey2 = get_zoom_rect(cw, ch, app.sl_zoom_end.get(), app.sl_end_x.get(), app.sl_end_y.get())
        d_s = (mx - (sx1 + sx2) / 2.0) ** 2 + (my - (sy1 + sy2) / 2.0) ** 2
        d_e = (mx - (ex1 + ex2) / 2.0) ** 2 + (my - (ey1 + ey2) / 2.0) ** 2

        if d_e <= d_s and ex1 <= mx <= ex2 and ey1 <= my <= ey2:
            app.drag_target = "end"
        elif sx1 <= mx <= sx2 and sy1 <= my <= sy2:
            app.drag_target = "start"
        elif ex1 <= mx <= ex2 and ey1 <= my <= ey2:
            app.drag_target = "end"
        else:
            app.drag_target = None

    def on_drag(event):
        if not app.drag_target or not app.image_files:
            return
        mx, my, cw, ch = _coords(event)
        is_s = (app.drag_target == "start")
        z = max(1.01, app.sl_zoom_start.get() if is_s else app.sl_zoom_end.get())
        max_dx = (cw - cw / z) / 2.0
        max_dy = (ch - ch / z) / 2.0
        px = max(-100.0, min(100.0, ((mx - cw / 2.0) / max_dx * 100.0) if max_dx > 1 else 0.0))
        py = max(-100.0, min(100.0, ((my - ch / 2.0) / max_dy * 100.0) if max_dy > 1 else 0.0))

        if is_s:
            app.sl_start_x.set(px)
            app.sl_start_y.set(py)
            app.lbl_start_x.configure(text=f"{px:+.0f}%")
            app.lbl_start_y.configure(text=f"{py:+.0f}%")
        else:
            app.sl_end_x.set(px)
            app.sl_end_y.set(py)
            app.lbl_end_x.configure(text=f"{px:+.0f}%")
            app.lbl_end_y.configure(text=f"{py:+.0f}%")
        app.refresh_preview()

    app.preview_box.bind("\x3cButtonPress-1\x3e", on_press)
    app.preview_box.bind("\x3cB1-Motion\x3e", on_drag)
    app.preview_box.bind("\x3cButtonRelease-1\x3e", lambda _: setattr(app, "drag_target", None))
