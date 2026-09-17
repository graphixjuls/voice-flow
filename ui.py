import queue
import time
import tkinter as tk
from tkinter import font as tkfont

from PIL import Image, ImageDraw, ImageTk

STATUS_COLORS = {
    "idle": "#5b6072",
    "recording": "#ff5c5c",
    "transcribing": "#ffb545",
}

STATUS_LABELS = {
    "idle": "Idle",
    "recording": "Recording...",
    "transcribing": "Transcribing...",
}

BG = "#17181d"
SURFACE = "#212330"
FG = "#f5f6fa"
MUTED = "#888ca0"
ACCENT = "#6c8bff"
KEY_COLOR = "#ff00fe"  # never used elsewhere; marks pixels as transparent

CORNER_RADIUS = 16
WINDOW_W, WINDOW_H = 304, 244
MAX_HISTORY = 8


class VoiceFlowUI:
    """Small always-on-top floating widget mirroring the tray icon's state.

    All public methods are thread-safe: they may be called from the recorder,
    model-loading, or tray-icon threads. Actual widget mutation always happens
    on the Tk main thread via a polled queue.
    """

    def __init__(self, hotkey_label, mode, on_mode_change=None, on_quit=None):
        self._queue = queue.Queue()
        self._hotkey_label = hotkey_label
        self._initial_mode = mode
        self._on_mode_change = on_mode_change
        self._on_quit = on_quit

        self._root = None
        self._dot = None
        self._status_label = None
        self._model_label = None
        self._history_text = None
        self._mode_buttons = {}
        self._corner_images = []  # keep references alive

    # ---- public, thread-safe API -----------------------------------------

    def start(self):
        """Builds the window and blocks in the Tk main loop. Call from the main thread."""
        self._root = tk.Tk()
        self._build(self._root)
        self._root.after(50, self._poll)
        self._root.mainloop()

    def set_status(self, status):
        self._queue.put(("status", status))

    def set_model_status(self, text):
        self._queue.put(("model", text))

    def add_transcript(self, text):
        self._queue.put(("transcript", text))

    def set_mode(self, mode):
        self._queue.put(("mode", mode))

    def request_show(self):
        self._queue.put(("show", None))

    def request_quit(self):
        self._queue.put(("quit", None))

    # ---- window construction ----------------------------------------------

    def _build(self, root):
        root.title("Voice Flow")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        try:
            root.attributes("-transparentcolor", KEY_COLOR)
        except tk.TclError:
            pass

        width, height = WINDOW_W, WINDOW_H
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{width}x{height}+{sw - width - 24}+{sh - height - 90}")
        root.configure(bg=KEY_COLOR)
        root.resizable(False, False)

        title_font = tkfont.Font(family="Segoe UI Semibold", size=11)
        normal = tkfont.Font(family="Segoe UI", size=9)
        small = tkfont.Font(family="Segoe UI", size=8)

        card = tk.Frame(root, bg=BG)
        card.place(x=0, y=0, width=width, height=height)
        self._round_corners(root, card, width, height, CORNER_RADIUS)

        # Header
        header = tk.Frame(card, bg=BG, height=44)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        for w in (header,):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._do_drag)

        self._dot = tk.Canvas(header, width=18, height=18, bg=BG, highlightthickness=0)
        self._dot.create_oval(1, 1, 17, 17, fill=SURFACE, outline="")
        self._dot_id = self._dot.create_oval(4, 4, 14, 14, fill=STATUS_COLORS["idle"], outline="")
        self._dot.pack(side="left", padx=(16, 8))
        self._dot.bind("<ButtonPress-1>", self._start_drag)
        self._dot.bind("<B1-Motion>", self._do_drag)

        title_wrap = tk.Frame(header, bg=BG)
        title_wrap.pack(side="left", fill="y")
        title_wrap.bind("<ButtonPress-1>", self._start_drag)
        title_wrap.bind("<B1-Motion>", self._do_drag)

        tk.Label(title_wrap, text="Voice Flow", bg=BG, fg=FG, font=title_font).pack(
            anchor="w", pady=(9, 0)
        )
        self._status_label = tk.Label(
            title_wrap, text=STATUS_LABELS["idle"], bg=BG, fg=MUTED, font=small
        )
        self._status_label.pack(anchor="w")

        close_btn = tk.Label(
            header, text="–", bg=BG, fg=MUTED, font=("Segoe UI", 12), cursor="hand2", width=2
        )
        close_btn.pack(side="right", padx=(0, 8))
        close_btn.bind("<Button-1>", lambda _e: self._root.withdraw())
        self._add_hover(close_btn, SURFACE, BG, fg_hover=FG, fg_normal=MUTED)

        # Body
        body = tk.Frame(card, bg=BG)
        body.pack(fill="both", expand=True, padx=16, pady=(2, 12))

        tk.Label(
            body,
            text=f"Hold {self._hotkey_label} to talk",
            bg=BG,
            fg=MUTED,
            font=small,
        ).pack(anchor="w", pady=(4, 10))

        mode_row = tk.Frame(body, bg=BG)
        mode_row.pack(fill="x")
        tk.Label(mode_row, text="Mode", bg=BG, fg=FG, font=normal).pack(side="left")

        pill = tk.Frame(mode_row, bg=SURFACE)
        pill.pack(side="right")
        for value, label in (("local", "Local"), ("cloud", "Cloud")):
            btn = tk.Label(
                pill, text=label, bg=SURFACE, fg=MUTED, font=small, cursor="hand2",
                padx=10, pady=4,
            )
            btn.pack(side="left")
            btn.bind("<Button-1>", lambda _e, v=value: self._mode_selected(v))
            self._mode_buttons[value] = btn
        self._apply_mode_style(self._initial_mode)

        self._model_label = tk.Label(
            body, text="Loading model...", bg=BG, fg=MUTED, font=small
        )
        self._model_label.pack(anchor="w", pady=(10, 0))

        tk.Label(body, text="RECENT TRANSCRIPTS", bg=BG, fg=MUTED, font=small).pack(
            anchor="w", pady=(12, 4)
        )

        hist_wrap = tk.Frame(body, bg=SURFACE)
        hist_wrap.pack(fill="both", expand=True)
        self._history_text = tk.Text(
            hist_wrap,
            bg=SURFACE,
            fg=FG,
            font=small,
            wrap="word",
            bd=0,
            highlightthickness=0,
            padx=10,
            pady=8,
            state="disabled",
        )
        self._history_text.pack(fill="both", expand=True)

        footer = tk.Frame(card, bg=BG)
        footer.pack(fill="x", padx=16, pady=(0, 12))
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

    # ---- drag handling ------------------------------------------------------

    def _start_drag(self, event):
        self._drag_x, self._drag_y = event.x, event.y

    def _do_drag(self, event):
        x = self._root.winfo_x() + (event.x - self._drag_x)
        y = self._root.winfo_y() + (event.y - self._drag_y)
        self._root.geometry(f"+{x}+{y}")

    # ---- queue polling (runs on Tk main thread) ------------------------------

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

    def _poll(self):
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                self._handle(kind, payload)
        except queue.Empty:
            pass
        self._root.after(50, self._poll)

    def _handle(self, kind, payload):
        if kind == "status":
            self._dot.itemconfig(self._dot_id, fill=STATUS_COLORS.get(payload, "#5b6072"))
            self._status_label.configure(text=STATUS_LABELS.get(payload, payload))
        elif kind == "model":
            self._model_label.configure(text=payload)
        elif kind == "transcript":
            self._append_history(payload)
        elif kind == "mode":
            self._apply_mode_style(payload)
        elif kind == "show":
            self._root.deiconify()
            self._root.lift()
        elif kind == "quit":
            self._root.quit()
            self._root.destroy()

    def _append_history(self, text):
        stamp = time.strftime("%H:%M:%S")
        self._history_text.configure(state="normal")
        self._history_text.insert("end", f"[{stamp}] {text}\n")
        line_count = int(self._history_text.index("end-1c").split(".")[0])
        if line_count > MAX_HISTORY:
            self._history_text.delete("1.0", f"{line_count - MAX_HISTORY}.0")
        self._history_text.see("end")
        self._history_text.configure(state="disabled")
