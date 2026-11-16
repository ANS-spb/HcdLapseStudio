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
        command=_on_change
    )
    sl.set(default_val)
    sl.pack(fill="x", pady=(2, 2))

    def _ignore_wheel(event):
        return "break"
    sl.bind("<MouseWheel>", _ignore_wheel)
    sl._canvas.bind("<MouseWheel>", _ignore_wheel)

    return sl, val_lbl
