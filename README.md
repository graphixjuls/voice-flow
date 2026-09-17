# Voice Flow

A minimal Whisper Flow-style dictation tool: hold **Ctrl+Alt**, speak, release it — your speech
is transcribed and pasted into whatever app currently has focus. Supports two transcription
modes: fully offline (local Whisper) or online (OpenAI's API, more accurate).

## Run the app (no Python needed)

Double-click the **Voice Flow** shortcut on your Desktop, or run
`dist\VoiceFlow.exe` directly. That's it — no terminal, no Python install.

> Don't double-click `main.py` — that runs your system Python, which doesn't
> have this project's dependencies installed and will just error out.

## Developer setup (only needed if you're changing the code)

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Run from source:

```powershell
python main.py
```

### Rebuilding the .exe after code changes

```powershell
venv\Scripts\activate
pip install pyinstaller
pyinstaller --onefile --windowed --name VoiceFlow --icon icon.ico --collect-data faster_whisper --distpath dist --workpath build --specpath build main.py
```

This regenerates `dist\VoiceFlow.exe` (the Desktop shortcut points here, so it
picks up the update automatically).

> The `--collect-data faster_whisper` flag is required — without it, PyInstaller
> omits faster-whisper's bundled voice-activity-detection model file and every
> transcription fails with an `onnxruntime ... NO_SUCHFILE` error.

If the exe misbehaves, check the log file at
`%LOCALAPPDATA%\VoiceFlow\voiceflow.log` — it records hotkey presses, recording
durations, and any transcription errors (the packaged exe has no console, so
this log is the only way to see what went wrong).

A tray icon appears (gray = idle, red = recording, yellow = transcribing), along with a small
rounded floating widget in the bottom-right corner of your screen showing the same status, the
current mode, and your recent transcripts. Drag it by the header to reposition it, hit the `–`
button to tuck it away (bring it back via the tray icon's "Show widget" menu item), and switch
between local/cloud mode with the Local/Cloud toggle.

Hold **Ctrl+Alt** anywhere on your system, talk, then release — the text is typed into whatever
window you were using. Right-click the tray icon (or click "Quit" on the widget) to exit.

In local mode, the first run downloads the Whisper `base` model (~150MB); after that it works
fully offline.

## Configuration

Edit the constants at the top of `main.py`:

- `HOTKEY_KEYS` — push-to-talk key combo, held together (default `("ctrl", "alt")`)
- `STT_MODE` — `"local"` (offline, free, private) or `"cloud"` (online, more accurate, costs
  a small amount per use — see below)
- `MODEL_SIZE` — `tiny` / `base` / `small` / `medium` / `large-v3`, used in local mode (bigger =
  more accurate, slower)
- `CLOUD_MODEL` — OpenAI transcription model, used in cloud mode (default `gpt-4o-transcribe`)
- `LANGUAGE` — set to `"en"` etc. to skip language auto-detection

### Using cloud mode (more accurate)

1. Set `STT_MODE = "cloud"` in `main.py`.
2. Get an API key from https://platform.openai.com/api-keys.
3. Set it as an environment variable before running:
   ```powershell
   $env:OPENAI_API_KEY = "sk-..."
   python main.py
   ```

Cloud mode sends your recorded audio to OpenAI over the internet and costs a small amount per
minute of speech. Local mode never leaves your machine and is free after the model download.
You can switch back to `STT_MODE = "local"` at any time — nothing else in the app changes.

## Notes

- Uses your default microphone via `sounddevice`.
- Transcription runs on CPU by default (`int8`). If you have an NVIDIA GPU with CUDA set up,
  change `device="cpu"` to `device="cuda"` in `transcriber.py` for much faster transcription.
- The `keyboard` library's global hook may need the terminal running as Administrator to
  capture keystrokes while an elevated app (e.g. Task Manager) has focus.
