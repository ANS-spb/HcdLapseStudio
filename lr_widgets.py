import tkinter as tk
import customtkinter as ctk

class ToolTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip_win = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _=None):
        if self.tip_win or not self.text:
            return
        x = self.widget.winfo_rootx() + 24
        y = self.widget.winfo_rooty() + 20
        self.tip_win = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg="#3f3f46")
        lbl = tk.Label(
            tw, text=self.text, justify="left", bg="#18181b", fg="#f4f4f5",
            relief="solid", borderwidth=1, font=("Segoe UI", 9), padx=10, pady=6, wraplength=280
        )
        lbl.pack()

    def hide(self, _=None):
        if self.tip_win:
            self.tip_win.destroy()
            self.tip_win = None

def add_help_badge(parent, tooltip_text: str):
    badge = ctk.CTkLabel(
        parent, text="?", width=18, height=18, corner_radius=9,
        fg_color="#3f3f46", text_color="#e4e4e7", font=("Segoe UI", 11, "bold")
    )
    badge.pack(side="right", padx=(4, 0))
    ToolTip(badge, tooltip_text)
    return badge

def make_aurora_logo(parent):
    badge = ctk.CTkFrame(
        parent, fg_color="#0f231d", border_width=1,
        border_color="#10b981", corner_radius=6
    )
    badge.pack(side="left", padx=(12, 14), pady=7)
    lbl = ctk.CTkLabel(
        badge, text="  TIMELAPSE STUDIO  ",
        font=("Bahnschrift", 15, "bold"), text_color="#a7f3d0"
    )
    lbl.pack(padx=4, pady=3)


def _bind_parent_scroll(slider, parent):
    """Intentionally do not bind mouse-wheel events to sliders.

    CTkScrollableFrame handles scrolling itself. The slider must never
    receive or redirect wheel input, so wheel events cannot change its value
    or trigger custom scrolling logic.
    """
    return None

def make_lr_slider(parent, label_text: str, from_val: float, to_val: float, default_val: float,
                   steps: int, fmt: str, command, tooltip: str):
    box = ctk.CTkFrame(parent, fg_color="transparent")
    box.pack(fill="x", padx=10, pady=3)
    hdr = ctk.CTkFrame(box, fg_color="transparent")
    hdr.pack(fill="x")
    ctk.CTkLabel(hdr, text=label_text, font=("Segoe UI", 11), text_color="#d4d4d8").pack(side="left")
    add_help_badge(hdr, tooltip)
    val_lbl = ctk.CTkLabel(hdr, text=fmt.format(default_val), font=("Segoe UI", 11, "bold"), text_color="#38bdf8")
    val_lbl.pack(side="right", padx=4)

    def _on_change(v):
        val_lbl.configure(text=fmt.format(v))
        if command:
            command(v)

    sl = ctk.CTkSlider(
        box, from_=from_val, to=to_val, number_of_steps=steps, height=14,
        fg_color="#3f3f46", progress_color="#0284c7", button_color="#e4e4e7", button_hover_color="#ffffff",
        command=_on_change,
        scroll_step=0  # Disable CTkSlider mouse-wheel value changes; parent scroll frame still receives wheel events.
    )
    sl.set(default_val)
    sl.pack(fill="x", pady=(2, 2))
    _bind_parent_scroll(sl, parent)

    # Do not intercept <MouseWheel> here. Returning "break" on the slider
    # prevents the parent CTkScrollableFrame from receiving the event, so
    # scrolling works only when the pointer is over empty space.
    # CTkSlider does not need a wheel binding to keep its value unchanged.

    # Lightroom-style reset: double-clicking the slider restores only this
    # control to its own declared default value.
    def _reset_on_double_click(_event=None):
        sl.set(default_val)
        _on_change(default_val)
        return "break"

    # CTkSlider receives pointer events on its internal canvas. Bind there so
    # the gesture works when the user double-clicks the track or the knob.
    sl._canvas.bind("<Double-Button-1>", _reset_on_double_click, add="+")

    return sl, val_lbl


def make_lr_slider_with_entry(parent, label_text: str, from_val: float, to_val: float, default_val: float,
                              steps: int, unit: str, command, tooltip: str):
    """Slider with an editable numeric value; keeps wheel scrolling on the parent."""
    box = ctk.CTkFrame(parent, fg_color="transparent")
    box.pack(fill="x", padx=10, pady=3)
    hdr = ctk.CTkFrame(box, fg_color="transparent")
    hdr.pack(fill="x")
    ctk.CTkLabel(hdr, text=label_text, font=("Segoe UI", 11), text_color="#d4d4d8").pack(side="left")
    add_help_badge(hdr, tooltip)
    entry = ctk.CTkEntry(hdr, width=88, height=23, justify="right", font=("Segoe UI", 10),
                         fg_color="#16181c", border_color="#3b434d")
    entry.pack(side="right", padx=4)

    def fmt(v):
        return f"{int(round(float(v))):+d} {unit}"

    def update(v, notify=True):
        value = max(from_val, min(to_val, float(v)))
        slider.set(value)
        entry.delete(0, "end")
        entry.insert(0, fmt(value))
        if notify and command:
            command(value)

    def on_slider(v):
        entry.delete(0, "end")
        entry.insert(0, fmt(v))
        if command:
            command(v)

    slider = ctk.CTkSlider(box, from_=from_val, to=to_val, number_of_steps=steps, height=14,
        fg_color="#3f3f46", progress_color="#0284c7", button_color="#e4e4e7",
        button_hover_color="#ffffff", command=on_slider, scroll_step=0)
    slider.set(default_val)
    slider.pack(fill="x", pady=(2, 2))
    _bind_parent_scroll(slider, parent)
    entry.insert(0, fmt(default_val))

    def commit(_event=None):
        raw = entry.get().strip().lower().replace(unit.lower(), "").replace("k", "").strip()
        try:
            update(float(raw))
        except ValueError:
            update(slider.get(), notify=False)

    entry.bind("<Return>", commit)
    entry.bind("<FocusOut>", commit)

    def reset(_event=None):
        update(default_val)
        return "break"
    slider._canvas.bind("<Double-Button-1>", reset, add="+")
    return slider, entry
