# Carregado pelo Python do snap na inicializacao (fica em site-packages).
# ctypes.util.find_library procura bibliotecas com ldconfig e gcc, que nao enxergam as do
# snap; o sounddevice depende dele para achar a libportaudio. Se a busca normal falhar,
# procura tambem nas pastas de LD_LIBRARY_PATH, que apontam para as bibliotecas do snap.
import ctypes.util
import glob
import os

_find_library_original = ctypes.util.find_library


def _find_library(nome):
    achado = _find_library_original(nome)
    if achado:
        return achado
    for pasta in os.environ.get("LD_LIBRARY_PATH", "").split(":"):
        libs = sorted(glob.glob(os.path.join(pasta, f"lib{nome}.so.*")))
        if pasta and libs:
            return libs[0]
    return None


ctypes.util.find_library = _find_library
