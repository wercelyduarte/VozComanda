#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bootstrapper do VozComanda.

Garante que todas as dependencias estejam instaladas ANTES de abrir o app.
Pensado para rodar em qualquer PC Windows que tenha o interpretador Python
disponivel no PATH (ou via 'py -3.x'). Se faltar algum pacote, ele instala
automaticamente via pip (mesmo Python que esta executando este script).

Fluxo:
  1. Tenta importar cada dependencia.
  2. Se faltar alguma, instala via 'pip install <pkg==versao>' (versao
     minima pega do requirements.txt).
  3. So entao import (lazy) e dispara vozComanda.main().

Nada aqui depende de pacotes de terceiros -- usa apenas stdlib + sys.executable
para chamar o pip do mesmo Python que roda este script.
"""
import os
import re
import sys
import subprocess
import importlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REQUIREMENTS = os.path.join(BASE_DIR, "requirements.txt")

# (modulo_importado, nome_do_pip_package)
# faster_whisper -> pip package 'faster-whisper'
DEPENDENCIAS = [
    ("sounddevice", "sounddevice"),
    ("numpy", "numpy"),
    ("faster_whisper", "faster-whisper"),
    ("speech_recognition", "SpeechRecognition"),
    ("deep_translator", "deep-translator"),
    ("sv_ttk", "sv-ttk"),
    ("edge_tts", "edge-tts"),
]
if sys.platform == "win32":
    DEPENDENCIAS.append(("comtypes", "comtypes"))   # voz offline do Windows (SAPI)


def _versao_minima(pkg_pip):
    """Le requirements.txt e devolve a versao minima (ex.: '>=1.0.0') se houver."""
    if not os.path.exists(REQUIREMENTS):
        return ""
    try:
        with open(REQUIREMENTS, "r", encoding="utf-8") as f:
            for linha in f:
                linha = linha.strip()
                if not linha or linha.startswith("#"):
                    continue
                # tolera formatos "pkg>=1.0.0", "pkg>=1.0.0  # comment", "pkg"
                nome = re.split(r"[<>=!~\[]", linha, 1)[0].strip()
                if nome.lower() == pkg_pip.lower():
                    # pega o trecho a partir do primeiro >= / == / ~= etc.
                    m = re.search(r"(>=|==|~=|>|<)[^;#]*", linha)   # sem o marcador "; sys_platform"
                    return m.group(0).strip() if m else ""
    except Exception:
        pass
    return ""


def _tem(modulo):
    try:
        importlib.import_module(modulo)
        return True
    except Exception:
        return False


def _instalar(pkg_pip):
    """Instala o pacote usando o pip do MESMO interpretador que roda este script."""
    spec = _versao_minima(pkg_pip)
    alvo = f"{pkg_pip}{spec}" if spec else pkg_pip
    # --no-warn-script-location evita ruido no console do usuario.
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
           "--no-warn-script-location", alvo]
    print(f"[bootstrap] Instalando: {alvo}")
    try:
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[bootstrap] FALHA ao instalar {alvo} (exit {e.returncode}).")
        return False


def garantir_deps():
    faltando = [m for m, _ in DEPENDENCIAS if not _tem(m)]
    if not faltando:
        print("[bootstrap] Todas as dependencias estao presentes.")
        return True

    print("[bootstrap] Dependencias faltando:", ", ".join(faltando))
    # Tenta garantir que o pip em si exista (algumas instalacoes minimalistas nao tem).
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "--version"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("[bootstrap] pip nao encontrado. Tentando ensurepip...")
        try:
            import ensurepip  # type: ignore
            ensurepip.bootstrap(upgrade=True, default_pip=True)
        except Exception as e:
            print(f"[bootstrap] Nao foi possivel habilitar o pip: {e}")
            print("[bootstrap] Instale o Python marcando 'Add pip' na instalacao "
                  "ou rode: python -m ensurepip --upgrade")
            return False

    ok = True
    for modulo, pkg in DEPENDENCIAS:
        if _tem(modulo):
            continue
        if not _instalar(pkg):
            ok = False
            continue
        if not _tem(modulo):
            print(f"[bootstrap] {pkg} instalado, mas import '{modulo}' ainda falha. "
                  "Pode ser incompatibilidade de versao do Python.")
            ok = False
    return ok


def main():
    print("=" * 60)
    print(" VozComanda - verificacao de ambiente")
    print("=" * 60)
    print(f"Python: {sys.executable} ({sys.version.split()[0]})")
    print(f"Local : {BASE_DIR}")
    if not garantir_deps():
        print()
        print("[bootstrap] NAO foi possivel deixar o ambiente pronto.")
        print("[bootstrap] Verifique conexao com a internet e tente novamente,")
        print("[bootstrap] ou instale manualmente: pip install -r requirements.txt")
        input("Pressione Enter para sair...")
        sys.exit(1)

    print()
    print("[bootstrap] Ambiente OK. Abrindo o app...")
    # Import so agora, depois de garantir que existe.
    import vozComanda
    vozComanda.main()


if __name__ == "__main__":
    main()
