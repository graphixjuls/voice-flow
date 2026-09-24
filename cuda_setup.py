import importlib
import logging
import os
import sys


def setup_cuda_dlls():
    """Locates and registers NVIDIA CUDA runtime DLLs (cublas, cudnn) for ctranslate2."""
    try:
        search_dirs = []

        # 1. PyInstaller temp directory
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            search_dirs.append(sys._MEIPASS)

        # 2. Executable directory & adjacent cuda folder
        if sys.executable:
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            search_dirs.append(exe_dir)
            search_dirs.append(os.path.join(exe_dir, "cuda"))

        # 3. Project workspace venv nvidia directories
        try:
            mod_file = globals().get("__file__")
            if mod_file:
                base_dir = os.path.dirname(os.path.abspath(mod_file))
                venv_site = os.path.join(base_dir, "venv", "Lib", "site-packages", "nvidia")
                if os.path.exists(venv_site):
                    for sub in ("cublas", "cudnn", "cuda_nvrtc"):
                        b = os.path.join(venv_site, sub, "bin")
                        if os.path.exists(b):
                            search_dirs.append(b)
        except Exception:
            pass

        # 4. Known project workspace path on this machine
        known_venv_nvidia = r"C:\Users\onwod\Documents\My Projects\Voice Recorder and Transcriper\venv\Lib\site-packages\nvidia"
        if os.path.exists(known_venv_nvidia):
            for sub in ("cublas", "cudnn", "cuda_nvrtc"):
                b = os.path.join(known_venv_nvidia, sub, "bin")
                if os.path.exists(b):
                    search_dirs.append(b)

        # 5. Global installed python packages
        for name in ("nvidia.cublas", "nvidia.cudnn", "nvidia.cuda_nvrtc"):
            try:
                mod = importlib.import_module(name)
                for p in getattr(mod, "__path__", []):
                    b = os.path.join(p, "bin")
                    if os.path.exists(b):
                        search_dirs.append(b)
            except Exception:
                pass

        # Register each directory
        registered = set()
        for d in search_dirs:
            if os.path.isdir(d) and d not in registered:
                try:
                    if hasattr(os, "add_dll_directory"):
                        os.add_dll_directory(d)
                    os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
                    registered.add(d)
                    logging.info("Registered CUDA DLL search path: %s", d)
                except Exception as e:
                    logging.debug("Could not register %s: %s", d, e)

    except Exception as exc:
        logging.warning("setup_cuda_dlls encountered error: %s", exc)
