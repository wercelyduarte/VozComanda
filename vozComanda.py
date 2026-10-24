#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VozComanda — Ditado por voz para agentes IA.

A voz vira texto, o texto vira comando. Dois modos:
  - Google (online): sem download, precisa de internet.
  - Offline (faster-whisper): tiny / base / small / medium / large-v3.

Atalhos:
  F5 ou Space (quando nao estiver digitando) -> Gravar / Parar
  Ctrl+S -> Salvar comando
  Ctrl+L -> Limpar texto
"""
import os
import re
import sys
import json
import glob
import gc
import queue
import threading
import datetime

try:
    import numpy as np
    import tkinter as tk
    from tkinter import ttk, scrolledtext, messagebox, simpledialog
    import sounddevice as sd
    import speech_recognition as sr
except ImportError as _e:
    print("=" * 60)
    print(" Faltam dependencias do VozComanda.")
    print("=" * 60)
    print(f" Detalhe: {_e}")
    print("\n Rode: python bootstrap.py  ou  duplo clique em rodar.bat")
    input(" Pressione Enter para sair...")
    sys.exit(1)

try:
    from faster_whisper import WhisperModel
except ImportError:
    WhisperModel = None

try:
    import sv_ttk as _sv_ttk
except ImportError:
    _sv_ttk = None

# ------------------------------------------------------------------ config
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    BASE_DIR = os.environ.get("VOZ_DATA_DIR") or os.path.join(
        os.environ.get("LOCALAPPDATA", APP_DIR), "VozComanda")
    os.makedirs(BASE_DIR, exist_ok=True)
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = APP_DIR

COMANDO_TXT = os.path.join(BASE_DIR, "comando.txt")
HIST_DIR    = os.path.join(BASE_DIR, "historico")
MODEL_CACHE = os.path.join(BASE_DIR, "models_whisper")
CONFIG_JSON = os.path.join(BASE_DIR, "config.json")

SAMPLE_RATE = 16000
BLOCK       = 4000

# Silencio adicionado antes e depois do audio gravado.
# Evita que o decodificador/VAD corte a primeira e a ultima silaba.
PAD_INICIO  = int(SAMPLE_RATE * 0.15)   # 150 ms antes
PAD_FIM     = int(SAMPLE_RATE * 0.60)   # 600 ms depois

MODELOS = {
    "tiny":     "~75 MB",
    "base":     "~145 MB",
    "small":    "~480 MB",
    "medium":   "~1,5 GB",
    "large-v3": "~3 GB",
}
ONLINE = "Google (online)"
MODEL_SIZE = os.environ.get("VOZ_MODEL", ONLINE)
if MODEL_SIZE != ONLINE and MODEL_SIZE not in MODELOS:
    MODELOS[MODEL_SIZE] = "tamanho desconhecido"

# VAD menos agressivo: speech_pad de 400 ms protege bordas das palavras.
VAD_PARAMS = dict(
    threshold=0.30,
    min_speech_duration_ms=200,
    min_silence_duration_ms=250,
    speech_pad_ms=400,
)

# Vocabulario de dominio: aumenta a precisao em termos tecnicos.
PROMPT_PT = (
    "Firmware, bootloader, atuador, omnimob, OmniCarga, LoRa, LoRaWAN, P2P, OTA, "
    "pareamento, supervisao, PING, PONG, bloqueio, desbloqueio, STM32, KG200Z, "
    "atuador LoRa, Kiro, compilar, gravar, define, UART, ignicao, evento, posicao, "
    "GPRS, GPS, flash, porta, modulo, secret, device, slot, intervalo, firmware do Raul, "
    "spec, steering, commit, branch, relatorio, Jira, Everynet, Quectel, Smart Modular."
)

# ------------------------------------------------------------------ idiomas
# whisper: codigo de 2 letras do Whisper
# google:  codigo BCP-47 para SpeechRecognition
# mm:      codigo para MyMemoryTranslator (exige formato xx-XX)
IDIOMAS_VOZ = {
    "Português BR": {"whisper": "pt", "google": "pt-BR", "mm": "pt-BR"},
    "Português PT": {"whisper": "pt", "google": "pt-PT", "mm": "pt-PT"},
    "Inglês":       {"whisper": "en", "google": "en-US", "mm": "en-GB"},
    "Espanhol":     {"whisper": "es", "google": "es-ES", "mm": "es-ES"},
    "Francês":      {"whisper": "fr", "google": "fr-FR", "mm": "fr-FR"},
    "Alemão":       {"whisper": "de", "google": "de-DE", "mm": "de-DE"},
    "Italiano":     {"whisper": "it", "google": "it-IT", "mm": "it-IT"},
    "Japonês":      {"whisper": "ja", "google": "ja-JP", "mm": "ja-JP"},
    "Chinês":       {"whisper": "zh", "google": "zh-CN", "mm": "zh-CN"},
    "Árabe":        {"whisper": "ar", "google": "ar-SA", "mm": "ar-SA"},
}
IDIOMA_VOZ_PAD = "Português BR"

IDIOMAS_ALVO = {
    "Português": "pt-BR",
    "Inglês":    "en-GB",
    "Espanhol":  "es-ES",
    "Francês":   "fr-FR",
    "Alemão":    "de-DE",
    "Italiano":  "it-IT",
    "Japonês":   "ja-JP",
    "Chinês":    "zh-CN",
    "Árabe":     "ar-SA",
}
IDIOMA_ALVO_PAD = "Inglês"

# Palavras frequentes usadas para detectar PT vs EN sem chamar servico externo.
# Ficam de fora as que existem nos dois idiomas ("a", "as", "no", "do").
_PALAVRAS_PT = {
    "de", "o", "e", "que", "em", "um", "uma", "para", "com", "não", "na",
    "da", "os", "se", "por", "mais", "dos", "das", "mas", "ao", "nos", "nas",
    "seu", "sua", "foi", "ser", "ter", "está", "são", "você", "isso", "como",
    "quando", "muito", "já", "também", "pode",
}
_PALAVRAS_EN = {
    "the", "is", "are", "was", "were", "be", "been", "have", "has", "had",
    "does", "did", "will", "would", "could", "should", "of", "in", "on",
    "at", "to", "for", "with", "by", "this", "that", "it", "an", "and", "or",
    "you", "your", "from", "they", "there", "which", "what", "when",
}

# MyMemory recusa requisicoes acima de 500 caracteres.
_LIMITE_MM = 480


def _quebrar_linha(linha: str, limite: int) -> list:
    """Quebra uma linha longa em pedacos <= limite: fim de frase, senao espaco, senao corte seco."""
    pedacos = []
    while len(linha) > limite:
        corte = max(linha.rfind(s, 0, limite) for s in (". ", "? ", "! ", "。", "？", "！")) + 1
        if corte <= 0:
            corte = linha.rfind(" ", 0, limite)
        if corte <= 0:
            corte = limite
        pedacos.append(linha[:corte].rstrip())
        linha = linha[corte:].lstrip()
    pedacos.append(linha)
    return pedacos


def _dividir_texto(texto: str, limite: int = _LIMITE_MM) -> list:
    """Divide o texto em blocos <= limite sem perder as quebras de linha.
    Cada item e [separador, bloco]; o separador ('', '\\n' ou ' ') vai antes do bloco traduzido."""
    blocos = []
    for i, linha in enumerate(texto.split("\n")):
        for j, parte in enumerate(_quebrar_linha(linha, limite)):
            sep = " " if j else ("\n" if i else "")
            if blocos and len(blocos[-1][1]) + len(sep) + len(parte) <= limite:
                blocos[-1][1] += sep + parte
            else:
                blocos.append([sep, parte])
    return blocos

# ------------------------------------------------------------------ paleta
PALETA = {
    "dark": {
        "C_BG":    "#1a1b2e",
        "C_PANEL": "#252636",
        "C_BORDER":"#3a3b4e",
        "C_TEXT":  "#e2e8f0",
        "C_TEXT2": "#94a3b8",
        "C_SEL":   "#3b4f7a",
        "ST_OK":   "#052e16",
        "ST_INFO": "#0c1a3a",
        "ST_WARN": "#2d1b00",
        "ST_ERR":  "#2d0b0b",
    },
    "light": {
        "C_BG":    "#f0f2f5",
        "C_PANEL": "#ffffff",
        "C_BORDER":"#d1d5db",
        "C_TEXT":  "#111827",
        "C_TEXT2": "#6b7280",
        "C_SEL":   "#bfdbfe",
        "ST_OK":   "#f0fdf4",
        "ST_INFO": "#eff6ff",
        "ST_WARN": "#fffbeb",
        "ST_ERR":  "#fef2f2",
    },
}

# Valores iniciais: dark (padrao). Atualizados por _aplicar_tema().
C_BG      = PALETA["dark"]["C_BG"]
C_PANEL   = PALETA["dark"]["C_PANEL"]
C_HEADER  = "#1a56db"
C_BORDER  = PALETA["dark"]["C_BORDER"]
C_REC     = "#dc2626"
C_REC_DK  = "#991b1b"
C_REC_LT  = "#ef4444"
C_READY   = "#2563eb"
C_READY_H = "#1e40af"
C_TRAN    = "#6b7280"
C_OK      = "#16a34a"
C_INFO    = "#1d4ed8"
C_WARN    = "#b45309"
C_ERR     = "#b91c1c"
C_TEXT    = PALETA["dark"]["C_TEXT"]
C_TEXT2   = PALETA["dark"]["C_TEXT2"]


def opcoes_disponiveis():
    return [ONLINE] + (list(MODELOS.keys()) if WhisperModel is not None else [])


def modelo_baixado(nome):
    pasta = os.path.join(MODEL_CACHE, f"models--Systran--faster-whisper-{nome}", "snapshots")
    return bool(glob.glob(os.path.join(pasta, "*", "model.bin")))


def carregar_config():
    try:
        with open(CONFIG_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def salvar_config(cfg):
    try:
        with open(CONFIG_JSON, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception:
        pass


def _aplicar_pontuacao_google(texto: str) -> str:
    """Capitaliza a primeira letra e adiciona ponto final se nao houver pontuacao."""
    if not texto:
        return texto
    texto = texto[0].upper() + texto[1:]
    if texto[-1] not in ".!?…":
        texto += "."
    return texto


def _remover_pontuacao(texto: str) -> str:
    """Remove pontuacao preservando letras (incluindo acentuadas), numeros e espacos."""
    resultado = re.sub(r"[^\w\s]", " ", texto, flags=re.UNICODE)
    return re.sub(r" +", " ", resultado).strip()


def _normalizar_audio(audio: np.ndarray) -> np.ndarray:
    """Normaliza o volume para ~-10 dBFS.
    Audio muito fraco ou muito forte prejudica o reconhecimento online e offline.
    """
    pico = float(np.max(np.abs(audio)))
    if pico < 1e-4:
        return audio
    alvo = 0.30  # aprox. -10 dBFS
    return np.clip(audio * (alvo / pico), -1.0, 1.0).astype(np.float32)


# ------------------------------------------------------------------ app
class VozComandaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("VozComanda")
        self.root.geometry("740x640")
        self.root.configure(bg=C_BG)
        self.root.resizable(True, True)
        self.root.minsize(560, 500)
        try:
            self.root.iconbitmap(os.path.join(APP_DIR, "icone.ico"))
        except Exception:
            pass

        self.model = None
        self.modelo_atual = None
        self.carregando = False
        self.audio_q: queue.Queue = queue.Queue()
        self.gravando = False
        self.stream = None
        self._pulso = False

        cfg = carregar_config()
        escolhido = cfg.get("modelo", MODEL_SIZE)
        if escolhido not in opcoes_disponiveis():
            escolhido = ONLINE
        self.modelo_sel    = tk.StringVar(value=escolhido)
        self.var_pontuacao = tk.BooleanVar(value=cfg.get("pontuacao", True))
        self._save_dir     = cfg.get("save_dir") or None
        # None = ainda nao perguntado; "" = usuario pulou
        self._mm_email     = cfg.get("mm_email")

        idioma_voz = cfg.get("idioma_voz", IDIOMA_VOZ_PAD)
        if idioma_voz not in IDIOMAS_VOZ:
            idioma_voz = IDIOMA_VOZ_PAD
        self.var_idioma_voz = tk.StringVar(value=idioma_voz)

        self.var_traduzir   = tk.BooleanVar(value=cfg.get("traduzir", False))

        idioma_alvo = cfg.get("idioma_alvo", IDIOMA_ALVO_PAD)
        if idioma_alvo not in IDIOMAS_ALVO:
            idioma_alvo = IDIOMA_ALVO_PAD
        self.var_idioma_alvo = tk.StringVar(value=idioma_alvo)

        self._tema = cfg.get("tema", "dark")
        self._borders = []   # tk.Frame separadores — atualizados em _recolorir_ui

        self._aplicar_tema()
        self._build_ui()
        self._atualizar_info_modelo()
        self._bind_atalhos()

        if escolhido == ONLINE or modelo_baixado(escolhido):
            self.carregar_modelo()
        else:
            self.set_status(
                f"Modelo '{escolhido}' nao baixado. Escolha um e clique em 'Baixar e carregar'.",
                "warn")

    # ---------------------------------------------------------------- tema
    def _aplicar_tema(self, tema=None):
        if tema is not None:
            self._tema = tema
        p = PALETA[self._tema]
        global C_BG, C_PANEL, C_BORDER, C_TEXT, C_TEXT2
        C_BG    = p["C_BG"]
        C_PANEL = p["C_PANEL"]
        C_BORDER= p["C_BORDER"]
        C_TEXT  = p["C_TEXT"]
        C_TEXT2 = p["C_TEXT2"]
        self._STATUS_COR = {
            "ok":   (C_OK,   p["ST_OK"]),
            "info": (C_INFO, p["ST_INFO"]),
            "warn": (C_WARN, p["ST_WARN"]),
            "err":  (C_ERR,  p["ST_ERR"]),
            "idle": (C_TEXT2, C_BG),
        }
        self.root.configure(bg=C_BG)
        if _sv_ttk:
            _sv_ttk.set_theme(self._tema)
        else:
            s = ttk.Style(self.root)
            s.theme_use("clam")
            s.configure("TFrame",       background=C_BG)
            s.configure("TLabel",       background=C_BG, foreground=C_TEXT, font=("Segoe UI", 10))
            s.configure("TButton",      font=("Segoe UI", 10), padding=(10, 6))
            s.configure("TCombobox",    font=("Segoe UI", 10))
            s.configure("TProgressbar", troughcolor=C_BORDER, background=C_INFO, thickness=4)
            s.configure("TSeparator",   background=C_BORDER)

    # ---------------------------------------------------------------- UI
    def _build_ui(self):
        # ---- Cabecalho
        hdr = tk.Frame(self.root, bg=C_HEADER, height=56)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        tk.Label(hdr, text="🎤", bg=C_HEADER, fg="white",
                 font=("Segoe UI", 20)).pack(side=tk.LEFT, padx=(14, 6), pady=8)
        tk.Label(hdr, text="VozComanda", bg=C_HEADER, fg="white",
                 font=("Segoe UI", 15, "bold")).pack(side=tk.LEFT, pady=8)
        tk.Label(hdr, text="  Ditado por voz para agentes IA", bg=C_HEADER,
                 fg="#93c5fd", font=("Segoe UI", 9)).pack(side=tk.LEFT, anchor=tk.S, pady=14)

        # ---- Linha modelo
        self._frm_mdl = frm_mdl = tk.Frame(self.root, bg=C_PANEL)
        frm_mdl.pack(fill=tk.X)
        b = tk.Frame(frm_mdl, bg=C_BORDER, height=1); b.pack(fill=tk.X); self._borders.append(b)
        self._inner_mdl = inner = tk.Frame(frm_mdl, bg=C_PANEL)
        inner.pack(fill=tk.X, padx=14, pady=8)

        self._lbl_mdl_pfx = tk.Label(inner, text="Modelo:", bg=C_PANEL, fg=C_TEXT,
                 font=("Segoe UI", 10))
        self._lbl_mdl_pfx.pack(side=tk.LEFT)
        self.cmb_modelo = ttk.Combobox(inner, textvariable=self.modelo_sel,
                                       values=opcoes_disponiveis(), state="readonly", width=18)
        self.cmb_modelo.pack(side=tk.LEFT, padx=(8, 6))
        self.cmb_modelo.bind("<<ComboboxSelected>>", lambda e: self._atualizar_info_modelo())

        self.btn_carregar = ttk.Button(inner, text="Usar", command=self.carregar_modelo)
        self.btn_carregar.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_modelo = tk.Label(inner, text="", bg=C_PANEL, fg=C_TEXT2,
                                   font=("Segoe UI", 9))
        self.lbl_modelo.pack(side=tk.LEFT)

        # Botao de configuracao (apenas pasta)
        self.btn_pasta = tk.Button(
            inner, text="⚙", command=self._abrir_menu_config,
            bg=C_PANEL, fg=C_TEXT2,
            activebackground=C_BG, activeforeground=C_TEXT,
            font=("Segoe UI", 10), relief="flat", bd=0,
            padx=4, pady=2, cursor="hand2",
        )
        self.btn_pasta.pack(side=tk.RIGHT, padx=(0, 4))
        self.btn_pasta.bind("<Enter>", lambda e: self.btn_pasta.config(fg=C_TEXT))
        self.btn_pasta.bind("<Leave>", lambda e: self.btn_pasta.config(fg=C_TEXT2))

        # Botao de alternância de tema (🌙 dark / ☀️ light)
        _icone_tema = "🌙" if self._tema == "dark" else "☀️"
        self.btn_tema = tk.Button(
            inner, text=_icone_tema, command=self._toggle_tema,
            bg=C_PANEL, fg=C_TEXT2,
            activebackground=C_BG, activeforeground=C_TEXT,
            font=("Segoe UI", 10), relief="flat", bd=0,
            padx=4, pady=2, cursor="hand2",
        )
        self.btn_tema.pack(side=tk.RIGHT, padx=(0, 2))
        self.btn_tema.bind("<Enter>", lambda e: self.btn_tema.config(fg=C_TEXT))
        self.btn_tema.bind("<Leave>", lambda e: self.btn_tema.config(fg=C_TEXT2))

        # Checkbox pontuacao (direita, antes do botao pasta)
        self.chk_pont = tk.Checkbutton(
            inner, text="Pontuação", variable=self.var_pontuacao,
            command=self._salvar_pontuacao,
            bg=C_PANEL, fg=C_TEXT, activebackground=C_PANEL,
            selectcolor=C_PANEL,
            font=("Segoe UI", 9), cursor="hand2",
        )
        self.chk_pont.pack(side=tk.RIGHT, padx=(0, 8))

        b = tk.Frame(frm_mdl, bg=C_BORDER, height=1); b.pack(fill=tk.X); self._borders.append(b)

        # ---- Linha idioma / traducao
        self._frm_lang = frm_lang = tk.Frame(self.root, bg=C_PANEL)
        frm_lang.pack(fill=tk.X)
        self._inner_lang = inner_lang = tk.Frame(frm_lang, bg=C_PANEL)
        inner_lang.pack(fill=tk.X, padx=14, pady=6)

        self._lbl_idioma_pfx = tk.Label(inner_lang, text="Idioma de voz:", bg=C_PANEL, fg=C_TEXT,
                 font=("Segoe UI", 9))
        self._lbl_idioma_pfx.pack(side=tk.LEFT)
        self.cmb_idioma = ttk.Combobox(
            inner_lang, textvariable=self.var_idioma_voz,
            values=list(IDIOMAS_VOZ.keys()), state="readonly", width=14,
        )
        self.cmb_idioma.pack(side=tk.LEFT, padx=(6, 16))
        self.cmb_idioma.bind("<<ComboboxSelected>>", lambda e: self._salvar_idiomas())

        self.chk_trad = tk.Checkbutton(
            inner_lang, text="Traduzir para:", variable=self.var_traduzir,
            command=self._toggle_traducao,
            bg=C_PANEL, fg=C_TEXT, activebackground=C_PANEL,
            selectcolor=C_PANEL, font=("Segoe UI", 9), cursor="hand2",
        )
        self.chk_trad.pack(side=tk.LEFT)
        self.cmb_alvo = ttk.Combobox(
            inner_lang, textvariable=self.var_idioma_alvo,
            values=list(IDIOMAS_ALVO.keys()), state="readonly", width=12,
        )
        self.cmb_alvo.pack(side=tk.LEFT, padx=(4, 0))
        self.cmb_alvo.bind("<<ComboboxSelected>>", lambda e: self._salvar_idiomas())
        self._toggle_traducao()  # aplica estado inicial (habilita/desabilita combobox)

        b = tk.Frame(frm_lang, bg=C_BORDER, height=1); b.pack(fill=tk.X); self._borders.append(b)

        # ---- Progressbar (oculta por padrao)
        self.progress = ttk.Progressbar(self.root, mode="indeterminate")

        # ---- Controles
        self._frm_ctrl = frm_ctrl = tk.Frame(self.root, bg=C_BG)
        frm_ctrl.pack(fill=tk.X, padx=14, pady=(12, 6))

        self.btn_gravar = tk.Button(
            frm_ctrl,
            text="● Gravar  [F5]",
            command=self.toggle_gravar,
            state=tk.DISABLED,
            bg=C_READY, fg="white",
            activebackground=C_READY_H, activeforeground="white",
            font=("Segoe UI", 11, "bold"),
            relief="flat", bd=0,
            padx=20, pady=9,
            cursor="hand2",
        )
        self.btn_gravar.pack(side=tk.LEFT, padx=(0, 10))
        self.btn_gravar.bind("<Enter>", self._hover_gravar_on)
        self.btn_gravar.bind("<Leave>", self._hover_gravar_off)

        ttk.Separator(frm_ctrl, orient=tk.VERTICAL).pack(
            side=tk.LEFT, fill=tk.Y, padx=8, pady=4)

        self.btn_copiar = ttk.Button(frm_ctrl, text="Copiar", command=self.copiar_texto)
        self.btn_copiar.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_limpar = ttk.Button(frm_ctrl, text="Limpar", command=self.limpar_texto)
        self.btn_limpar.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_traduzir = ttk.Button(frm_ctrl, text="⇔ Traduzir", command=self.traduzir_texto)
        self.btn_traduzir.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_salvar = ttk.Button(frm_ctrl, text="💾 Salvar  [Ctrl+S]",
                                     command=self.salvar_comando)
        self.btn_salvar.pack(side=tk.LEFT)

        # ---- Barra de nivel de audio
        self.cnv_nivel = tk.Canvas(self.root, height=8, bg=C_BG, highlightthickness=0)
        self.cnv_nivel.pack(fill=tk.X, padx=14, pady=(0, 6))
        self._bg_bar  = self.cnv_nivel.create_rectangle(0, 2, 4000, 6, fill=C_BORDER, outline="")
        self._fwd_bar = self.cnv_nivel.create_rectangle(0, 2, 0,    6, fill=C_READY,  outline="")

        # ---- Area de texto
        self._frm_txt = frm_txt = tk.Frame(self.root, bg=C_BG)
        frm_txt.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 6))

        self._lbl_txt_hint = tk.Label(frm_txt, text="Texto transcrito  —  edite se precisar antes de salvar:",
                 bg=C_BG, fg=C_TEXT2, font=("Segoe UI", 9))
        self._lbl_txt_hint.pack(anchor=tk.W, pady=(0, 4))

        self.txt = scrolledtext.ScrolledText(
            frm_txt,
            wrap=tk.WORD,
            font=("Segoe UI", 12),
            height=13,
            bg=C_PANEL, fg=C_TEXT,
            insertbackground=C_INFO,
            selectbackground="#bfdbfe",
            selectforeground=C_TEXT,
            relief="flat", bd=0,
            highlightbackground=C_BORDER,
            highlightcolor=C_INFO,
            highlightthickness=1,
        )
        self.txt.pack(fill=tk.BOTH, expand=True)
        self._criar_menu_contexto()

        # ---- Barra de status
        self.frm_status = tk.Frame(self.root, bg=C_BG)
        self.frm_status.pack(fill=tk.X, side=tk.BOTTOM)
        b = tk.Frame(self.frm_status, bg=C_BORDER, height=1); b.pack(fill=tk.X); self._borders.append(b)
        self.lbl_status = tk.Label(
            self.frm_status, text="Iniciando...",
            bg=C_BG, fg=C_TEXT2,
            font=("Segoe UI", 9),
            anchor=tk.W, padx=14, pady=5,
        )
        self.lbl_status.pack(fill=tk.X)

    def _hover_gravar_on(self, _e=None):
        if not self.gravando and str(self.btn_gravar["state"]) == tk.NORMAL:
            self.btn_gravar.config(bg=C_READY_H)

    def _hover_gravar_off(self, _e=None):
        if not self.gravando and str(self.btn_gravar["state"]) == tk.NORMAL:
            self.btn_gravar.config(bg=C_READY)

    # ---------------------------------------------------------------- atalhos
    def _bind_atalhos(self):
        self.root.bind("<F5>", lambda e: self._atalho_gravar())
        self.root.bind("<Control-s>", lambda e: self.salvar_comando())
        self.root.bind("<Control-S>", lambda e: self.salvar_comando())
        self.root.bind("<Control-l>", lambda e: self.limpar_texto())
        self.root.bind("<Control-L>", lambda e: self.limpar_texto())
        # Space so dispara se o foco NAO estiver na caixa de texto
        self.root.bind("<space>", lambda e: self._atalho_space(e))

    def _atalho_gravar(self):
        if str(self.btn_gravar["state"]) == tk.NORMAL:
            self.toggle_gravar()

    def _atalho_space(self, event):
        if event.widget is not self.txt:
            self._atalho_gravar()

    # ---------------------------------------------------------------- status
    _STATUS_COR = {
        "ok":   (C_OK,   "#f0fdf4"),
        "info": (C_INFO, "#eff6ff"),
        "warn": (C_WARN, "#fffbeb"),
        "err":  (C_ERR,  "#fef2f2"),
        "idle": (C_TEXT2, C_BG),
    }

    def set_status(self, msg, tipo="idle"):
        fg, bg = self._STATUS_COR.get(tipo, (C_TEXT2, C_BG))
        self.lbl_status.config(text=f"  {msg}", fg=fg, bg=bg)
        self.frm_status.config(bg=bg)

    # ---------------------------------------------------------------- nivel
    def _set_nivel(self, val: float):
        w = self.cnv_nivel.winfo_width()
        if w < 4:
            return
        preenchido = max(0, min(int(w * val), w))
        cor = C_REC if self.gravando else C_READY
        self.cnv_nivel.coords(self._bg_bar,  0, 2, w,          6)
        self.cnv_nivel.coords(self._fwd_bar, 0, 2, preenchido, 6)
        self.cnv_nivel.itemconfig(self._fwd_bar, fill=cor)

    # ---------------------------------------------------------------- modelo
    def _atualizar_info_modelo(self):
        nome = self.modelo_sel.get()
        if nome == ONLINE:
            self.lbl_modelo.config(text="☁ online — sem download, precisa de internet",
                                   fg="#1d4ed8")
            self.btn_carregar.config(text="Usar")
        elif modelo_baixado(nome):
            self.lbl_modelo.config(text="✔ ja baixado", fg=C_OK)
            self.btn_carregar.config(text="Carregar")
        else:
            self.lbl_modelo.config(
                text=f"↓ nao baixado ({MODELOS.get(nome, '?')})", fg=C_WARN)
            self.btn_carregar.config(text="Baixar e carregar")

    def _habilitar_seletor(self, on: bool):
        self.cmb_modelo.config(state="readonly" if on else "disabled")
        self.btn_carregar.config(state=tk.NORMAL if on else tk.DISABLED)

    def _salvar_pontuacao(self):
        cfg = carregar_config()
        cfg["pontuacao"] = self.var_pontuacao.get()
        salvar_config(cfg)

    def _salvar_idiomas(self):
        cfg = carregar_config()
        cfg["idioma_voz"]  = self.var_idioma_voz.get()
        cfg["idioma_alvo"] = self.var_idioma_alvo.get()
        salvar_config(cfg)

    def _toggle_traducao(self):
        estado = "readonly" if self.var_traduzir.get() else "disabled"
        self.cmb_alvo.config(state=estado)
        cfg = carregar_config()
        cfg["traduzir"] = self.var_traduzir.get()
        salvar_config(cfg)

    # ---------------------------------------------------------------- traducao
    @staticmethod
    def _detectar_idioma(texto: str) -> str:
        """Detecta PT ou EN por contagem de palavras frequentes — sem API."""
        palavras = re.findall(r"\w+", texto.lower())
        pt = sum(p in _PALAVRAS_PT for p in palavras)
        en = sum(p in _PALAVRAS_EN for p in palavras)
        return "pt" if pt >= en else "en"

    def _garantir_email_mm(self):
        """Na primeira traducao, oferece informar um e-mail (MyMemory: 5.000 -> 50.000 caracteres/dia)."""
        if self._mm_email is not None:
            return
        while True:
            email = simpledialog.askstring(
                "Limite de tradução",
                "O tradutor gratuito (MyMemory) permite 5.000 caracteres por dia.\n"
                "Informando um e-mail, o limite sobe para 50.000.\n"
                "O e-mail é enviado ao MyMemory junto com cada tradução.\n\n"
                "E-mail (opcional — deixe em branco para pular):",
                parent=self.root,
            )
            email = (email or "").strip()
            if not email or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                break
            messagebox.showwarning("E-mail inválido",
                                   "Digite um e-mail válido ou deixe em branco para pular.",
                                   parent=self.root)
        self._mm_email = email
        cfg = carregar_config()
        cfg["mm_email"] = email
        salvar_config(cfg)

    @staticmethod
    def _traduzir_bloco(texto: str, de: str, para: str, email=None) -> str:
        """MyMemory primeiro; GoogleTranslator de reserva (hoje bloqueado, pode voltar)."""
        from deep_translator import GoogleTranslator, MyMemoryTranslator
        try:
            resultado = MyMemoryTranslator(source=de, target=para, email=email).translate(texto) or texto
            # MyMemory devolve erros como se fossem a traducao, em maiusculas
            if resultado.startswith("MYMEMORY WARNING"):
                raise RuntimeError("limite diário gratuito do MyMemory atingido — tente amanhã")
            if "INVALID" in resultado and resultado.isupper():
                raise RuntimeError(f"MyMemory recusou o pedido: {resultado[:80]}")
            return resultado
        except Exception as erro_mm:
            g_de, g_para = (c if c.startswith("zh") else c.split("-")[0] for c in (de, para))
            try:
                return GoogleTranslator(source=g_de, target=g_para).translate(texto) or texto
            except Exception:
                raise erro_mm from None

    def _fazer_traducao(self, texto: str, de: str, para: str) -> str:
        """Traduz em blocos de ate 480 caracteres, preservando as quebras de linha."""
        saida = []
        for sep, bloco in _dividir_texto(texto):
            nucleo = bloco.strip()
            if nucleo:
                ini = bloco[:len(bloco) - len(bloco.lstrip())]
                fim = bloco[len(bloco.rstrip()):]
                bloco = ini + self._traduzir_bloco(nucleo, de, para, self._mm_email or None) + fim
            saida.append(sep + bloco)
        return "".join(saida)

    def _aplicar_traducao_voz(self, texto: str) -> str:
        """Traduz o texto transcrito se o toggle de traducao estiver ativo."""
        if not self.var_traduzir.get() or not texto:
            return texto
        idioma_entry = IDIOMAS_VOZ.get(self.var_idioma_voz.get(), {})
        de   = idioma_entry.get("mm", "pt-BR")
        para = IDIOMAS_ALVO.get(self.var_idioma_alvo.get(), "en-GB")
        if de == para:
            return texto
        return self._fazer_traducao(texto, de, para)

    def traduzir_texto(self):
        """Detecta o idioma do texto na caixa e traduz PT<->EN automaticamente."""
        texto = self.txt.get("1.0", tk.END).strip()
        if not texto:
            self.set_status("Nada para traduzir.", "warn")
            return
        self._garantir_email_mm()
        self.set_status("Traduzindo...", "info")
        self.btn_traduzir.config(state=tk.DISABLED)

        def _do():
            try:
                # MyMemory nao aceita origem "auto": a deteccao local decide a direcao
                if self._detectar_idioma(texto) == "pt":
                    de, para, rotulo = "pt-BR", "en-GB", "PT → EN"
                else:
                    de, para, rotulo = "en-GB", "pt-BR", "EN → PT"
                resultado = self._fazer_traducao(texto, de, para)
                self.root.after(0, lambda: self._mostrar_traducao(resultado, rotulo))
            except Exception as exc:
                msg = str(exc)
                self.root.after(0, lambda: self._erro_traducao(msg))

        threading.Thread(target=_do, daemon=True).start()

    def _mostrar_traducao(self, texto: str, rotulo: str):
        self.txt.delete("1.0", tk.END)
        self.txt.insert(tk.END, texto)
        self.txt.see(tk.END)
        self.btn_traduzir.config(state=tk.NORMAL)
        self.set_status(f"Texto traduzido ({rotulo}).", "ok")

    def _erro_traducao(self, erro: str):
        self.btn_traduzir.config(state=tk.NORMAL)
        self.set_status(f"Erro na tradução: {erro}", "err")

    def _obter_save_dir(self) -> str:
        """Retorna o diretorio de saida, pedindo ao usuario na primeira vez."""
        if self._save_dir:
            return self._save_dir
        from tkinter import filedialog
        pasta = filedialog.askdirectory(
            title="Escolha a pasta onde VozComanda vai salvar os arquivos",
            initialdir=BASE_DIR,
        )
        if not pasta:
            return BASE_DIR
        self._save_dir = pasta
        cfg = carregar_config()
        cfg["save_dir"] = pasta
        salvar_config(cfg)
        return pasta

    def _trocar_pasta(self):
        from tkinter import filedialog
        pasta = filedialog.askdirectory(
            title="Trocar pasta de saida do VozComanda",
            initialdir=self._save_dir or BASE_DIR,
        )
        if not pasta:
            return
        self._save_dir = pasta
        cfg = carregar_config()
        cfg["save_dir"] = pasta
        salvar_config(cfg)
        self.set_status(f"Pasta de saida: {pasta}", "ok")

    def _abrir_menu_config(self):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Trocar pasta de salvamento", command=self._trocar_pasta)
        x = self.btn_pasta.winfo_rootx()
        y = self.btn_pasta.winfo_rooty() + self.btn_pasta.winfo_height()
        menu.tk_popup(x, y)

    def _toggle_tema(self):
        self._trocar_tema("light" if self._tema == "dark" else "dark")

    def _trocar_tema(self, tema):
        if tema == self._tema:
            return
        self._aplicar_tema(tema)
        self._recolorir_ui()
        cfg = carregar_config()
        cfg["tema"] = tema
        salvar_config(cfg)

    def _recolorir_ui(self):
        p = PALETA[self._tema]
        sel = p["C_SEL"]
        # Frames principais
        self._frm_mdl.configure(bg=C_PANEL)
        self._inner_mdl.configure(bg=C_PANEL)
        self._frm_lang.configure(bg=C_PANEL)
        self._inner_lang.configure(bg=C_PANEL)
        self._frm_ctrl.configure(bg=C_BG)
        self._frm_txt.configure(bg=C_BG)
        self.frm_status.configure(bg=C_BG)
        # Separadores
        for b in self._borders:
            b.configure(bg=C_BORDER)
        # Labels
        self._lbl_mdl_pfx.configure(bg=C_PANEL, fg=C_TEXT)
        self._lbl_idioma_pfx.configure(bg=C_PANEL, fg=C_TEXT)
        self._lbl_txt_hint.configure(bg=C_BG, fg=C_TEXT2)
        self.lbl_modelo.configure(bg=C_PANEL)
        self.lbl_status.configure(bg=C_BG, fg=C_TEXT2)
        # Botoes gear e tema, e checkboxes
        self.btn_pasta.configure(bg=C_PANEL, fg=C_TEXT2,
                                 activebackground=C_BG, activeforeground=C_TEXT)
        self.btn_pasta.bind("<Leave>", lambda e: self.btn_pasta.config(fg=C_TEXT2))
        self.btn_pasta.bind("<Enter>", lambda e: self.btn_pasta.config(fg=C_TEXT))
        _icone = "🌙" if self._tema == "dark" else "☀️"
        self.btn_tema.configure(bg=C_PANEL, fg=C_TEXT2, text=_icone,
                                activebackground=C_BG, activeforeground=C_TEXT)
        self.btn_tema.bind("<Leave>", lambda e: self.btn_tema.config(fg=C_TEXT2))
        self.btn_tema.bind("<Enter>", lambda e: self.btn_tema.config(fg=C_TEXT))
        for chk in (self.chk_pont, self.chk_trad):
            chk.configure(bg=C_PANEL, fg=C_TEXT, activebackground=C_PANEL, selectcolor=C_PANEL)
        # Canvas de nivel
        self.cnv_nivel.configure(bg=C_BG)
        self.cnv_nivel.itemconfig(self._bg_bar, fill=C_BORDER)
        # Caixa de texto
        self.txt.configure(bg=C_PANEL, fg=C_TEXT,
                           insertbackground=C_INFO,
                           selectbackground=sel, selectforeground=C_TEXT,
                           highlightbackground=C_BORDER, highlightcolor=C_INFO)

    def carregar_modelo(self):
        if self.carregando or self.gravando:
            return
        nome = self.modelo_sel.get()
        if self.modelo_atual == nome:
            self.set_status(f"'{nome}' ja esta em uso.", "ok")
            return
        if nome == ONLINE:
            self.model = None
            self.modelo_atual = ONLINE
            gc.collect()
            cfg = carregar_config()
            cfg["modelo"] = ONLINE
            salvar_config(cfg)
            self._atualizar_info_modelo()
            self.set_status("Pronto — Google online. Clique em Gravar ou pressione F5.", "ok")
            self.btn_gravar.config(state=tk.NORMAL)
            return

        baixado = modelo_baixado(nome)
        self.carregando = True
        self.model = None
        self.modelo_atual = None
        gc.collect()
        self._habilitar_seletor(False)
        self.btn_gravar.config(state=tk.DISABLED)
        self.progress.pack(fill=tk.X, padx=14, pady=(0, 2), before=self.frm_status)
        self.progress.start(12)
        if baixado:
            self.set_status(f"Carregando '{nome}'...", "info")
        else:
            self.set_status(
                f"Baixando '{nome}' ({MODELOS.get(nome, '?')}) — aguarde, nao feche...",
                "info")

        def _load():
            try:
                os.makedirs(MODEL_CACHE, exist_ok=True)
                m = WhisperModel(nome, device="cpu", compute_type="int8",
                                 download_root=MODEL_CACHE)
                self.root.after(0, lambda: self._modelo_pronto(nome, m))
            except Exception as exc:
                msg = str(exc)
                self.root.after(0, lambda: self._modelo_erro(nome, msg))

        threading.Thread(target=_load, daemon=True).start()

    def _fim_carregamento(self):
        self.carregando = False
        self.progress.stop()
        self.progress.pack_forget()
        self._habilitar_seletor(True)
        self._atualizar_info_modelo()

    def _modelo_pronto(self, nome, modelo):
        self.model = modelo
        self.modelo_atual = nome
        self._fim_carregamento()
        cfg = carregar_config()
        cfg["modelo"] = nome
        salvar_config(cfg)
        self.set_status(f"Pronto — modelo '{nome}'. Clique em Gravar ou pressione F5.", "ok")
        self.btn_gravar.config(state=tk.NORMAL)

    def _modelo_erro(self, nome, erro):
        self._fim_carregamento()
        self.set_status(f"Erro ao carregar '{nome}': {erro}", "err")

    # ---------------------------------------------------------------- gravacao
    def toggle_gravar(self):
        if self.gravando:
            self.parar_e_transcrever()
        else:
            self.iniciar_gravacao()

    def iniciar_gravacao(self):
        if self.modelo_atual is None:
            return
        with self.audio_q.mutex:
            self.audio_q.queue.clear()
        self.gravando = True
        self._habilitar_seletor(False)
        self.btn_gravar.config(text="■ Parar  [F5]", bg=C_REC, activebackground=C_REC_DK)
        self.set_status("Gravando... fale e pressione F5 ou clique em Parar.", "warn")
        self._pulso = True
        self._animar_gravar()

        def _cb(indata, frames, time_info, status):
            self.audio_q.put(indata.copy())
            rms = float(np.sqrt(np.mean(indata ** 2)))
            nivel = min(rms * 10.0, 1.0)
            self.root.after(0, lambda: self._set_nivel(nivel))

        try:
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE, blocksize=BLOCK,
                dtype="float32", channels=1, callback=_cb)
            self.stream.start()
        except Exception as exc:
            self.gravando = False
            self._habilitar_seletor(True)
            self.btn_gravar.config(text="● Gravar  [F5]", bg=C_READY,
                                   activebackground=C_READY_H)
            messagebox.showerror("Erro de microfone", str(exc))
            self.set_status("Erro ao abrir o microfone.", "err")

    def _animar_gravar(self):
        if not self.gravando:
            return
        self._pulso = not self._pulso
        cor = C_REC if self._pulso else C_REC_LT
        self.btn_gravar.config(bg=cor)
        self.root.after(550, self._animar_gravar)

    def parar_e_transcrever(self):
        self.gravando = False
        self.btn_gravar.config(state=tk.DISABLED, text="● Gravar  [F5]",
                               bg=C_TRAN, activebackground=C_TRAN)
        self.set_status("Transcrevendo...", "info")
        self._set_nivel(0)
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        # Dialogo precisa da thread principal; o audio ja esta na fila
        if self.var_traduzir.get():
            self._garantir_email_mm()
        threading.Thread(target=self._transcrever, daemon=True).start()

    def _transcrever(self):
        blocos = []
        while not self.audio_q.empty():
            blocos.append(self.audio_q.get())
        if not blocos:
            self.root.after(0, lambda: self._mostrar_texto(""))
            return

        audio_bruto = np.concatenate(blocos, axis=0).flatten().astype(np.float32)
        # Normaliza volume: melhora reconhecimento tanto no Google quanto no Whisper
        audio_norm = _normalizar_audio(audio_bruto)
        # Padding de silencio: evita que o decodificador corte inicio e fim das palavras
        silencio_ini = np.zeros(PAD_INICIO, dtype=np.float32)
        silencio_fim = np.zeros(PAD_FIM,    dtype=np.float32)
        audio = np.concatenate([silencio_ini, audio_norm, silencio_fim])

        modo   = self.modelo_atual
        modelo = self.model
        try:
            if modo == ONLINE:
                texto = self._transcrever_google(audio)
            else:
                texto = self._transcrever_whisper(modelo, audio)
        except sr.UnknownValueError:
            texto = ""
        except sr.RequestError as exc:
            erro = (f"sem conexao com o Google ({exc}). "
                    f"Verifique a internet ou use um modelo offline.")
            self.root.after(0, lambda: self._erro_transcricao(erro))
            return
        except Exception as exc:
            msg = str(exc)
            self.root.after(0, lambda: self._erro_transcricao(msg))
            return
        # Falha na traducao nao pode descartar o que foi ditado
        aviso = None
        if texto:
            try:
                texto = self._aplicar_traducao_voz(texto)
            except Exception as exc:
                aviso = f"Tradução falhou ({exc}). Mostrando o texto original."
        self.root.after(0, lambda: self._mostrar_texto(texto, aviso))

    def _transcrever_google(self, audio: np.ndarray) -> str:
        """Envia o audio normalizado ao Google (sem criar arquivo no disco)."""
        audio_int16 = (audio * 32767).astype(np.int16)
        dados = sr.AudioData(audio_int16.tobytes(), SAMPLE_RATE, 2)
        r = sr.Recognizer()
        r.operation_timeout = 30
        # show_all=False: retorna a transcricao de maior confianca
        lang_google = IDIOMAS_VOZ.get(self.var_idioma_voz.get(), {}).get("google", "pt-BR")
        texto = r.recognize_google(dados, language=lang_google, show_all=False)
        if self.var_pontuacao.get():
            texto = _aplicar_pontuacao_google(texto)
        return texto

    def _transcrever_whisper(self, modelo, audio: np.ndarray) -> str:
        """Transcreve com faster-whisper. beam_size=5 equilibra velocidade e precisao."""
        lang_whisper = IDIOMAS_VOZ.get(self.var_idioma_voz.get(), {}).get("whisper", "pt")
        segs, _info = modelo.transcribe(
            audio,
            language=lang_whisper,
            beam_size=5,          # era 8 — mais rapido, qualidade equivalente
            vad_filter=True,
            vad_parameters=VAD_PARAMS,
            initial_prompt=PROMPT_PT,
            condition_on_previous_text=False,
            temperature=0.0,      # decodificacao gulosa: mais rapida e menos alucinacoes
            no_speech_threshold=0.45,
        )
        texto = " ".join(s.text.strip() for s in segs).strip()
        if not self.var_pontuacao.get():
            texto = _remover_pontuacao(texto)
        return texto

    def _erro_transcricao(self, erro):
        self.set_status(f"Erro na transcricao: {erro}", "err")
        self.btn_gravar.config(state=tk.NORMAL, bg=C_READY, activebackground=C_READY_H)
        self._habilitar_seletor(True)

    def _mostrar_texto(self, texto, aviso=None):
        if texto:
            atual = self.txt.get("1.0", tk.END).strip()
            sep = "\n" if atual else ""
            self.txt.insert(tk.END, sep + texto)
            self.txt.see(tk.END)
            if aviso:
                self.set_status(aviso, "warn")
            else:
                self.set_status("Transcrito. Edite se precisar e pressione Ctrl+S para salvar.", "ok")
        else:
            self.set_status(
                "Nada reconhecido. Tente novamente — fale mais perto do microfone.", "warn")
        self.btn_gravar.config(state=tk.NORMAL, bg=C_READY, activebackground=C_READY_H)
        self._habilitar_seletor(True)

    # ---------------------------------------------------------------- menu contexto
    def _criar_menu_contexto(self):
        m = tk.Menu(self.txt, tearoff=0)
        m.add_command(label="Recortar",       command=lambda: self.txt.event_generate("<<Cut>>"))
        m.add_command(label="Copiar",         command=lambda: self.txt.event_generate("<<Copy>>"))
        m.add_command(label="Colar",          command=lambda: self.txt.event_generate("<<Paste>>"))
        m.add_separator()
        m.add_command(label="Selecionar tudo", command=self._sel_tudo)
        self.menu_ctx = m
        self.txt.bind("<Button-3>", self._mostrar_ctx)

    def _sel_tudo(self):
        self.txt.tag_add(tk.SEL, "1.0", tk.END)
        self.txt.focus_set()

    def _mostrar_ctx(self, event):
        self.txt.focus_set()
        tem = bool(self.txt.tag_ranges(tk.SEL))
        for label in ("Recortar", "Copiar"):
            self.menu_ctx.entryconfig(label, state=tk.NORMAL if tem else tk.DISABLED)
        try:
            self.menu_ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu_ctx.grab_release()

    # ---------------------------------------------------------------- acoes
    def copiar_texto(self):
        texto = self.txt.get("1.0", tk.END).strip()
        if not texto:
            self.set_status("Nada para copiar.", "warn")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(texto)
        self.root.update()
        self.set_status("Texto copiado para a area de transferencia.", "ok")

    def limpar_texto(self):
        self.txt.delete("1.0", tk.END)
        self._set_nivel(0)
        self.set_status("Texto limpo.", "idle")

    def salvar_comando(self):
        texto = self.txt.get("1.0", tk.END).strip()
        if not texto:
            messagebox.showwarning("Vazio", "Nao ha texto para salvar.")
            return
        save_dir   = self._obter_save_dir()
        cmd_path   = os.path.join(save_dir, "comando.txt")
        hist_dir   = os.path.join(save_dir, "historico")
        try:
            with open(cmd_path, "w", encoding="utf-8") as f:
                f.write(texto + "\n")
            os.makedirs(hist_dir, exist_ok=True)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            with open(os.path.join(hist_dir, f"comando_{ts}.txt"), "w", encoding="utf-8") as f:
                f.write(texto + "\n")
        except Exception as exc:
            messagebox.showerror("Erro ao salvar", str(exc))
            return
        pasta_nome = os.path.basename(save_dir) or save_dir
        self.set_status(
            f"Salvo em '{pasta_nome}/comando.txt'.  Peca ao Kiro: 'le o comando.txt e executa'.",
            "ok")


def main():
    root = tk.Tk()
    VozComandaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
