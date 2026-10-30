# -*- coding: utf-8 -*-
"""
Build do Voz Comando com cx_Freeze.

  python setup.py build        -> pasta pronta em build\\VozComando\\ (VozComando.exe)
  python setup.py bdist_msi    -> instalador .msi em dist\\
"""
import os
import subprocess
import sys
from pathlib import Path
from cx_Freeze import setup, Executable

APP_NAME = "VozComanda"


def _version() -> str:
    """VERSAO (definida pelo workflow de release) ou a ultima tag do git, para o build local
    sair com a versao da ultima release sem precisar editar este arquivo."""
    if os.environ.get("VERSAO"):
        return os.environ["VERSAO"]
    try:
        tag = subprocess.run(["git", "describe", "--tags", "--abbrev=0"], capture_output=True,
                             text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "1.0.0"
    return tag.lstrip("v") or "1.0.0"


VERSION = _version()
Path("VERSION").write_text(VERSION, encoding="utf-8")   # vai junto do .exe; o build_msix.py le
DESCRIPTION = "Ditado por voz para agentes IA (Google online + faster-whisper offline)"

# base "gui" esconde a janela preta do console no Windows
base = "gui" if sys.platform == "win32" else None

build_exe_options = {
    "build_exe": f"build/{APP_NAME}",
    "packages": [
        "faster_whisper", "ctranslate2", "onnxruntime", "tokenizers",
        "huggingface_hub", "av", "numpy", "sounddevice", "_sounddevice_data",
        "tkinter", "encodings", "speech_recognition", "deep_translator", "sv_ttk",
        "edge_tts", "aiohttp", "certifi", "comtypes",   # leitura em voz alta
    ],
    "excludes": ["pyautogui", "pyperclip", "matplotlib", "pandas", "scipy",
                 "torch", "IPython", "pytest", "PyQt5", "PyQt6"],
    "include_files": [("icone.ico", "icone.ico"),  # icone da janela do app
                      ("VERSION", "VERSION")],
    "include_msvcr": True,
    "optimize": 1,
}

bdist_msi_options = {
    "upgrade_code": "{8F1B3C52-4D7A-4E0B-9A63-2C5D7E91A4F0}",  # mantenha fixo p/ atualizacoes
    "initial_target_dir": rf"[ProgramFiles64Folder]\{APP_NAME}",
    "add_to_path": False,
}

executables = [
    Executable(
        "vozComanda.py",
        base=base,
        target_name=f"{APP_NAME}.exe",
        icon="icone.ico",
        shortcut_name="VozComanda",
        shortcut_dir="DesktopFolder",
    )
]

setup(
    name=APP_NAME,
    version=VERSION,
    description=DESCRIPTION,
    options={"build_exe": build_exe_options, "bdist_msi": bdist_msi_options},
    executables=executables,
)