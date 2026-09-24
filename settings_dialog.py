import logging
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from typing import Callable, Optional

from config import has_cuda, load_config, save_config
from recorder import Recorder, list_input_devices

BG = "#14151b"
SURFACE = "#1e2029"
SURFACE2 = "#282a36"
FG = "#f8f9fa"
MUTED = "#909296"
ACCENT = "#4c6ef5"
SUCCESS = "#51cf66"
ERROR = "#ff6b6b"


class SettingsDialog:
    """Modern dark-themed Settings window for Voice Flow V2."""

    def __init__(self, parent: tk.Tk, on_settings_saved: Optional[Callable[[dict], None]] = None):
        self.parent = parent
        self.on_settings_saved = on_settings_saved
        self.cfg = load_config()

        self.window = tk.Toplevel(parent)
        self.window.title("Voice Flow V2 - Settings")
        self.window.geometry("520x620")
        self.window.minsize(500, 580)
        self.window.configure(bg=BG)
        self.window.transient(parent)
        self.window.grab_set()

        # Center on screen
        sw = self.window.winfo_screenwidth()
        sh = self.window.winfo_screenheight()
        self.window.geometry(f"520x620+{(sw - 520) // 2}+{(sh - 620) // 2}")

        self._test_rec = None
        self._test_thread = None
        self._testing_mic = False

        self._build_ui()
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        title_font = tkfont.Font(family="Segoe UI Semibold", size=13)
        section_font = tkfont.Font(family="Segoe UI Semibold", size=10)
        label_font = tkfont.Font(family="Segoe UI", size=9)
        small_font = tkfont.Font(family="Segoe UI", size=8)

        # Header
        header = tk.Frame(self.window, bg=SURFACE, height=50)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(
            header,
            text="Settings & Preferences",
            bg=SURFACE,
            fg=FG,
            font=title_font,
        ).pack(side="left", padx=20, pady=12)

        # Notebook / Tabs
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "TNotebook",
            background=BG,
            borderwidth=0,
        )
        style.configure(
            "TNotebook.Tab",
            background=SURFACE,
            foreground=MUTED,
            padding=[14, 8],
            font=("Segoe UI", 9),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", SURFACE2)],
            foreground=[("selected", FG)],
        )

        notebook = ttk.Notebook(self.window)
        notebook.pack(fill="both", expand=True, padx=16, pady=12)

        tab_engine = tk.Frame(notebook, bg=BG)
        tab_audio = tk.Frame(notebook, bg=BG)
        tab_hotkey = tk.Frame(notebook, bg=BG)
        tab_dictation = tk.Frame(notebook, bg=BG)

        notebook.add(tab_engine, text="Engine & Model")
        notebook.add(tab_audio, text="Microphone")
        notebook.add(tab_hotkey, text="Hotkey & Paste")
        notebook.add(tab_dictation, text="Smart Dictation")

        # ================= TAB 1: ENGINE & MODEL =================
        cuda_ok = has_cuda()
        cuda_badge = "⚡ NVIDIA CUDA GPU Detected (Fastest)" if cuda_ok else "💻 CPU Mode Only"

        tk.Label(
            tab_engine,
            text=f"Hardware: {cuda_badge}",
            bg=SURFACE,
            fg=SUCCESS if cuda_ok else MUTED,
            font=label_font,
            padx=10,
            pady=6,
        ).pack(fill="x", padx=14, pady=(12, 10))

        # STT Mode
        mode_box = tk.LabelFrame(
            tab_engine, text=" Transcription Mode ", bg=BG, fg=FG, font=section_font, padx=12, pady=8
        )
        mode_box.pack(fill="x", padx=14, pady=6)

        self.mode_var = tk.StringVar(value=self.cfg.get("stt_mode", "local"))
        tk.Radiobutton(
            mode_box,
            text="Local Mode (Completely offline, private, zero cost)",
            variable=self.mode_var,
            value="local",
            bg=BG,
            fg=FG,
            selectcolor=SURFACE2,
            activebackground=BG,
            activeforeground=FG,
            font=label_font,
        ).pack(anchor="w", pady=2)
        tk.Radiobutton(
            mode_box,
            text="Cloud Mode (Online API: OpenAI, Groq, or Gemini)",
            variable=self.mode_var,
            value="cloud",
            bg=BG,
            fg=FG,
            selectcolor=SURFACE2,
            activebackground=BG,
            activeforeground=FG,
            font=label_font,
        ).pack(anchor="w", pady=2)

        # Local Model
        local_box = tk.LabelFrame(
            tab_engine, text=" Local Model Settings ", bg=BG, fg=FG, font=section_font, padx=12, pady=8
        )
        local_box.pack(fill="x", padx=14, pady=6)

        tk.Label(local_box, text="Whisper Model:", bg=BG, fg=MUTED, font=label_font).pack(anchor="w")
        self.local_model_var = tk.StringVar(value=self.cfg.get("local_model", "distil-large-v3"))
        model_options = [
            "distil-large-v3",
            "large-v3",
            "medium",
            "small",
            "base",
            "tiny",
        ]
        model_dropdown = ttk.Combobox(
            local_box,
            textvariable=self.local_model_var,
            values=model_options,
            state="readonly",
            font=label_font,
        )
        model_dropdown.pack(fill="x", pady=(2, 6))

        tk.Label(
            local_box,
            text="* distil-large-v3 is recommended on CUDA for state-of-the-art accuracy.",
            bg=BG,
            fg=MUTED,
            font=small_font,
        ).pack(anchor="w")

        # Cloud Settings
        cloud_box = tk.LabelFrame(
            tab_engine, text=" Cloud API Settings ", bg=BG, fg=FG, font=section_font, padx=12, pady=8
        )
        cloud_box.pack(fill="x", padx=14, pady=6)

        prov_row = tk.Frame(cloud_box, bg=BG)
        prov_row.pack(fill="x", pady=2)
        tk.Label(prov_row, text="Provider:", bg=BG, fg=MUTED, font=label_font).pack(side="left")
        self.cloud_provider_var = tk.StringVar(value=self.cfg.get("cloud_provider", "openai"))
        prov_dropdown = ttk.Combobox(
            prov_row,
            textvariable=self.cloud_provider_var,
            values=["openai", "groq", "gemini"],
            state="readonly",
            width=14,
            font=label_font,
        )
        prov_dropdown.pack(side="left", padx=10)

        tk.Label(cloud_box, text="API Key:", bg=BG, fg=MUTED, font=label_font).pack(
            anchor="w", pady=(6, 2)
        )
        self.api_key_var = tk.StringVar()
        # Prepopulate with corresponding key
        self._update_api_key_field()
        prov_dropdown.bind("<<ComboboxSelected>>", lambda _e: self._update_api_key_field())

        key_row = tk.Frame(cloud_box, bg=BG)
        key_row.pack(fill="x")
        self.key_entry = tk.Entry(
            key_row,
            textvariable=self.api_key_var,
            show="*",
            bg=SURFACE,
            fg=FG,
            insertbackground=FG,
            bd=0,
            font=label_font,
        )
        self.key_entry.pack(side="left", fill="x", expand=True, ipady=4, padx=(0, 6))

        self.show_key_var = tk.BooleanVar(value=False)

        def toggle_key_mask():
            self.key_entry.configure(show="" if self.show_key_var.get() else "*")

        tk.Checkbutton(
            key_row,
            text="Show",
            variable=self.show_key_var,
            command=toggle_key_mask,
            bg=BG,
            fg=MUTED,
            selectcolor=SURFACE2,
            font=small_font,
        ).pack(side="right")

        # ================= TAB 2: MICROPHONE =================
        dev_box = tk.LabelFrame(
            tab_audio, text=" Input Audio Device ", bg=BG, fg=FG, font=section_font, padx=12, pady=10
        )
        dev_box.pack(fill="x", padx=14, pady=10)

        self.devices = list_input_devices()
        dev_names = ["System Default"] + [f"{idx}: {name}" for idx, name in self.devices]

        current_dev = self.cfg.get("input_device_index")
        default_val = "System Default"
        if current_dev is not None:
            for idx, name in self.devices:
                if idx == current_dev:
                    default_val = f"{idx}: {name}"
                    break

        self.device_var = tk.StringVar(value=default_val)
        dev_dropdown = ttk.Combobox(
            dev_box,
            textvariable=self.device_var,
            values=dev_names,
            state="readonly",
            font=label_font,
        )
        dev_dropdown.pack(fill="x", pady=6)

        # Test Mic Button & Meter
        test_frame = tk.Frame(dev_box, bg=BG)
        test_frame.pack(fill="x", pady=(10, 4))

        self.test_btn = tk.Button(
            test_frame,
            text="🎤 Test Microphone",
            command=self._toggle_test_mic,
            bg=SURFACE2,
            fg=FG,
            bd=0,
            padx=10,
            pady=4,
            cursor="hand2",
            font=label_font,
        )
        self.test_btn.pack(side="left")

        self.meter_canvas = tk.Canvas(test_frame, height=18, bg=SURFACE, highlightthickness=0)
        self.meter_canvas.pack(side="right", fill="x", expand=True, padx=(12, 0))
        self.meter_bar = self.meter_canvas.create_rectangle(0, 0, 0, 18, fill=ACCENT, outline="")

        # Sound cues
        cue_box = tk.LabelFrame(
            tab_audio, text=" Audio Feedback ", bg=BG, fg=FG, font=section_font, padx=12, pady=10
        )
        cue_box.pack(fill="x", padx=14, pady=10)

        self.sound_cues_var = tk.BooleanVar(value=self.cfg.get("sound_cues", True))
        tk.Checkbutton(
            cue_box,
            text="Play subtle audio cues when starting and finishing recording",
            variable=self.sound_cues_var,
            bg=BG,
            fg=FG,
            selectcolor=SURFACE2,
            activebackground=BG,
            font=label_font,
        ).pack(anchor="w")

        # ================= TAB 3: HOTKEY & PASTE =================
        hotkey_box = tk.LabelFrame(
            tab_hotkey, text=" Push-To-Talk & Hotkeys ", bg=BG, fg=FG, font=section_font, padx=12, pady=10
        )
        hotkey_box.pack(fill="x", padx=14, pady=10)

        tk.Label(hotkey_box, text="Shortcut Combination:", bg=BG, fg=MUTED, font=label_font).pack(
            anchor="w"
        )
        self.hotkey_var = tk.StringVar(value=self.cfg.get("hotkey", "ctrl+alt"))
        hotkey_options = [
            "ctrl+alt",
            "ctrl+space",
            "alt+space",
            "ctrl+shift",
            "f8",
            "f9",
        ]
        hotkey_combo = ttk.Combobox(
            hotkey_box,
            textvariable=self.hotkey_var,
            values=hotkey_options,
            font=label_font,
        )
        hotkey_combo.pack(fill="x", pady=(2, 10))

        tk.Label(hotkey_box, text="Recording Trigger Mode:", bg=BG, fg=MUTED, font=label_font).pack(
            anchor="w"
        )
        self.trigger_mode_var = tk.StringVar(value=self.cfg.get("hotkey_mode", "hold"))
        tk.Radiobutton(
            hotkey_box,
            text="Hold-to-Talk (Hold keys to speak, release to paste)",
            variable=self.trigger_mode_var,
            value="hold",
            bg=BG,
            fg=FG,
            selectcolor=SURFACE2,
            activebackground=BG,
            font=label_font,
        ).pack(anchor="w", pady=2)
        tk.Radiobutton(
            hotkey_box,
            text="Tap-to-Toggle (Tap once to start, tap again to finish)",
            variable=self.trigger_mode_var,
            value="toggle",
            bg=BG,
            fg=FG,
            selectcolor=SURFACE2,
            activebackground=BG,
            font=label_font,
        ).pack(anchor="w", pady=2)

        paste_box = tk.LabelFrame(
            tab_hotkey, text=" Pasting & Clipboard ", bg=BG, fg=FG, font=section_font, padx=12, pady=10
        )
        paste_box.pack(fill="x", padx=14, pady=10)

        self.auto_paste_var = tk.BooleanVar(value=self.cfg.get("auto_paste", True))
        tk.Checkbutton(
            paste_box,
            text="Auto-paste transcript into focused window",
            variable=self.auto_paste_var,
            bg=BG,
            fg=FG,
            selectcolor=SURFACE2,
            activebackground=BG,
            font=label_font,
        ).pack(anchor="w", pady=2)

        self.restore_clip_var = tk.BooleanVar(value=self.cfg.get("restore_clipboard", True))
        tk.Checkbutton(
            paste_box,
            text="Restore original clipboard content after pasting",
            variable=self.restore_clip_var,
            bg=BG,
            fg=FG,
            selectcolor=SURFACE2,
            activebackground=BG,
            font=label_font,
        ).pack(anchor="w", pady=2)

        # ================= TAB 4: SMART DICTATION =================
        dict_box = tk.LabelFrame(
            tab_dictation, text=" Formatting & Accuracy Rules ", bg=BG, fg=FG, font=section_font, padx=12, pady=10
        )
        dict_box.pack(fill="x", padx=14, pady=10)

        self.smart_dict_var = tk.BooleanVar(value=self.cfg.get("smart_dictation", True))
        tk.Checkbutton(
            dict_box,
            text="Enable Smart Dictation processing",
            variable=self.smart_dict_var,
            bg=BG,
            fg=FG,
            selectcolor=SURFACE2,
            activebackground=BG,
            font=label_font,
        ).pack(anchor="w", pady=2)

        self.punct_var = tk.BooleanVar(value=self.cfg.get("format_punctuation", True))
        tk.Checkbutton(
            dict_box,
            text='Format spoken punctuation (e.g. "period" -> ., "new line" -> Enter)',
            variable=self.punct_var,
            bg=BG,
            fg=FG,
            selectcolor=SURFACE2,
            activebackground=BG,
            font=label_font,
        ).pack(anchor="w", pady=2)

        self.fillers_var = tk.BooleanVar(value=self.cfg.get("clean_fillers", True))
        tk.Checkbutton(
            dict_box,
            text='Filter verbal fillers ("um", "uh", duplicated words)',
            variable=self.fillers_var,
            bg=BG,
            fg=FG,
            selectcolor=SURFACE2,
            activebackground=BG,
            font=label_font,
        ).pack(anchor="w", pady=2)

        self.ai_polish_var = tk.BooleanVar(value=self.cfg.get("ai_polish", False))
        tk.Checkbutton(
            dict_box,
            text="AI Polish (Run LLM pass to rewrite rambling speech into clean prose)",
            variable=self.ai_polish_var,
            bg=BG,
            fg=FG,
            selectcolor=SURFACE2,
            activebackground=BG,
            font=label_font,
        ).pack(anchor="w", pady=2)

        lang_box = tk.Frame(dict_box, bg=BG)
        lang_box.pack(fill="x", pady=(10, 2))
        tk.Label(lang_box, text="Language:", bg=BG, fg=MUTED, font=label_font).pack(side="left")
        self.lang_var = tk.StringVar(value=self.cfg.get("language") or "auto")
        lang_options = ["auto", "en", "es", "fr", "de", "it", "pt", "zh", "ja"]
        lang_combo = ttk.Combobox(
            lang_box,
            textvariable=self.lang_var,
            values=lang_options,
            state="readonly",
            width=10,
            font=label_font,
        )
        lang_combo.pack(side="left", padx=10)

        # Bottom Bar
        footer = tk.Frame(self.window, bg=SURFACE, height=54)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        save_btn = tk.Button(
            footer,
            text="Save & Apply",
            command=self._on_save,
            bg=ACCENT,
            fg="#ffffff",
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            font=label_font,
        )
        save_btn.pack(side="right", padx=16, pady=10)

        cancel_btn = tk.Button(
            footer,
            text="Cancel",
            command=self._on_close,
            bg=SURFACE2,
            fg=FG,
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            font=label_font,
        )
        cancel_btn.pack(side="right", padx=(0, 8), pady=10)

    def _update_api_key_field(self):
        prov = self.cloud_provider_var.get()
        if prov == "groq":
            self.api_key_var.set(self.cfg.get("groq_api_key", ""))
        elif prov == "gemini":
            self.api_key_var.set(self.cfg.get("gemini_api_key", ""))
        else:
            self.api_key_var.set(self.cfg.get("openai_api_key", ""))

    def _toggle_test_mic(self):
        if self._testing_mic:
            self._testing_mic = False
            self.test_btn.configure(text="🎤 Test Microphone", bg=SURFACE2)
            if self._test_rec:
                self._test_rec.stop()
                self._test_rec = None
            self.meter_canvas.coords(self.meter_bar, 0, 0, 0, 18)
        else:
            self._testing_mic = True
            self.test_btn.configure(text="⏹ Stop Test", bg=ERROR)

            dev_val = self.device_var.get()
            dev_idx = None
            if dev_val != "System Default" and ":" in dev_val:
                try:
                    dev_idx = int(dev_val.split(":")[0])
                except Exception:
                    dev_idx = None

            def on_level(lvl):
                if not self._testing_mic:
                    return
                w = self.meter_canvas.winfo_width()
                bar_w = int(w * lvl)
                self.window.after(0, lambda: self.meter_canvas.coords(self.meter_bar, 0, 0, bar_w, 18))

            self._test_rec = Recorder(device=dev_idx, on_level=on_level)
            try:
                self._test_rec.start()
            except Exception as exc:
                self._testing_mic = False
                self.test_btn.configure(text="🎤 Test Microphone", bg=SURFACE2)
                logging.error("Test mic failed: %s", exc)

    def _on_save(self):
        # Update config dictionary
        self.cfg["stt_mode"] = self.mode_var.get()
        self.cfg["local_model"] = self.local_model_var.get()

        prov = self.cloud_provider_var.get()
        self.cfg["cloud_provider"] = prov
        key = self.api_key_var.get().strip()
        if prov == "groq":
            self.cfg["groq_api_key"] = key
            self.cfg["cloud_model"] = "whisper-large-v3"
        elif prov == "gemini":
            self.cfg["gemini_api_key"] = key
            self.cfg["cloud_model"] = "gemini-2.5-flash"
        else:
            self.cfg["openai_api_key"] = key
            self.cfg["cloud_model"] = "whisper-1"

        # Device
        dev_val = self.device_var.get()
        if dev_val == "System Default" or ":" not in dev_val:
            self.cfg["input_device_index"] = None
        else:
            try:
                self.cfg["input_device_index"] = int(dev_val.split(":")[0])
            except Exception:
                self.cfg["input_device_index"] = None

        self.cfg["sound_cues"] = self.sound_cues_var.get()
        self.cfg["hotkey"] = self.hotkey_var.get().lower().strip()
        self.cfg["hotkey_mode"] = self.trigger_mode_var.get()
        self.cfg["auto_paste"] = self.auto_paste_var.get()
        self.cfg["restore_clipboard"] = self.restore_clip_var.get()

        self.cfg["smart_dictation"] = self.smart_dict_var.get()
        self.cfg["format_punctuation"] = self.punct_var.get()
        self.cfg["clean_fillers"] = self.fillers_var.get()
        self.cfg["ai_polish"] = self.ai_polish_var.get()

        lang = self.lang_var.get()
        self.cfg["language"] = None if lang == "auto" else lang

        save_config(self.cfg)

        if self._testing_mic and self._test_rec:
            self._test_rec.stop()

        if self.on_settings_saved:
            self.on_settings_saved(self.cfg)

        self.window.destroy()

    def _on_close(self):
        if self._testing_mic and self._test_rec:
            self._test_rec.stop()
        self.window.destroy()
