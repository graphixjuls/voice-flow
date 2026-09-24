# Voice Flow V2

A lightning-fast, ultra-accurate voice dictation and transcription tool for Windows.
Hold **Ctrl+Alt** (or tap to toggle), speak naturally, and your voice is transcribed with near-instant speed and pasted directly into whatever app has focus.

Powered by **faster-whisper** with **NVIDIA CUDA GPU acceleration**, **Smart Dictation** post-processing, and multi-engine cloud support (OpenAI, Groq, and Gemini).

---

## What's New in V2

- ⚡ **CUDA GPU Acceleration**: Automatically detects your NVIDIA GPU (e.g. RTX 4050) to run Whisper in **~200–300ms** with `float16` precision (gracefully falls back to CPU if no GPU is present).
- 🎯 **State-of-the-Art Accuracy (`large-v3-turbo`)**: Uses Whisper's 809M-parameter turbo model by default on GPU for ~99% accuracy across accents, terminology, and complex phrasing.
- 🧠 **Smart Dictation Engine**:
  - **Spoken Punctuation**: Naturally handles voice commands like `"period"`, `"comma"`, `"question mark"`, `"new line"`, `"colon"`, `"open quotes"`, etc.
  - **Verbal Filler Cleanup**: Filters stuttered duplicates and filler words (`"um"`, `"uh"`, `"ah"`).
  - **Anti-Hallucination Guard**: Eliminates phantom Whisper phrases (`"Thank you for watching"`, `"Subtitles by..."`, music tags) during silence or breathing.
  - **AI Polish (Optional)**: Can route transcripts through an LLM to rewrite informal rambling into structured, publication-ready prose.
- 🎙️ **Live Audio Level VU Meter**: Real-time visual feedback in the floating widget during recording so you can verify microphone activity.
- 🎛️ **Dual Trigger Styles**: Choose between **Push-to-Talk (Hold)** or **Tap-to-Toggle (Hands-Free)** in Settings.
- ⚙️ **Graphical Settings Window**: Configure everything directly from the UI:
  - Select your preferred microphone from a dropdown with a built-in **Live Mic Test** meter.
  - Choose between Local Whisper models (`large-v3-turbo`, `medium`, `small`, `base`, `tiny`) or Cloud engines (OpenAI, Groq, Gemini).
  - Input API keys securely in the GUI.
  - Customize hotkeys and trigger modes.
- 📋 **Transcript History with One-Click Copy**: Copy any past transcript with a single click, or clear history when done.
- 🔔 **Subtle Sound Cues**: Gentle audio chimes when recording starts and finishes.
- 💾 **Persistent Settings**: Configurations are saved to `%LOCALAPPDATA%\VoiceFlow\config.json`.

---

## Quick Start (Run Executable)

Double-click the **Voice Flow** shortcut on your Desktop, or run `dist\VoiceFlow.exe`.
No Python installation or terminal needed.

- **To talk**: Hold **Ctrl+Alt** (or your custom hotkey), speak, then release.
- **To configure**: Click the **⚙ Settings** button in the floating widget (or right-click the system tray icon and select **Settings...**).
- **To switch mode**: Click the **Local** or **Cloud** pill on the widget.
- **To quit**: Click **Quit** on the widget or right-click the tray icon.

---

## Developer Setup (Running from Source)

```powershell
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py
```

### Rebuilding the .exe

```powershell
venv\Scripts\activate
pyinstaller --onefile --windowed --name VoiceFlow --icon icon.ico --collect-data faster_whisper --collect-binaries ctranslate2 --distpath dist --workpath build --specpath build main.py
```

This regenerates `dist\VoiceFlow.exe`.

---

## Cloud Providers (Optional)

If you prefer online cloud transcription or want to use AI Polish:
1. Open **Settings** (⚙ icon on widget).
2. Under **Engine & Model**, select your cloud provider:
   - **OpenAI**: Uses `whisper-1` for transcription.
   - **Groq**: Uses ultra-fast `whisper-large-v3` (~150ms cloud latency).
   - **Google Gemini**: Uses `gemini-2.5-flash` for multimodal speech-to-text.
3. Paste your API key and click **Save & Apply**.

---

## Configuration & Logs

- **Config File**: `%LOCALAPPDATA%\VoiceFlow\config.json`
- **Application Log**: `%LOCALAPPDATA%\VoiceFlow\voiceflow.log`
