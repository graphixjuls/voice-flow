import queue
import time
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageTk
import pyperclip

from settings_dialog import SettingsDialog

STATUS_COLORS = {
    "idle": "#5c6275",
    "recording": "#ff5252",
    "transcribing": "#f59f00",
    "ready": "#51cf66",
    "error": "#fa5252",
}

STATUS_LABELS = {
    "idle": "Ready",
    "recording": "Listening...",
    "transcribing": "Transcribing...",
    "ready": "Pasted!",
    "error": "Error",
}

BG = "#13141a"
SURFACE = "#1c1e27"
SURFACE2 = "#262938"
FG = "#f8f9fa"
MUTED = "#868e96"
ACCENT = "#4c6ef5"
KEY_COLOR = "#ff00fe"

CORNER_RADIUS = 16
WINDOW_W, WINDOW_H = 340, 310
MAX_HISTORY = 10


class VoiceFlowUI:
    """Modern floating glassmorphism widget for Voice Flow V2 with audio level metering."""

    def __init__(
        self,
        hotkey_label: str = "CTRL+ALT",
        mode: str = "local",
        trigger_mode: str = "hold",
        on_mode_change: Optional[Callable[[str], None]] = None,
        on_settings_saved: Optional[Callable[[dict], None]] = None,
        on_quit: Optional[Callable[[], None]] = None,
    ):
        self._queue = queue.Queue()
        self._hotkey_label = hotkey_label
        self._initial_mode = mode
        self._trigger_mode = trigger_mode
        self._on_mode_change = on_mode_change
        self._on_settings_saved = on_settings_saved
        self._on_quit = on_quit

        self._root = None
        self._dot = None
        self._status_label = None
        self._model_label = None
        self._hotkey_sublabel = None
        self._history_frame = None
        self._history_items = []
        self._mode_buttons = {}
        self._corner_images = []
        self._audio_level_bar = None
        self._audio_canvas = None
        self._current_status = "idle"

    # ---- Public Thread-Safe API -----------------------------------------

    def start(self):
        """Initializes the Tk window loop on the main thread."""
        self._root = tk.Tk()
        self._build(self._root)
        self._root.after(40, self._poll)
        self._root.mainloop()

    def set_status(self, status: str):
        self._queue.put(("status", status))

    def set_model_status(self, text: str):
        self._queue.put(("model", text))

    def set_hotkey_label(self, label: str, trigger_mode: str = "hold"):
        self._queue.put(("hotkey_label", (label, trigger_mode)))

    def update_audio_level(self, level: float):
        self._queue.put(("audio_level", level))

    def add_transcript(self, text: str):
        self._queue.put(("transcript", text))

    def set_mode(self, mode: str):
        self._queue.put(("mode", mode))

    def request_show(self):
        self._queue.put(("show", None))

    def request_quit(self):
        self._queue.put(("quit", None))

    # ---- Window Construction --------------------------------------------

    def _build(self, root: tk.Tk):
        root.title("Voice Flow V2")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        try:
            root.attributes("-transparentcolor", KEY_COLOR)
        except tk.TclError:
            pass

        width, height = WINDOW_W, WINDOW_H
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{width}x{height}+{sw - width - 24}+{sh - height - 80}")
        root.configure(bg=KEY_COLOR)
        root.resizable(False, False)

        title_font = tkfont.Font(family="Segoe UI Semibold", size=11)
        normal = tkfont.Font(family="Segoe UI", size=9)
        small = tkfont.Font(family="Segoe UI", size=8)

        card = tk.Frame(root, bg=BG)
        card.place(x=0, y=0, width=width, height=height)
        self._round_corners(root, card, width, height, CORNER_RADIUS)

        # Header Frame
        header = tk.Frame(card, bg=BG, height=44)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        for w in (header,):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._do_drag)

        # Status Glowing Dot
        self._dot = tk.Canvas(header, width=18, height=18, bg=BG, highlightthickness=0)
        self._dot.create_oval(1, 1, 17, 17, fill=SURFACE, outline="")
        self._dot_id = self._dot.create_oval(4, 4, 14, 14, fill=STATUS_COLORS["idle"], outline="")
        self._dot.pack(side="left", padx=(14, 8))
        self._dot.bind("<ButtonPress-1>", self._start_drag)
        self._dot.bind("<B1-Motion>", self._do_drag)

        # Title and dynamic status
        title_wrap = tk.Frame(header, bg=BG)
        title_wrap.pack(side="left", fill="y")
        title_wrap.bind("<ButtonPress-1>", self._start_drag)
        title_wrap.bind("<B1-Motion>", self._do_drag)

        title_row = tk.Frame(title_wrap, bg=BG)
        title_row.pack(anchor="w", pady=(6, 0))
        title_lbl = tk.Label(title_row, text="Voice Flow", bg=BG, fg=FG, font=title_font)
        title_lbl.pack(side="left")
        title_lbl.bind("<ButtonPress-1>", self._start_drag)
        title_lbl.bind("<B1-Motion>", self._do_drag)

        v2_badge = tk.Label(
            title_row,
            text="v2.0",
            bg=SURFACE2,
            fg=ACCENT,
            font=("Segoe UI", 7, "bold"),
            padx=4,
            pady=1,
        )
        v2_badge.pack(side="left", padx=(6, 0))

        self._status_label = tk.Label(
            title_wrap, text=STATUS_LABELS["idle"], bg=BG, fg=MUTED, font=small
        )
        self._status_label.pack(anchor="w")

        # Top Action Buttons: Settings (⚙), Minimize (–), Close (✕)
        btn_box = tk.Frame(header, bg=BG)
        btn_box.pack(side="right", padx=(0, 10))

        settings_btn = tk.Label(
            btn_box, text="⚙", bg=BG, fg=MUTED, font=("Segoe UI", 11), cursor="hand2", width=2
        )
        settings_btn.pack(side="left", padx=2)
        settings_btn.bind("<Button-1>", lambda _e: self._open_settings())
        self._add_hover(settings_btn, SURFACE, BG, fg_hover=FG, fg_normal=MUTED)

        minimize_btn = tk.Label(
            btn_box, text="–", bg=BG, fg=MUTED, font=("Segoe UI", 11), cursor="hand2", width=2
        )
        minimize_btn.pack(side="left", padx=2)
        minimize_btn.bind("<Button-1>", lambda _e: self._root.withdraw())
        self._add_hover(minimize_btn, SURFACE, BG, fg_hover=FG, fg_normal=MUTED)

        # Body Frame
        body = tk.Frame(card, bg=BG)
        body.pack(fill="both", expand=True, padx=14, pady=(2, 8))

        # Hotkey / Trigger indicator row
        hotkey_row = tk.Frame(body, bg=BG)
        hotkey_row.pack(fill="x", pady=(2, 6))

        mode_text = "Hold" if self._trigger_mode == "hold" else "Tap"
        self._hotkey_sublabel = tk.Label(
            hotkey_row,
            text=f"{mode_text} {self._hotkey_label} to talk",
            bg=BG,
            fg=MUTED,
            font=small,
        )
        self._hotkey_sublabel.pack(side="left")

        # Mode Pill (Local vs Cloud)
        pill = tk.Frame(hotkey_row, bg=SURFACE)
        pill.pack(side="right")
        for value, label in (("local", "Local"), ("cloud", "Cloud")):
            btn = tk.Label(
                pill,
                text=label,
                bg=SURFACE,
                fg=MUTED,
                font=small,
                cursor="hand2",
                padx=8,
                pady=2,
            )
            btn.pack(side="left")
            btn.bind("<Button-1>", lambda _e, v=value: self._mode_selected(v))
            self._mode_buttons[value] = btn
        self._apply_mode_style(self._initial_mode)

        # Live VU Audio Level Meter (Active when listening)
        self._audio_canvas = tk.Canvas(body, height=4, bg=SURFACE, highlightthickness=0)
        self._audio_canvas.pack(fill="x", pady=(2, 6))
        self._audio_level_bar = self._audio_canvas.create_rectangle(
            0, 0, 0, 4, fill=STATUS_COLORS["recording"], outline=""
        )

        # Model readiness label
        self._model_label = tk.Label(
            body, text="Initializing model...", bg=BG, fg=MUTED, font=small
        )
        self._model_label.pack(anchor="w", pady=(0, 4))

        # Recent Transcripts Header & Clear button
        hist_head = tk.Frame(body, bg=BG)
        hist_head.pack(fill="x", pady=(6, 2))
        tk.Label(hist_head, text="RECENT TRANSCRIPTS", bg=BG, fg=MUTED, font=small).pack(
            side="left"
        )
        clear_btn = tk.Label(
            hist_head, text="Clear", bg=BG, fg=MUTED, font=small, cursor="hand2"
        )
        clear_btn.pack(side="right")
        clear_btn.bind("<Button-1>", lambda _e: self._clear_history())
        self._add_hover(clear_btn, BG, BG, fg_hover=FG, fg_normal=MUTED)

        # History Scrollable Box
        hist_box = tk.Frame(body, bg=SURFACE)
        hist_box.pack(fill="both", expand=True)

        self._history_canvas = tk.Canvas(hist_box, bg=SURFACE, highlightthickness=0)
        self._history_canvas.pack(side="left", fill="both", expand=True)

        self._history_content = tk.Frame(self._history_canvas, bg=SURFACE)
        self._history_window_id = self._history_canvas.create_window(
            (0, 0), window=self._history_content, anchor="nw"
        )
        self._history_content.bind(
            "<Configure>",
            lambda _e: self._history_canvas.configure(
                scrollregion=self._history_canvas.bbox("all")
            ),
        )
        self._history_canvas.bind(
            "<Configure>",
            lambda e: self._history_canvas.itemconfig(self._history_window_id, width=e.width),
        )

        # Footer
        footer = tk.Frame(card, bg=BG, height=28)
        footer.pack(fill="x", side="bottom", padx=14, pady=(0, 8))
        footer.pack_propagate(False)

        settings_link = tk.Label(
            footer, text="⚙ Settings", bg=BG, fg=MUTED, font=small, cursor="hand2"
        )
        settings_link.pack(side="left")
        settings_link.bind("<Button-1>", lambda _e: self._open_settings())
        self._add_hover(settings_link, BG, BG, fg_hover=FG, fg_normal=MUTED)

        quit_btn = tk.Label(footer, text="Quit", bg=BG, fg=MUTED, font=small, cursor="hand2")
        quit_btn.pack(side="right")
        quit_btn.bind("<Button-1>", lambda _e: self._on_quit and self._on_quit())
        self._add_hover(quit_btn, BG, BG, fg_hover=FG, fg_normal=MUTED)

        root.protocol("WM_DELETE_WINDOW", root.withdraw)

    def _round_corners(self, root, card, width, height, radius):
        size = radius * 2
        mask = Image.new("RGB", (size, size), KEY_COLOR)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BG)
        crops = {
            "nw": mask.crop((0, 0, radius, radius)),
            "ne": mask.crop((radius, 0, size, radius)),
            "sw": mask.crop((0, radius, radius, size)),
            "se": mask.crop((radius, radius, size, size)),
        }
        positions = {
            "nw": (0, 0),
            "ne": (width - radius, 0),
            "sw": (0, height - radius),
            "se": (width - radius, height - radius),
        }
        for key, crop in crops.items():
            photo = ImageTk.PhotoImage(crop)
            self._corner_images.append(photo)
            label = tk.Label(root, image=photo, bd=0, highlightthickness=0)
            label.place(x=positions[key][0], y=positions[key][1])

    def _add_hover(self, widget, bg_hover, bg_normal, fg_hover, fg_normal):
        widget.bind("<Enter>", lambda _e: widget.configure(bg=bg_hover, fg=fg_hover))
        widget.bind("<Leave>", lambda _e: widget.configure(bg=bg_normal, fg=fg_normal))

    # ---- Dragging --------------------------------------------------------

    def _start_drag(self, event):
        self._drag_x, self._drag_y = event.x, event.y

    def _do_drag(self, event):
        x = self._root.winfo_x() + (event.x - self._drag_x)
        y = self._root.winfo_y() + (event.y - self._drag_y)
        self._root.geometry(f"+{x}+{y}")

    # ---- Mode Styling ----------------------------------------------------

    def _mode_selected(self, value):
        self._apply_mode_style(value)
        if self._on_mode_change:
            self._on_mode_change(value)

    def _apply_mode_style(self, active_value):
        for value, btn in self._mode_buttons.items():
            if value == active_value:
                btn.configure(bg=ACCENT, fg="#ffffff")
            else:
                btn.configure(bg=SURFACE, fg=MUTED)

    # ---- Settings Dialog -------------------------------------------------

    def _open_settings(self):
        SettingsDialog(self._root, on_settings_saved=self._handle_settings_saved)

    def _handle_settings_saved(self, new_cfg):
        self._initial_mode = new_cfg.get("stt_mode", "local")
        self._apply_mode_style(self._initial_mode)
        mode_text = "Hold" if new_cfg.get("hotkey_mode") == "hold" else "Tap"
        hotkey_str = new_cfg.get("hotkey", "ctrl+alt").upper()
        self._hotkey_sublabel.configure(text=f"{mode_text} {hotkey_str} to talk")

        if self._on_settings_saved:
            self._on_settings_saved(new_cfg)

    # ---- Queue Polling (Main Thread) -------------------------------------

    def _poll(self):
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                self._handle(kind, payload)
        except queue.Empty:
            pass
        self._root.after(40, self._poll)

    def _handle(self, kind: str, payload):
        if kind == "status":
            self._current_status = payload
            color = STATUS_COLORS.get(payload, "#5c6275")
            self._dot.itemconfig(self._dot_id, fill=color)
            self._status_label.configure(text=STATUS_LABELS.get(payload, payload))
            # Reset audio bar if not recording
            if payload != "recording":
                self._audio_canvas.coords(self._audio_level_bar, 0, 0, 0, 4)

        elif kind == "audio_level":
            if self._current_status == "recording":
                w = self._audio_canvas.winfo_width()
                bar_w = int(w * payload)
                self._audio_canvas.coords(self._audio_level_bar, 0, 0, bar_w, 4)

        elif kind == "model":
            self._model_label.configure(text=payload)

        elif kind == "hotkey_label":
            label, trig = payload
            mode_text = "Hold" if trig == "hold" else "Tap"
            self._hotkey_sublabel.configure(text=f"{mode_text} {label} to talk")

        elif kind == "transcript":
            self._append_history_item(payload)

        elif kind == "mode":
            self._apply_mode_style(payload)

        elif kind == "show":
            self._root.deiconify()
            self._root.lift()

        elif kind == "quit":
            self._root.quit()
            self._root.destroy()

    def _append_history_item(self, text: str):
        if not text:
            return

        stamp = time.strftime("%H:%M:%S")
        is_system = text.startswith("[") and text.endswith("]")

        row = tk.Frame(self._history_content, bg=SURFACE)
        row.pack(fill="x", padx=6, pady=3)

        top_line = tk.Frame(row, bg=SURFACE)
        top_line.pack(fill="x")

        tk.Label(
            top_line,
            text=stamp,
            bg=SURFACE,
            fg=MUTED,
            font=("Segoe UI", 7),
        ).pack(side="left")

        if not is_system:
            copy_btn = tk.Label(
                top_line,
                text="📋 Copy",
                bg=SURFACE,
                fg=MUTED,
                font=("Segoe UI", 7),
                cursor="hand2",
            )
            copy_btn.pack(side="right")
            copy_btn.bind("<Button-1>", lambda _e, t=text, b=copy_btn: self._copy_transcript(t, b))
            self._add_hover(copy_btn, SURFACE2, SURFACE, fg_hover=FG, fg_normal=MUTED)

        txt_label = tk.Label(
            row,
            text=text,
            bg=SURFACE,
            fg=MUTED if is_system else FG,
            font=("Segoe UI", 8),
            wraplength=290,
            justify="left",
            anchor="w",
        )
        txt_label.pack(fill="x", anchor="w")

        self._history_items.append(row)
        if len(self._history_items) > MAX_HISTORY:
            oldest = self._history_items.pop(0)
            oldest.destroy()

        self._history_canvas.update_idletasks()
        self._history_canvas.yview_moveto(1.0)

    def _copy_transcript(self, text: str, btn: tk.Label):
        try:
            pyperclip.copy(text)
            btn.configure(text="✓ Copied!", fg=STATUS_COLORS["ready"])
            self._root.after(1500, lambda: btn.configure(text="📋 Copy", fg=MUTED))
        except Exception:
            pass

    def _clear_history(self):
        for item in self._history_items:
            item.destroy()
        self._history_items.clear()
