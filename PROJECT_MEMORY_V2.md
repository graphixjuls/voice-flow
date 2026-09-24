# Voice Flow V2 — Project Memory & Session Snapshot

## 📅 Snapshot Date
- **Timestamp**: 2026-09-24
- **Version**: Voice Flow 2.0 (Stable)
- **Status**: Production-ready, fully tested, running with CUDA hardware acceleration on RTX 4050 GPU.

---

## 🏗️ System Architecture & Key Files

| File | Purpose & Architecture |
| :--- | :--- |
| [`main.py`](file:///c:/Users/onwod/Documents/My%20Projects/Voice%20Recorder%20and%20Transcriper/main.py) | Application entrypoint, system tray icon (`pystray`), logging setup, recording state coordination, auto-paste workflow. |
| [`cuda_setup.py`](file:///c:/Users/onwod/Documents/My%20Projects/Voice%20Recorder%20and%20Transcriper/cuda_setup.py) | Early discovery and registration of NVIDIA CUDA 12 runtime DLLs (`cublas`, `cudnn`, `nvrtc`) via `os.add_dll_directory` and system `PATH`. |
| [`transcriber.py`](file:///c:/Users/onwod/Documents/My%20Projects/Voice%20Recorder%20and%20Transcriper/transcriber.py) | Faster-Whisper local engine. Configured for `distil-large-v3` on CUDA `float16`. Includes a 1-sample warmup probe and seamless automatic fallback to CPU `int8`. |
| [`cloud_transcriber.py`](file:///c:/Users/onwod/Documents/My%20Projects/Voice%20Recorder%20and%20Transcriper/cloud_transcriber.py) | Multi-provider cloud engine supporting OpenAI (`whisper-1`), Groq (`whisper-large-v3`), and Google Gemini (`gemini-2.5-flash`). |
| [`smart_dictation.py`](file:///c:/Users/onwod/Documents/My%20Projects/Voice%20Recorder%20and%20Transcriper/smart_dictation.py) | Post-processing pipeline: parses spoken punctuation ("period", "comma", "new line"), filters fillers ("um", "uh"), cleans stuttered duplicates, suppresses Whisper hallucinations. |
| [`hotkey_manager.py`](file:///c:/Users/onwod/Documents/My%20Projects/Voice%20Recorder%20and%20Transcriper/hotkey_manager.py) | Global low-level keyboard listener supporting both **Hold-to-Talk** (Push-to-Talk) and **Tap-to-Toggle** (Hands-free). Uses `threading.RLock` with callbacks dispatched outside lock to prevent recursive deadlocks. |
| [`recorder.py`](file:///c:/Users/onwod/Documents/My%20Projects/Voice%20Recorder%20and%20Transcriper/recorder.py) | `sounddevice` audio capture with throttled (30 FPS) RMS level callback, audio gain normalization (AGC), and device selection. |
| [`settings_dialog.py`](file:///c:/Users/onwod/Documents/My%20Projects/Voice%20Recorder%20and%20Transcriper/settings_dialog.py) | Dark-themed settings GUI for microphone selection, model choices, API key management, hotkey binding, and decoupled live mic test meter. |
| [`ui.py`](file:///c:/Users/onwod/Documents/My%20Projects/Voice%20Recorder%20and%20Transcriper/ui.py) | Always-on-top glassmorphic floating widget with live audio VU meter, status pill, one-click copy buttons, and history list. |
| [`paste_service.py`](file:///c:/Users/onwod/Documents/My%20Projects/Voice%20Recorder%20and%20Transcriper/paste_service.py) | Modifier-safe text paste into focused windows with delayed clipboard restoration. |
| [`sound_cues.py`](file:///c:/Users/onwod/Documents/My%20Projects/Voice%20Recorder%20and%20Transcriper/sound_cues.py) | Audio feedback with `winsound.Beep` and system `MessageBeep` fallback. |
| [`config.py`](file:///c:/Users/onwod/Documents/My%20Projects/Voice%20Recorder%20and%20Transcriper/config.py) | Persistent JSON settings at `%LOCALAPPDATA%\VoiceFlow\config.json`. |
| [`dist/VoiceFlow.exe`](file:///c:/Users/onwod/Documents/My%20Projects/Voice%20Recorder%20and%20Transcriper/dist/VoiceFlow.exe) | Rebuilt standalone single-file Windows executable. |

---

## 🛠️ Resolved Gotchas & Critical Fixes

1. **`cublas64_12.dll is not found`**:
   - Installed `nvidia-cublas-cu12` and `nvidia-cudnn-cu12`.
   - Copied essential CUDA DLLs into `dist\`.
   - Implemented `cuda_setup.py` for early search directory registration.
   - Added automatic CPU fallback in `transcriber.py` if CUDA DLLs are ever missing.
2. **Settings Window (Not Responding) Freeze**:
   - Fixed by decoupling the mic test meter from raw audio callbacks and throttling audio level updates to 30 FPS.
   - Removed blocking `grab_set()` modal lock.
3. **Push-to-Talk Deadlock**:
   - Fixed by switching `hotkey_manager.py` mutex to `threading.RLock()` and dispatching callbacks outside the lock.
4. **VAD Empty Audio Crash (`ValueError: max() arg is an empty sequence`)**:
   - Fixed by adding silence amplitude thresholding and catching empty sequence exceptions in `transcriber.py`.

---

## 🚀 How to Resume Next Time
1. **Launch App**: Double-click the **Voice Flow** shortcut on the Desktop or run `dist\VoiceFlow.exe`.
2. **Dictate**: Hold **Ctrl+Alt**, speak naturally, and release to paste.
3. **Configure**: Click **⚙** on the floating widget or right-click the tray icon to open **Settings**.
