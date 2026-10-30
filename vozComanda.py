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
WINDOWS = sys.platform == "win32"
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
    BASE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", APP_DIR), "VozComanda")
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    # No snap a pasta do app e somente leitura; SNAP_USER_COMMON vale para todas as
    # revisoes, entao os modelos (ate 3 GB) nao se repetem a cada atualizacao.
    BASE_DIR = os.environ.get("SNAP_USER_COMMON") or APP_DIR
BASE_DIR = os.environ.get("VOZ_DATA_DIR") or BASE_DIR
os.makedirs(BASE_DIR, exist_ok=True)

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
    MODELOS[MODEL_SIZE] = "?"

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
    "pt-BR": {"whisper": "pt", "google": "pt-BR", "mm": "pt-BR"},
    "pt-PT": {"whisper": "pt", "google": "pt-PT", "mm": "pt-PT"},
    "en":    {"whisper": "en", "google": "en-US", "mm": "en-GB"},
    "es":    {"whisper": "es", "google": "es-ES", "mm": "es-ES"},
    "fr":    {"whisper": "fr", "google": "fr-FR", "mm": "fr-FR"},
    "de":    {"whisper": "de", "google": "de-DE", "mm": "de-DE"},
    "it":    {"whisper": "it", "google": "it-IT", "mm": "it-IT"},
    "ja":    {"whisper": "ja", "google": "ja-JP", "mm": "ja-JP"},
    "zh":    {"whisper": "zh", "google": "zh-CN", "mm": "zh-CN"},
    "ar":    {"whisper": "ar", "google": "ar-SA", "mm": "ar-SA"},
}

IDIOMAS_ALVO = {
    "pt": "pt-BR",
    "en": "en-GB",
    "es": "es-ES",
    "fr": "fr-FR",
    "de": "de-DE",
    "it": "it-IT",
    "ja": "ja-JP",
    "zh": "zh-CN",
    "ar": "ar-SA",
}

# Nome de cada idioma na interface: (pt, en, es). O nome em PT tambem reconhece
# o config.json das versoes antigas, que guardava o nome em vez do codigo.
NOMES_IDIOMA = {
    "pt-BR": ("Português BR", "Portuguese (BR)", "Portugués (BR)"),
    "pt-PT": ("Português PT", "Portuguese (PT)", "Portugués (PT)"),
    "pt":    ("Português",    "Portuguese",      "Portugués"),
    "en":    ("Inglês",       "English",         "Inglés"),
    "es":    ("Espanhol",     "Spanish",         "Español"),
    "fr":    ("Francês",      "French",          "Francés"),
    "de":    ("Alemão",       "German",          "Alemán"),
    "it":    ("Italiano",     "Italian",         "Italiano"),
    "ja":    ("Japonês",      "Japanese",        "Japonés"),
    "zh":    ("Chinês",       "Chinese",         "Chino"),
    "ar":    ("Árabe",        "Arabic",          "Árabe"),
}
IDIOMAS_UI = ("pt", "en", "es")

# Leitura em voz alta. Online: vozes neurais do Microsoft Edge (edge-tts).
# Offline: vozes do Windows (SAPI), escolhidas pelo LCID do idioma.
VOZES_ONLINE = {
    "pt-BR": "pt-BR-FranciscaNeural", "pt-PT": "pt-PT-RaquelNeural",
    "en": "en-US-AriaNeural", "es": "es-ES-ElviraNeural", "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural", "it": "it-IT-ElsaNeural", "ja": "ja-JP-NanamiNeural",
    "zh": "zh-CN-XiaoxiaoNeural", "ar": "ar-SA-ZariyahNeural",
}
LCID_WINDOWS = {
    "pt-BR": 0x416, "pt-PT": 0x816, "en": 0x409, "es": 0xC0A, "fr": 0x40C,
    "de": 0x407, "it": 0x410, "ja": 0x411, "zh": 0x804, "ar": 0x401,
}
VOZES_ESPEAK = {   # voz offline no Linux (espeak-ng)
    "pt-BR": "pt-br", "pt-PT": "pt", "en": "en-us", "es": "es", "fr": "fr",
    "de": "de", "it": "it", "ja": "ja", "zh": "cmn", "ar": "ar",
}
TAXA_VOZ = 24000   # Hz do audio decodificado da voz online

# O Tk do Linux mostra emoji como quadrados (ou trava com emoji colorido):
# fora do Windows eles viram simbolos que as fontes comuns tem.
EMOJI_LINUX = {"🔊 ": "", "💾 ": "", "🎤": "", "🌙": "☾", "☀️": "☀"}


def _sem_emoji(texto: str) -> str:
    if WINDOWS:
        return texto
    for emoji, troca in EMOJI_LINUX.items():
        texto = texto.replace(emoji, troca)
    return texto


def _codigo_idioma(valor, tabela, padrao):
    """Codigo do idioma salvo no config: aceita o codigo ou o nome em PT das versoes antigas."""
    if valor in tabela:
        return valor
    for cod in tabela:
        if NOMES_IDIOMA[cod][0] == valor:
            return cod
    return padrao


def _idioma_sistema() -> str:
    """Idioma da interface do Windows (pt, en ou es); ingles para os demais."""
    try:
        import ctypes
        lid = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        return {0x16: "pt", 0x0A: "es", 0x09: "en"}.get(lid, "en")
    except Exception:
        import locale
        loc = (locale.getlocale()[0] or "").lower()
        return next((c for c in IDIOMAS_UI if loc.startswith(c)), "en")


# Palavras frequentes usadas para detectar se o texto esta em ingles sem chamar
# servico externo. Ficam de fora as que existem em mais de um idioma ("a", "no", "do").
_PALAVRAS_PT = {
    "de", "o", "e", "que", "em", "um", "uma", "para", "com", "não", "na",
    "da", "os", "se", "por", "mais", "dos", "das", "mas", "ao", "nos", "nas",
    "seu", "sua", "foi", "ser", "ter", "está", "são", "você", "isso", "como",
    "quando", "muito", "já", "também", "pode",
}
_PALAVRAS_ES = {
    "el", "la", "los", "las", "y", "en", "un", "una", "con", "del", "al",
    "es", "lo", "se", "su", "sus", "pero", "más", "muy", "está", "son", "esto",
    "cuando", "también", "puede", "hay", "ya", "porque", "usted", "tú",
}
_PALAVRAS_EN = {
    "the", "is", "are", "was", "were", "be", "been", "have", "has", "had",
    "does", "did", "will", "would", "could", "should", "of", "in", "on",
    "at", "to", "for", "with", "by", "this", "that", "it", "an", "and", "or",
    "you", "your", "from", "they", "there", "which", "what", "when",
}

# MyMemory recusa requisicoes acima de 500 caracteres.
_LIMITE_MM = 480

# ------------------------------------------------------------------ textos da interface
TEXTS = {
    "pt": {
        "hdr_sub":          "  Ditado por voz para agentes IA",
        "lbl_modelo":       "Modelo:",
        "lbl_idioma":       "Idioma de voz:",
        "chk_pont":         "Pontuação",
        "chk_trad":         "Traduzir para:",
        "btn_gravar":       "● Gravar  [F5]",
        "btn_parar":        "■ Parar  [F5]",
        "btn_copiar":       "Copiar",
        "btn_limpar":       "Limpar",
        "btn_traduzir":     "⇔ Traduzir",
        "btn_salvar":       "💾 Salvar  [Ctrl+S]",
        "txt_hint":         "Texto transcrito  —  edite se precisar antes de salvar:",
        "btn_usar":         "Usar",
        "btn_carregar":     "Carregar",
        "btn_baixar":       "Baixar e carregar",
        "mdl_online":       "☁ online — sem download, precisa de internet",
        "mdl_baixado":      "✔ já baixado",
        "mdl_nao_baixado":  "↓ não baixado ({tam})",
        "menu_pasta":       "Trocar pasta de salvamento",
        "ctx_recortar":     "Recortar",
        "ctx_copiar":       "Copiar",
        "ctx_colar":        "Colar",
        "ctx_sel_tudo":     "Selecionar tudo",
        "dlg_email_t":      "Limite de tradução",
        "dlg_email":        "O tradutor gratuito (MyMemory) permite 5.000 caracteres por dia.\n"
                            "Informando um e-mail, o limite sobe para 50.000.\n"
                            "O e-mail é enviado ao MyMemory junto com cada tradução.\n\n"
                            "E-mail (opcional — deixe em branco para pular):",
        "dlg_email_inv_t":  "E-mail inválido",
        "dlg_email_inv":    "Digite um e-mail válido ou deixe em branco para pular.",
        "dlg_pasta":        "Escolha a pasta onde o VozComanda vai salvar os arquivos",
        "dlg_trocar_pasta": "Trocar pasta de saída do VozComanda",
        "dlg_erro_mic":     "Erro de microfone",
        "dlg_vazio_t":      "Vazio",
        "dlg_vazio":        "Não há texto para salvar.",
        "dlg_erro_salvar":  "Erro ao salvar",
        "err_mm_limite":    "limite diário gratuito do MyMemory atingido — tente amanhã",
        "err_mm_recusou":   "MyMemory recusou o pedido: {msg}",
        "err_google":       "sem conexão com o Google ({exc}). Verifique a internet ou use um modelo offline.",
        "st_iniciando":     "Iniciando...",
        "st_nao_baixado":   "Modelo '{nome}' não baixado. Escolha um e clique em 'Baixar e carregar'.",
        "st_nada_traduzir": "Nada para traduzir.",
        "st_traduzindo":    "Traduzindo...",
        "st_traduzido":     "Texto traduzido ({rotulo}).",
        "st_erro_trad":     "Erro na tradução: {erro}",
        "st_pasta":         "Pasta de saída: {pasta}",
        "st_em_uso":        "'{nome}' já está em uso.",
        "st_pronto_online": "Pronto — Google online. Clique em Gravar ou pressione F5.",
        "st_carregando":    "Carregando '{nome}'...",
        "st_baixando":      "Baixando '{nome}' ({tam}) — aguarde, não feche...",
        "st_pronto_modelo": "Pronto — modelo '{nome}'. Clique em Gravar ou pressione F5.",
        "st_erro_modelo":   "Erro ao carregar '{nome}': {erro}",
        "st_gravando":      "Gravando... fale e pressione F5 ou clique em Parar.",
        "st_erro_mic":      "Erro ao abrir o microfone.",
        "st_transcrevendo": "Transcrevendo...",
        "st_aviso_trad":    "Tradução falhou ({exc}). Mostrando o texto original.",
        "st_erro_transc":   "Erro na transcrição: {erro}",
        "st_transcrito":    "Transcrito. Edite se precisar e pressione Ctrl+S para salvar.",
        "st_nada_reconh":   "Nada reconhecido. Tente novamente — fale mais perto do microfone.",
        "st_nada_copiar":   "Nada para copiar.",
        "st_copiado":       "Texto copiado para a área de transferência.",
        "st_limpo":         "Texto limpo.",
        "st_salvo":         "Salvo em '{pasta}/comando.txt'.  Peça ao agente: 'lê o comando.txt e executa'.",
        "st_idioma":        "Idioma da interface: Português.",
        "btn_ouvir":        "🔊 Ouvir  [F6]",
        "btn_parar_voz":    "■ Parar voz  [F6]",
        "st_nada_ouvir":    "Nada para ler.",
        "st_gerando_voz":   "Gerando a voz...",
        "st_lendo":         "Lendo em voz alta ({idioma}). F6 para parar.",
        "st_lendo_offline": "Sem conexão com a voz online — lendo com a voz do sistema ({idioma}).",
        "st_sem_espeak":    "Nenhuma voz offline instalada. Instale com: sudo apt install espeak-ng, ou use o modo Google online.",
        "st_sem_voz":       "Nenhuma voz do Windows para {idioma}. Instale em Configurações > Hora e idioma > Fala, ou use o modo Google online.",
        "st_erro_voz":      "Erro ao ler o texto: {erro}",
    },
    "en": {
        "hdr_sub":          "  Voice dictation for AI agents",
        "lbl_modelo":       "Model:",
        "lbl_idioma":       "Voice language:",
        "chk_pont":         "Punctuation",
        "chk_trad":         "Translate to:",
        "btn_gravar":       "● Record  [F5]",
        "btn_parar":        "■ Stop  [F5]",
        "btn_copiar":       "Copy",
        "btn_limpar":       "Clear",
        "btn_traduzir":     "⇔ Translate",
        "btn_salvar":       "💾 Save  [Ctrl+S]",
        "txt_hint":         "Transcribed text  —  edit it if needed before saving:",
        "btn_usar":         "Use",
        "btn_carregar":     "Load",
        "btn_baixar":       "Download and load",
        "mdl_online":       "☁ online — no download, needs internet",
        "mdl_baixado":      "✔ downloaded",
        "mdl_nao_baixado":  "↓ not downloaded ({tam})",
        "menu_pasta":       "Change save folder",
        "ctx_recortar":     "Cut",
        "ctx_copiar":       "Copy",
        "ctx_colar":        "Paste",
        "ctx_sel_tudo":     "Select all",
        "dlg_email_t":      "Translation limit",
        "dlg_email":        "The free translator (MyMemory) allows 5,000 characters a day.\n"
                            "With an e-mail address the limit goes up to 50,000.\n"
                            "The e-mail is sent to MyMemory with each translation.\n\n"
                            "E-mail (optional — leave blank to skip):",
        "dlg_email_inv_t":  "Invalid e-mail",
        "dlg_email_inv":    "Enter a valid e-mail or leave it blank to skip.",
        "dlg_pasta":        "Choose the folder where VozComanda saves its files",
        "dlg_trocar_pasta": "Change VozComanda's output folder",
        "dlg_erro_mic":     "Microphone error",
        "dlg_vazio_t":      "Empty",
        "dlg_vazio":        "There is no text to save.",
        "dlg_erro_salvar":  "Error saving",
        "err_mm_limite":    "MyMemory free daily limit reached — try again tomorrow",
        "err_mm_recusou":   "MyMemory refused the request: {msg}",
        "err_google":       "no connection to Google ({exc}). Check your internet or use an offline model.",
        "st_iniciando":     "Starting...",
        "st_nao_baixado":   "Model '{nome}' is not downloaded. Pick one and click 'Download and load'.",
        "st_nada_traduzir": "Nothing to translate.",
        "st_traduzindo":    "Translating...",
        "st_traduzido":     "Text translated ({rotulo}).",
        "st_erro_trad":     "Translation error: {erro}",
        "st_pasta":         "Output folder: {pasta}",
        "st_em_uso":        "'{nome}' is already in use.",
        "st_pronto_online": "Ready — Google online. Click Record or press F5.",
        "st_carregando":    "Loading '{nome}'...",
        "st_baixando":      "Downloading '{nome}' ({tam}) — please wait, don't close the app...",
        "st_pronto_modelo": "Ready — model '{nome}'. Click Record or press F5.",
        "st_erro_modelo":   "Error loading '{nome}': {erro}",
        "st_gravando":      "Recording... speak, then press F5 or click Stop.",
        "st_erro_mic":      "Could not open the microphone.",
        "st_transcrevendo": "Transcribing...",
        "st_aviso_trad":    "Translation failed ({exc}). Showing the original text.",
        "st_erro_transc":   "Transcription error: {erro}",
        "st_transcrito":    "Transcribed. Edit it if needed and press Ctrl+S to save.",
        "st_nada_reconh":   "Nothing recognized. Try again — speak closer to the microphone.",
        "st_nada_copiar":   "Nothing to copy.",
        "st_copiado":       "Text copied to the clipboard.",
        "st_limpo":         "Text cleared.",
        "st_salvo":         "Saved to '{pasta}/comando.txt'.  Ask the agent: 'read comando.txt and run it'.",
        "st_idioma":        "Interface language: English.",
        "btn_ouvir":        "🔊 Listen  [F6]",
        "btn_parar_voz":    "■ Stop voice  [F6]",
        "st_nada_ouvir":    "Nothing to read.",
        "st_gerando_voz":   "Generating the voice...",
        "st_lendo":         "Reading aloud ({idioma}). F6 to stop.",
        "st_lendo_offline": "No connection to the online voice — reading with the system voice ({idioma}).",
        "st_sem_espeak":    "No offline voice installed. Install one with: sudo apt install espeak-ng, or use Google online mode.",
        "st_sem_voz":       "No Windows voice for {idioma}. Install one in Settings > Time & language > Speech, or use Google online mode.",
        "st_erro_voz":      "Error reading the text: {erro}",
    },
    "es": {
        "hdr_sub":          "  Dictado por voz para agentes de IA",
        "lbl_modelo":       "Modelo:",
        "lbl_idioma":       "Idioma de voz:",
        "chk_pont":         "Puntuación",
        "chk_trad":         "Traducir a:",
        "btn_gravar":       "● Grabar  [F5]",
        "btn_parar":        "■ Parar  [F5]",
        "btn_copiar":       "Copiar",
        "btn_limpar":       "Borrar",
        "btn_traduzir":     "⇔ Traducir",
        "btn_salvar":       "💾 Guardar  [Ctrl+S]",
        "txt_hint":         "Texto transcrito  —  edítalo si hace falta antes de guardar:",
        "btn_usar":         "Usar",
        "btn_carregar":     "Cargar",
        "btn_baixar":       "Descargar y cargar",
        "mdl_online":       "☁ en línea — sin descarga, requiere internet",
        "mdl_baixado":      "✔ descargado",
        "mdl_nao_baixado":  "↓ no descargado ({tam})",
        "menu_pasta":       "Cambiar carpeta de guardado",
        "ctx_recortar":     "Cortar",
        "ctx_copiar":       "Copiar",
        "ctx_colar":        "Pegar",
        "ctx_sel_tudo":     "Seleccionar todo",
        "dlg_email_t":      "Límite de traducción",
        "dlg_email":        "El traductor gratuito (MyMemory) permite 5.000 caracteres al día.\n"
                            "Con un correo electrónico, el límite sube a 50.000.\n"
                            "El correo se envía a MyMemory con cada traducción.\n\n"
                            "Correo (opcional — déjalo en blanco para omitirlo):",
        "dlg_email_inv_t":  "Correo no válido",
        "dlg_email_inv":    "Escribe un correo válido o déjalo en blanco para omitirlo.",
        "dlg_pasta":        "Elige la carpeta donde VozComanda guardará los archivos",
        "dlg_trocar_pasta": "Cambiar la carpeta de salida de VozComanda",
        "dlg_erro_mic":     "Error de micrófono",
        "dlg_vazio_t":      "Vacío",
        "dlg_vazio":        "No hay texto para guardar.",
        "dlg_erro_salvar":  "Error al guardar",
        "err_mm_limite":    "se alcanzó el límite diario gratuito de MyMemory — inténtalo mañana",
        "err_mm_recusou":   "MyMemory rechazó la solicitud: {msg}",
        "err_google":       "sin conexión con Google ({exc}). Revisa internet o usa un modelo sin conexión.",
        "st_iniciando":     "Iniciando...",
        "st_nao_baixado":   "El modelo '{nome}' no está descargado. Elige uno y haz clic en 'Descargar y cargar'.",
        "st_nada_traduzir": "Nada que traducir.",
        "st_traduzindo":    "Traduciendo...",
        "st_traduzido":     "Texto traducido ({rotulo}).",
        "st_erro_trad":     "Error de traducción: {erro}",
        "st_pasta":         "Carpeta de salida: {pasta}",
        "st_em_uso":        "'{nome}' ya está en uso.",
        "st_pronto_online": "Listo — Google en línea. Haz clic en Grabar o pulsa F5.",
        "st_carregando":    "Cargando '{nome}'...",
        "st_baixando":      "Descargando '{nome}' ({tam}) — espera, no cierres la app...",
        "st_pronto_modelo": "Listo — modelo '{nome}'. Haz clic en Grabar o pulsa F5.",
        "st_erro_modelo":   "Error al cargar '{nome}': {erro}",
        "st_gravando":      "Grabando... habla y pulsa F5 o haz clic en Parar.",
        "st_erro_mic":      "No se pudo abrir el micrófono.",
        "st_transcrevendo": "Transcribiendo...",
        "st_aviso_trad":    "La traducción falló ({exc}). Se muestra el texto original.",
        "st_erro_transc":   "Error de transcripción: {erro}",
        "st_transcrito":    "Transcrito. Edítalo si hace falta y pulsa Ctrl+S para guardar.",
        "st_nada_reconh":   "No se reconoció nada. Inténtalo de nuevo — habla más cerca del micrófono.",
        "st_nada_copiar":   "Nada que copiar.",
        "st_copiado":       "Texto copiado al portapapeles.",
        "st_limpo":         "Texto borrado.",
        "st_salvo":         "Guardado en '{pasta}/comando.txt'.  Pide al agente: 'lee comando.txt y ejecútalo'.",
        "st_idioma":        "Idioma de la interfaz: Español.",
        "btn_ouvir":        "🔊 Escuchar  [F6]",
        "btn_parar_voz":    "■ Detener voz  [F6]",
        "st_nada_ouvir":    "Nada que leer.",
        "st_gerando_voz":   "Generando la voz...",
        "st_lendo":         "Leyendo en voz alta ({idioma}). F6 para detener.",
        "st_lendo_offline": "Sin conexión con la voz en línea — leyendo con la voz del sistema ({idioma}).",
        "st_sem_espeak":    "No hay voz sin conexión instalada. Instálala con: sudo apt install espeak-ng, o usa el modo Google en línea.",
        "st_sem_voz":       "No hay voz de Windows para {idioma}. Instala una en Configuración > Hora e idioma > Voz, o usa el modo Google en línea.",
        "st_erro_voz":      "Error al leer el texto: {erro}",
    },
}


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
    # Mesmo estilo do AI Router Manager (customtkinter, modo dark, tema "blue")
    "dark": {
        "C_BG":     "#242424",  # gray14 — janela
        "C_PANEL":  "#2b2b2b",  # gray17 — frames
        "C_BORDER": "#474747",  # gray28 — borda de frame
        "C_TEXT":   "#e5e5e5",  # gray90
        "C_TEXT2":  "#bebebe",  # "gray"
        "C_SEL":    "#1f538d",  # item selecionado
        "C_HEADER": "#1f538d",
        "C_REC":    "#c0392b",
        "C_REC_DK": "#922b21",
        "C_REC_LT": "#e74c3c",
        "C_READY":  "#1f6aa5",  # botao padrao do tema blue
        "C_READY_H":"#144870",
        "C_TRAN":   "#7f7f7f",  # gray50
        "C_OK":     "#27ae60",
        "C_INFO":   "#3498db",
        "C_WARN":   "#e67e22",
        "C_ERR":    "#c0392b",
        "ST_OK":    "#24392d",
        "ST_INFO":  "#26353f",
        "ST_WARN":  "#413224",
        "ST_ERR":   "#3b2725",
    },
    "light": {
        "C_BG":     "#f0f2f5",
        "C_PANEL":  "#ffffff",
        "C_BORDER": "#d1d5db",
        "C_TEXT":   "#111827",
        "C_TEXT2":  "#6b7280",
        "C_SEL":    "#bfdbfe",
        "C_HEADER": "#1a56db",
        "C_REC":    "#dc2626",
        "C_REC_DK": "#991b1b",
        "C_REC_LT": "#ef4444",
        "C_READY":  "#2563eb",
        "C_READY_H":"#1e40af",
        "C_TRAN":   "#6b7280",
        "C_OK":     "#16a34a",
        "C_INFO":   "#1d4ed8",
        "C_WARN":   "#b45309",
        "C_ERR":    "#b91c1c",
        "ST_OK":    "#f0fdf4",
        "ST_INFO":  "#eff6ff",
        "ST_WARN":  "#fffbeb",
        "ST_ERR":   "#fef2f2",
    },
}

# Cores que mudam com o tema; viram globais (C_BG, C_REC, ...) em _aplicar_tema().
_CORES_TEMA = ("C_BG", "C_PANEL", "C_BORDER", "C_TEXT", "C_TEXT2", "C_HEADER",
               "C_REC", "C_REC_DK", "C_REC_LT", "C_READY", "C_READY_H", "C_TRAN",
               "C_OK", "C_INFO", "C_WARN", "C_ERR")
_P = PALETA["dark"]  # valores iniciais (dark, padrao)
C_BG, C_PANEL, C_BORDER, C_TEXT, C_TEXT2 = (_P[k] for k in _CORES_TEMA[:5])
C_HEADER, C_REC, C_REC_DK, C_REC_LT = (_P[k] for k in _CORES_TEMA[5:9])
C_READY, C_READY_H, C_TRAN = (_P[k] for k in _CORES_TEMA[9:12])
C_OK, C_INFO, C_WARN, C_ERR = (_P[k] for k in _CORES_TEMA[12:])


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


# O Google gratuito devolve o texto sem nenhuma pontuacao. Com a caixa Pontuacao marcada,
# o audio e cortado nas pausas e cada trecho vai ao Google em separado: pausa curta vira
# virgula, pausa longa vira ponto final. Medido com fala real e sintetica: virgulas
# ficam em ~0,25-0,3 s e fins de frase em ~0,7-0,9 s.
PAUSA_VIRGULA = 0.25   # segundos
PAUSA_PONTO   = 0.60
TRECHO_MIN    = 0.6    # trechos mais curtos se juntam ao seguinte (o Google erra palavras soltas)


def _trechos_por_pausa(audio: np.ndarray) -> list:
    """[(audio_do_trecho, pausa_depois_em_s)] cortando nas pausas >= PAUSA_VIRGULA.
    Lista vazia se o VAD do faster-whisper nao estiver instalado."""
    try:
        from faster_whisper.vad import VadOptions, get_speech_timestamps
    except ImportError:
        return []
    falas = get_speech_timestamps(audio, VadOptions(
        threshold=0.3, min_silence_duration_ms=int(PAUSA_VIRGULA * 1000), speech_pad_ms=100))
    trechos = []
    for i, fala in enumerate(falas):
        pausa = (falas[i + 1]["start"] - fala["end"]) / SAMPLE_RATE if i + 1 < len(falas) else 0.0
        if trechos and (trechos[-1][1] - trechos[-1][0]) / SAMPLE_RATE < TRECHO_MIN:
            trechos[-1][1:] = [fala["end"], pausa]        # junta ao trecho curto anterior
        else:
            trechos.append([fala["start"], fala["end"], pausa])
    pad = int(SAMPLE_RATE * 0.2)
    return [(audio[max(0, ini - pad):fim + pad], pausa) for ini, fim, pausa in trechos]


def _juntar_com_pontuacao(partes: list) -> str:
    """Junta [(texto, pausa_depois)] com virgula ou ponto conforme a pausa."""
    saida = ""
    for texto, pausa in partes:
        texto = texto.strip()
        if not saida or saida.endswith((". ", "? ", "! ")):
            texto = texto[:1].upper() + texto[1:]
        saida += texto
        if pausa >= PAUSA_PONTO:
            saida += ". "
        elif pausa > 0:
            saida += ", "
    return _aplicar_pontuacao_google(saida.strip().rstrip(","))


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
        self.root.geometry("840x640")
        self.root.configure(bg=C_BG)
        self.root.resizable(True, True)
        self.root.minsize(660, 500)
        try:
            if WINDOWS:
                self.root.iconbitmap(os.path.join(APP_DIR, "icone.ico"))
            else:   # o Tk do Linux nao le .ico
                self._icone = tk.PhotoImage(file=os.path.join(APP_DIR, "icone.png"))
                self.root.iconphoto(True, self._icone)
        except Exception:
            pass

        self.model = None
        self.modelo_atual = None
        self.carregando = False
        self.audio_q: queue.Queue = queue.Queue()
        self.gravando = False
        self.stream = None
        self._pulso = False
        self._lendo = 0        # numero da leitura em curso (0 = nenhuma); descarta respostas antigas
        self._leituras = 0
        self._sapi = None      # voz do Windows, criada no primeiro uso
        self._espeak = None    # processo do espeak-ng (voz offline no Linux)

        cfg = carregar_config()
        escolhido = cfg.get("modelo", MODEL_SIZE)
        if escolhido not in opcoes_disponiveis():
            escolhido = ONLINE
        self.modelo_sel    = tk.StringVar(value=escolhido)
        self.var_pontuacao = tk.BooleanVar(value=cfg.get("pontuacao", True))
        self._save_dir     = cfg.get("save_dir") or None
        # None = ainda nao perguntado; "" = usuario pulou
        self._mm_email     = cfg.get("mm_email")

        self._lang = cfg.get("lang") if cfg.get("lang") in IDIOMAS_UI else _idioma_sistema()
        self._translatable = []   # (widget, chave) — textos refeitos em _set_lang

        # Idiomas guardados como codigo; os comboboxes mostram o nome no idioma da interface
        voz_pad = {"pt": "pt-BR", "en": "en", "es": "es"}[self._lang]
        self._voz  = _codigo_idioma(cfg.get("idioma_voz"), IDIOMAS_VOZ, voz_pad)
        self._alvo = _codigo_idioma(cfg.get("idioma_alvo"), IDIOMAS_ALVO,
                                    "es" if self._lang == "en" else "en")
        self.var_idioma_voz  = tk.StringVar(value=self._nome_idioma(self._voz))
        self.var_idioma_alvo = tk.StringVar(value=self._nome_idioma(self._alvo))

        self.var_traduzir   = tk.BooleanVar(value=cfg.get("traduzir", False))

        self._tema = cfg.get("tema", "dark")
        self._borders = []   # tk.Frame separadores — atualizados em _recolorir_ui

        self._aplicar_tema()
        self._build_ui()
        self._atualizar_info_modelo()
        self._bind_atalhos()

        if escolhido == ONLINE or modelo_baixado(escolhido):
            self.carregar_modelo()
        else:
            self.set_status(self.t("st_nao_baixado", nome=escolhido), "warn")

    # ---------------------------------------------------------------- idioma
    def t(self, chave: str, **kw) -> str:
        texto = _sem_emoji(TEXTS[self._lang].get(chave, TEXTS["pt"].get(chave, chave)))
        return texto.format(**kw) if kw else texto

    def _reg(self, widget, chave: str):
        self._translatable.append((widget, chave))
        widget.configure(text=self.t(chave))
        return widget

    def _nome_idioma(self, codigo: str) -> str:
        return NOMES_IDIOMA[codigo][IDIOMAS_UI.index(self._lang)]

    def _codigo_por_nome(self, nome: str, tabela) -> str:
        return next(c for c in tabela if self._nome_idioma(c) == nome)

    def _set_lang(self, lang: str):
        if lang == self._lang:
            return
        self._lang = lang
        cfg = carregar_config()
        cfg["lang"] = lang
        salvar_config(cfg)
        for widget, chave in self._translatable:
            widget.configure(text=self.t(chave))
        self.btn_lang.configure(text=lang.upper())
        self.btn_gravar.configure(text=self.t("btn_parar" if self.gravando else "btn_gravar"))
        self.btn_ouvir.configure(text=self.t("btn_parar_voz" if self._lendo else "btn_ouvir"))
        self.cmb_idioma.configure(values=[self._nome_idioma(c) for c in IDIOMAS_VOZ])
        self.cmb_alvo.configure(values=[self._nome_idioma(c) for c in IDIOMAS_ALVO])
        self.var_idioma_voz.set(self._nome_idioma(self._voz))
        self.var_idioma_alvo.set(self._nome_idioma(self._alvo))
        for i, chave in enumerate(("ctx_recortar", "ctx_copiar", "ctx_colar", None, "ctx_sel_tudo")):
            if chave:
                self.menu_ctx.entryconfig(i, label=self.t(chave))
        self._atualizar_info_modelo()
        self.set_status(self.t("st_idioma"), "ok")

    def _abrir_menu_idioma(self):
        menu = tk.Menu(self.root, tearoff=0)
        menu.sel = tk.StringVar(value=self._lang)   # referencia no menu: o Tk nao guarda a variavel
        for lang, nome in (("pt", "Português"), ("en", "English"), ("es", "Español")):
            menu.add_radiobutton(label=nome, command=lambda l=lang: self._set_lang(l),
                                 value=lang, variable=menu.sel)
        menu.tk_popup(self.btn_lang.winfo_rootx(),
                      self.btn_lang.winfo_rooty() + self.btn_lang.winfo_height())

    # ---------------------------------------------------------------- tema
    def _aplicar_tema(self, tema=None):
        if tema is not None:
            self._tema = tema
        p = PALETA[self._tema]
        globals().update({k: p[k] for k in _CORES_TEMA})
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
        self._hdr = hdr = tk.Frame(self.root, bg=C_HEADER, height=56)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        tk.Label(hdr, text=_sem_emoji("🎤"), bg=C_HEADER, fg="white",
                 font=("Segoe UI", 20)).pack(side=tk.LEFT, padx=(14, 6), pady=8)
        tk.Label(hdr, text="VozComanda", bg=C_HEADER, fg="white",
                 font=("Segoe UI", 15, "bold")).pack(side=tk.LEFT, pady=8)
        self._reg(tk.Label(hdr, bg=C_HEADER, fg="#93c5fd", font=("Segoe UI", 9)),
                  "hdr_sub").pack(side=tk.LEFT, anchor=tk.S, pady=14)

        # ---- Linha modelo
        self._frm_mdl = frm_mdl = tk.Frame(self.root, bg=C_PANEL)
        frm_mdl.pack(fill=tk.X)
        b = tk.Frame(frm_mdl, bg=C_BORDER, height=1); b.pack(fill=tk.X); self._borders.append(b)
        self._inner_mdl = inner = tk.Frame(frm_mdl, bg=C_PANEL)
        inner.pack(fill=tk.X, padx=14, pady=8)

        self._lbl_mdl_pfx = self._reg(tk.Label(inner, bg=C_PANEL, fg=C_TEXT,
                                               font=("Segoe UI", 10)), "lbl_modelo")
        self._lbl_mdl_pfx.pack(side=tk.LEFT)
        self.cmb_modelo = ttk.Combobox(inner, textvariable=self.modelo_sel,
                                       values=opcoes_disponiveis(), state="readonly", width=18)
        self.cmb_modelo.pack(side=tk.LEFT, padx=(8, 6))
        self.cmb_modelo.bind("<<ComboboxSelected>>", lambda e: self._atualizar_info_modelo())

        self.btn_carregar = ttk.Button(inner, command=self.carregar_modelo)
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
        _icone_tema = _sem_emoji("🌙" if self._tema == "dark" else "☀️")
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

        # Botao de idioma da interface (PT / EN / ES)
        self.btn_lang = tk.Button(
            inner, text=self._lang.upper(), command=self._abrir_menu_idioma,
            bg=C_PANEL, fg=C_TEXT2,
            activebackground=C_BG, activeforeground=C_TEXT,
            font=("Segoe UI", 9, "bold"), relief="flat", bd=0,
            padx=4, pady=2, cursor="hand2",
        )
        self.btn_lang.pack(side=tk.RIGHT, padx=(0, 4))
        self.btn_lang.bind("<Enter>", lambda e: self.btn_lang.config(fg=C_TEXT))
        self.btn_lang.bind("<Leave>", lambda e: self.btn_lang.config(fg=C_TEXT2))

        # Checkbox pontuacao (direita, antes do botao pasta)
        self.chk_pont = tk.Checkbutton(
            inner, variable=self.var_pontuacao,
            command=self._salvar_pontuacao,
            bg=C_PANEL, fg=C_TEXT, activebackground=C_PANEL,
            selectcolor=C_PANEL,
            font=("Segoe UI", 9), cursor="hand2",
        )
        self._reg(self.chk_pont, "chk_pont")
        self.chk_pont.pack(side=tk.RIGHT, padx=(0, 8))

        b = tk.Frame(frm_mdl, bg=C_BORDER, height=1); b.pack(fill=tk.X); self._borders.append(b)

        # ---- Linha idioma / traducao
        self._frm_lang = frm_lang = tk.Frame(self.root, bg=C_PANEL)
        frm_lang.pack(fill=tk.X)
        self._inner_lang = inner_lang = tk.Frame(frm_lang, bg=C_PANEL)
        inner_lang.pack(fill=tk.X, padx=14, pady=6)

        self._lbl_idioma_pfx = self._reg(tk.Label(inner_lang, bg=C_PANEL, fg=C_TEXT,
                                                  font=("Segoe UI", 9)), "lbl_idioma")
        self._lbl_idioma_pfx.pack(side=tk.LEFT)
        self.cmb_idioma = ttk.Combobox(
            inner_lang, textvariable=self.var_idioma_voz,
            values=[self._nome_idioma(c) for c in IDIOMAS_VOZ], state="readonly", width=15,
        )
        self.cmb_idioma.pack(side=tk.LEFT, padx=(6, 16))
        self.cmb_idioma.bind("<<ComboboxSelected>>", lambda e: self._salvar_idiomas())

        self.chk_trad = tk.Checkbutton(
            inner_lang, variable=self.var_traduzir,
            command=self._toggle_traducao,
            bg=C_PANEL, fg=C_TEXT, activebackground=C_PANEL,
            selectcolor=C_PANEL, font=("Segoe UI", 9), cursor="hand2",
        )
        self._reg(self.chk_trad, "chk_trad")
        self.chk_trad.pack(side=tk.LEFT)
        self.cmb_alvo = ttk.Combobox(
            inner_lang, textvariable=self.var_idioma_alvo,
            values=[self._nome_idioma(c) for c in IDIOMAS_ALVO], state="readonly", width=12,
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
            text=self.t("btn_gravar"),
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

        self.btn_copiar = self._reg(ttk.Button(frm_ctrl, command=self.copiar_texto), "btn_copiar")
        self.btn_copiar.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_limpar = self._reg(ttk.Button(frm_ctrl, command=self.limpar_texto), "btn_limpar")
        self.btn_limpar.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_traduzir = self._reg(ttk.Button(frm_ctrl, command=self.traduzir_texto),
                                      "btn_traduzir")
        self.btn_traduzir.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_ouvir = ttk.Button(frm_ctrl, text=self.t("btn_ouvir"), command=self.toggle_ouvir)
        self.btn_ouvir.pack(side=tk.LEFT, padx=(0, 4))

        self.btn_salvar = self._reg(ttk.Button(frm_ctrl, command=self.salvar_comando),
                                    "btn_salvar")
        self.btn_salvar.pack(side=tk.LEFT)

        # ---- Barra de nivel de audio
        self.cnv_nivel = tk.Canvas(self.root, height=8, bg=C_BG, highlightthickness=0)
        self.cnv_nivel.pack(fill=tk.X, padx=14, pady=(0, 6))
        self._bg_bar  = self.cnv_nivel.create_rectangle(0, 2, 4000, 6, fill=C_BORDER, outline="")
        self._fwd_bar = self.cnv_nivel.create_rectangle(0, 2, 0,    6, fill=C_TEXT2,  outline="")

        # ---- Area de texto
        self._frm_txt = frm_txt = tk.Frame(self.root, bg=C_BG)
        frm_txt.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 6))

        self._lbl_txt_hint = self._reg(tk.Label(frm_txt, bg=C_BG, fg=C_TEXT2,
                                                font=("Segoe UI", 9)), "txt_hint")
        self._lbl_txt_hint.pack(anchor=tk.W, pady=(0, 4))

        self.txt = scrolledtext.ScrolledText(
            frm_txt,
            wrap=tk.WORD,
            font=("Segoe UI", 12),
            height=13,
            bg=C_PANEL, fg=C_TEXT,
            insertbackground=C_INFO,
            selectbackground=PALETA[self._tema]["C_SEL"],
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
            self.frm_status, text=self.t("st_iniciando"),
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
        self.root.bind("<F6>", lambda e: self.toggle_ouvir())
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
        cor = C_REC if self.gravando else C_TEXT2
        self.cnv_nivel.coords(self._bg_bar,  0, 2, w,          6)
        self.cnv_nivel.coords(self._fwd_bar, 0, 2, preenchido, 6)
        self.cnv_nivel.itemconfig(self._fwd_bar, fill=cor)

    # ---------------------------------------------------------------- modelo
    def _atualizar_info_modelo(self):
        nome = self.modelo_sel.get()
        if nome == ONLINE:
            self.lbl_modelo.config(text=self.t("mdl_online"), fg=C_INFO)
            self.btn_carregar.config(text=self.t("btn_usar"))
        elif modelo_baixado(nome):
            self.lbl_modelo.config(text=self.t("mdl_baixado"), fg=C_OK)
            self.btn_carregar.config(text=self.t("btn_carregar"))
        else:
            self.lbl_modelo.config(
                text=self.t("mdl_nao_baixado", tam=MODELOS.get(nome, "?")), fg=C_WARN)
            self.btn_carregar.config(text=self.t("btn_baixar"))

    def _habilitar_seletor(self, on: bool):
        self.cmb_modelo.config(state="readonly" if on else "disabled")
        self.btn_carregar.config(state=tk.NORMAL if on else tk.DISABLED)

    def _salvar_pontuacao(self):
        cfg = carregar_config()
        cfg["pontuacao"] = self.var_pontuacao.get()
        salvar_config(cfg)

    def _salvar_idiomas(self):
        self._voz  = self._codigo_por_nome(self.var_idioma_voz.get(), IDIOMAS_VOZ)
        self._alvo = self._codigo_por_nome(self.var_idioma_alvo.get(), IDIOMAS_ALVO)
        cfg = carregar_config()
        cfg["idioma_voz"]  = self._voz
        cfg["idioma_alvo"] = self._alvo
        salvar_config(cfg)

    def _toggle_traducao(self):
        estado = "readonly" if self.var_traduzir.get() else "disabled"
        self.cmb_alvo.config(state=estado)
        cfg = carregar_config()
        cfg["traduzir"] = self.var_traduzir.get()
        salvar_config(cfg)

    # ---------------------------------------------------------------- traducao
    @staticmethod
    def _parece_ingles(texto: str) -> bool:
        """Conta palavras frequentes de EN contra as de PT e ES — sem API."""
        palavras = re.findall(r"\w+", texto.lower())
        en = sum(p in _PALAVRAS_EN for p in palavras)
        outro = max(sum(p in _PALAVRAS_PT for p in palavras),
                    sum(p in _PALAVRAS_ES for p in palavras))
        return en > outro

    def _codigo_casa(self) -> str:
        """Idioma (codigo de IDIOMAS_VOZ) que o botao Traduzir troca com o ingles: o idioma de voz;
        se a voz for ingles, o de destino; se tambem for ingles, o da interface (PT na interface EN)."""
        for cod in (self._voz, self._alvo):
            if cod != "en":
                return "pt-BR" if cod == "pt" else cod
        return "es" if self._lang == "es" else "pt-BR"

    def _idioma_casa(self) -> str:
        return IDIOMAS_VOZ[self._codigo_casa()]["mm"]

    def _garantir_email_mm(self):
        """Na primeira traducao, oferece informar um e-mail (MyMemory: 5.000 -> 50.000 caracteres/dia)."""
        if self._mm_email is not None:
            return
        while True:
            email = simpledialog.askstring(self.t("dlg_email_t"), self.t("dlg_email"),
                                           parent=self.root)
            email = (email or "").strip()
            if not email or re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                break
            messagebox.showwarning(self.t("dlg_email_inv_t"), self.t("dlg_email_inv"),
                                   parent=self.root)
        self._mm_email = email
        cfg = carregar_config()
        cfg["mm_email"] = email
        salvar_config(cfg)

    def _traduzir_bloco(self, texto: str, de: str, para: str, email=None) -> str:
        """MyMemory primeiro; GoogleTranslator de reserva (hoje bloqueado, pode voltar)."""
        from deep_translator import GoogleTranslator, MyMemoryTranslator
        try:
            resultado = MyMemoryTranslator(source=de, target=para, email=email).translate(texto) or texto
            # MyMemory devolve erros como se fossem a traducao, em maiusculas
            if resultado.startswith("MYMEMORY WARNING"):
                raise RuntimeError(self.t("err_mm_limite"))
            if "INVALID" in resultado and resultado.isupper():
                raise RuntimeError(self.t("err_mm_recusou", msg=resultado[:80]))
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
        de   = IDIOMAS_VOZ[self._voz]["mm"]
        para = IDIOMAS_ALVO[self._alvo]
        if de == para:
            return texto
        return self._fazer_traducao(texto, de, para)

    def traduzir_texto(self):
        """Traduz o texto da caixa entre o ingles e o idioma de casa, na direcao detectada."""
        texto = self.txt.get("1.0", tk.END).strip()
        if not texto:
            self.set_status(self.t("st_nada_traduzir"), "warn")
            return
        self._garantir_email_mm()
        self.set_status(self.t("st_traduzindo"), "info")
        casa = self._idioma_casa()
        self.btn_traduzir.config(state=tk.DISABLED)

        def _do():
            try:
                # MyMemory nao aceita origem "auto": a deteccao local decide a direcao
                sigla = casa.split("-")[0].upper()
                if self._parece_ingles(texto):
                    de, para, rotulo = "en-GB", casa, f"EN → {sigla}"
                else:
                    de, para, rotulo = casa, "en-GB", f"{sigla} → EN"
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
        self.set_status(self.t("st_traduzido", rotulo=rotulo), "ok")

    def _erro_traducao(self, erro: str):
        self.btn_traduzir.config(state=tk.NORMAL)
        self.set_status(self.t("st_erro_trad", erro=erro), "err")

    # ---------------------------------------------------------------- leitura em voz alta
    def toggle_ouvir(self):
        if self._lendo:
            self._parar_leitura()
            self.set_status("", "idle")
            return
        texto = self.txt.get("1.0", tk.END).strip()
        if not texto:
            self.set_status(self.t("st_nada_ouvir"), "warn")
            return
        if self.gravando:
            return
        idioma = "en" if self._parece_ingles(texto) else self._codigo_casa()
        self._leituras += 1
        self._lendo = token = self._leituras
        self.btn_ouvir.config(text=self.t("btn_parar_voz"))
        if self.modelo_atual == ONLINE:   # modo online: voz neural; modo offline: nada sai do PC
            self.set_status(self.t("st_gerando_voz"), "info")
            threading.Thread(target=self._gerar_voz_online, args=(texto, idioma, token),
                             daemon=True).start()
        else:
            self._ler_offline(texto, idioma, token, "st_lendo")

    def _gerar_voz_online(self, texto, idioma, token):
        try:
            import asyncio, io, av, edge_tts

            async def baixar():
                mp3 = bytearray()
                async for parte in edge_tts.Communicate(texto, VOZES_ONLINE[idioma]).stream():
                    if parte["type"] == "audio":
                        mp3 += parte["data"]
                return bytes(mp3)

            mp3 = asyncio.run(baixar())
            conv = av.AudioResampler(format="flt", layout="mono", rate=TAXA_VOZ)
            with av.open(io.BytesIO(mp3)) as arq:
                pcm = np.concatenate([q.to_ndarray().reshape(-1)
                                      for quadro in arq.decode(audio=0) for q in conv.resample(quadro)])
            self.root.after(0, lambda: self._tocar_voz(pcm, idioma, token))
        except Exception:
            self.root.after(0, lambda: self._ler_offline(texto, idioma, token, "st_lendo_offline"))

    def _tocar_voz(self, pcm, idioma, token):
        if token != self._lendo:   # o usuario parou antes de a voz chegar
            return
        sd.play(pcm, TAXA_VOZ)
        self.set_status(self.t("st_lendo", idioma=self._nome_idioma(idioma)), "ok")
        self.root.after(int(len(pcm) / TAXA_VOZ * 1000) + 300, lambda: self._fim_leitura(token))

    def _ler_offline(self, texto, idioma, token, chave_status):
        if token != self._lendo:
            return
        if WINDOWS:
            self._ler_com_windows(texto, idioma, token, chave_status)
        else:
            self._ler_com_espeak(texto, idioma, token, chave_status)

    def _ler_com_espeak(self, texto, idioma, token, chave_status):
        import subprocess
        try:
            self._espeak = subprocess.Popen(["espeak-ng", "-v", VOZES_ESPEAK[idioma], "--", texto])
        except FileNotFoundError:
            self._fim_leitura(token)
            self.set_status(self.t("st_sem_espeak"), "warn")
            return
        self.set_status(self.t(chave_status, idioma=self._nome_idioma(idioma)), "ok")
        self._vigiar_espeak(token)

    def _vigiar_espeak(self, token):
        if token != self._lendo:
            return
        if self._espeak.poll() is None:
            self.root.after(250, lambda: self._vigiar_espeak(token))
        else:
            self._fim_leitura(token)

    def _ler_com_windows(self, texto, idioma, token, chave_status):
        try:
            if self._sapi is None:
                import comtypes.client
                self._sapi = comtypes.client.CreateObject("SAPI.SpVoice", dynamic=True)
            vozes = self._sapi.GetVoices()
            alvo = LCID_WINDOWS[idioma] & 0x3FF
            voz = next((vozes.Item(i) for i in range(vozes.Count)
                        if int(vozes.Item(i).GetAttribute("Language").split(";")[0], 16) & 0x3FF == alvo),
                       None)
        except Exception as exc:
            self._fim_leitura(token)
            self.set_status(self.t("st_erro_voz", erro=exc), "err")
            return
        if voz is None:
            self._fim_leitura(token)
            self.set_status(self.t("st_sem_voz", idioma=self._nome_idioma(idioma)), "warn")
            return
        self._sapi.Voice = voz
        self._sapi.Speak(texto, 1)   # 1 = assincrono
        self.set_status(self.t(chave_status, idioma=self._nome_idioma(idioma)), "ok")
        self._vigiar_windows(token)

    def _vigiar_windows(self, token):
        if token != self._lendo:
            return
        if self._sapi.Status.RunningState == 2:   # 2 = falando
            self.root.after(250, lambda: self._vigiar_windows(token))
        else:
            self._fim_leitura(token)

    def _parar_leitura(self):
        self._lendo = 0
        sd.stop()
        if self._sapi is not None:
            self._sapi.Speak("", 3)   # 3 = assincrono + descarta a fala em curso
        if self._espeak is not None and self._espeak.poll() is None:
            self._espeak.terminate()
        self.btn_ouvir.config(text=self.t("btn_ouvir"))

    def _fim_leitura(self, token):
        if token == self._lendo:
            self._lendo = 0
            self.btn_ouvir.config(text=self.t("btn_ouvir"))

    def _obter_save_dir(self) -> str:
        """Retorna o diretorio de saida, pedindo ao usuario na primeira vez."""
        if self._save_dir:
            return self._save_dir
        from tkinter import filedialog
        pasta = filedialog.askdirectory(
            title=self.t("dlg_pasta"),
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
            title=self.t("dlg_trocar_pasta"),
            initialdir=self._save_dir or BASE_DIR,
        )
        if not pasta:
            return
        self._save_dir = pasta
        cfg = carregar_config()
        cfg["save_dir"] = pasta
        salvar_config(cfg)
        self.set_status(self.t("st_pasta", pasta=pasta), "ok")

    def _abrir_menu_config(self):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=self.t("menu_pasta"), command=self._trocar_pasta)
        x = self.btn_pasta.winfo_rootx()
        y = self.btn_pasta.winfo_rooty() + self.btn_pasta.winfo_height()
        menu.tk_popup(x, y)

    def _toggle_tema(self):
        self._trocar_tema("light" if self._tema == "dark" else "dark")

    def _trocar_tema(self, tema):
        if tema == self._tema:
            return
        antiga = PALETA[self._tema]
        self._aplicar_tema(tema)
        self._recolorir_ui(antiga)
        cfg = carregar_config()
        cfg["tema"] = tema
        salvar_config(cfg)

    def _recolorir_ui(self, antiga):
        p = PALETA[self._tema]
        sel = p["C_SEL"]
        # Cabecalho
        self._hdr.configure(bg=C_HEADER)
        for w in self._hdr.winfo_children():
            w.configure(bg=C_HEADER)
        # Botao gravar: mantem o estado (pronto / gravando / transcrevendo)
        if self.gravando:
            self.btn_gravar.configure(bg=C_REC, activebackground=C_REC_DK)
        elif self.btn_gravar.cget("bg") == antiga["C_TRAN"]:
            self.btn_gravar.configure(bg=C_TRAN, activebackground=C_TRAN)
        else:
            self.btn_gravar.configure(bg=C_READY, activebackground=C_READY_H)
        self._atualizar_info_modelo()
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
        _icone = _sem_emoji("🌙" if self._tema == "dark" else "☀️")
        self.btn_tema.configure(bg=C_PANEL, fg=C_TEXT2, text=_icone,
                                activebackground=C_BG, activeforeground=C_TEXT)
        self.btn_tema.bind("<Leave>", lambda e: self.btn_tema.config(fg=C_TEXT2))
        self.btn_tema.bind("<Enter>", lambda e: self.btn_tema.config(fg=C_TEXT))
        self.btn_lang.configure(bg=C_PANEL, fg=C_TEXT2,
                                activebackground=C_BG, activeforeground=C_TEXT)
        self.btn_lang.bind("<Leave>", lambda e: self.btn_lang.config(fg=C_TEXT2))
        self.btn_lang.bind("<Enter>", lambda e: self.btn_lang.config(fg=C_TEXT))
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
            self.set_status(self.t("st_em_uso", nome=nome), "ok")
            return
        if nome == ONLINE:
            self.model = None
            self.modelo_atual = ONLINE
            gc.collect()
            cfg = carregar_config()
            cfg["modelo"] = ONLINE
            salvar_config(cfg)
            self._atualizar_info_modelo()
            self.set_status(self.t("st_pronto_online"), "ok")
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
            self.set_status(self.t("st_carregando", nome=nome), "info")
        else:
            self.set_status(self.t("st_baixando", nome=nome, tam=MODELOS.get(nome, "?")), "info")

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
        self.set_status(self.t("st_pronto_modelo", nome=nome), "ok")
        self.btn_gravar.config(state=tk.NORMAL)

    def _modelo_erro(self, nome, erro):
        self._fim_carregamento()
        self.set_status(self.t("st_erro_modelo", nome=nome, erro=erro), "err")

    # ---------------------------------------------------------------- gravacao
    def toggle_gravar(self):
        if self.gravando:
            self.parar_e_transcrever()
        else:
            self.iniciar_gravacao()

    def iniciar_gravacao(self):
        if self.modelo_atual is None:
            return
        if self._lendo:   # o microfone captaria a propria voz do app
            self._parar_leitura()
        with self.audio_q.mutex:
            self.audio_q.queue.clear()
        self.gravando = True
        self._habilitar_seletor(False)
        self.btn_gravar.config(text=self.t("btn_parar"), bg=C_REC, activebackground=C_REC_DK)
        self.set_status(self.t("st_gravando"), "warn")
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
            self.btn_gravar.config(text=self.t("btn_gravar"), bg=C_READY,
                                   activebackground=C_READY_H)
            messagebox.showerror(self.t("dlg_erro_mic"), str(exc))
            self.set_status(self.t("st_erro_mic"), "err")

    def _animar_gravar(self):
        if not self.gravando:
            return
        self._pulso = not self._pulso
        cor = C_REC if self._pulso else C_REC_LT
        self.btn_gravar.config(bg=cor)
        self.root.after(550, self._animar_gravar)

    def parar_e_transcrever(self):
        self.gravando = False
        self.btn_gravar.config(state=tk.DISABLED, text=self.t("btn_gravar"),
                               bg=C_TRAN, activebackground=C_TRAN)
        self.set_status(self.t("st_transcrevendo"), "info")
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
            erro = self.t("err_google", exc=exc)
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
                aviso = self.t("st_aviso_trad", exc=exc)
        self.root.after(0, lambda: self._mostrar_texto(texto, aviso))

    def _transcrever_google(self, audio: np.ndarray) -> str:
        """Envia o audio normalizado ao Google (sem criar arquivo no disco)."""
        lang_google = IDIOMAS_VOZ[self._voz]["google"]

        def reconhecer(trecho):
            dados = sr.AudioData((trecho * 32767).astype(np.int16).tobytes(), SAMPLE_RATE, 2)
            r = sr.Recognizer()
            r.operation_timeout = 30
            # show_all=False: retorna a transcricao de maior confianca
            return r.recognize_google(dados, language=lang_google, show_all=False)

        if not self.var_pontuacao.get():
            return reconhecer(audio)
        trechos = _trechos_por_pausa(audio)
        if len(trechos) > 1:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=4) as pool:
                futuros = [pool.submit(reconhecer, t) for t, _ in trechos]
            try:
                return _juntar_com_pontuacao([(f.result(), p) for f, (_, p) in zip(futuros, trechos)])
            except sr.UnknownValueError:
                pass   # um trecho sem palavras reconhecidas: refaz com o audio inteiro
        return _aplicar_pontuacao_google(reconhecer(audio))

    def _transcrever_whisper(self, modelo, audio: np.ndarray) -> str:
        """Transcreve com faster-whisper. beam_size=5 equilibra velocidade e precisao."""
        lang_whisper = IDIOMAS_VOZ[self._voz]["whisper"]
        segs, _info = modelo.transcribe(
            audio,
            language=lang_whisper,
            beam_size=5,          # era 8 — mais rapido, qualidade equivalente
            vad_filter=True,
            vad_parameters=VAD_PARAMS,
            initial_prompt=PROMPT_PT if lang_whisper == "pt" else None,  # vocabulario em PT
            condition_on_previous_text=False,
            temperature=0.0,      # decodificacao gulosa: mais rapida e menos alucinacoes
            no_speech_threshold=0.45,
        )
        texto = " ".join(s.text.strip() for s in segs).strip()
        if not self.var_pontuacao.get():
            texto = _remover_pontuacao(texto)
        return texto

    def _erro_transcricao(self, erro):
        self.set_status(self.t("st_erro_transc", erro=erro), "err")
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
                self.set_status(self.t("st_transcrito"), "ok")
        else:
            self.set_status(self.t("st_nada_reconh"), "warn")
        self.btn_gravar.config(state=tk.NORMAL, bg=C_READY, activebackground=C_READY_H)
        self._habilitar_seletor(True)

    # ---------------------------------------------------------------- menu contexto
    def _criar_menu_contexto(self):
        m = tk.Menu(self.txt, tearoff=0)
        m.add_command(label=self.t("ctx_recortar"), command=lambda: self.txt.event_generate("<<Cut>>"))
        m.add_command(label=self.t("ctx_copiar"),   command=lambda: self.txt.event_generate("<<Copy>>"))
        m.add_command(label=self.t("ctx_colar"),    command=lambda: self.txt.event_generate("<<Paste>>"))
        m.add_separator()
        m.add_command(label=self.t("ctx_sel_tudo"), command=self._sel_tudo)
        self.menu_ctx = m
        self.txt.bind("<Button-3>", self._mostrar_ctx)

    def _sel_tudo(self):
        self.txt.tag_add(tk.SEL, "1.0", tk.END)
        self.txt.focus_set()

    def _mostrar_ctx(self, event):
        self.txt.focus_set()
        tem = bool(self.txt.tag_ranges(tk.SEL))
        for indice in (0, 1):   # Recortar, Copiar
            self.menu_ctx.entryconfig(indice, state=tk.NORMAL if tem else tk.DISABLED)
        try:
            self.menu_ctx.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu_ctx.grab_release()

    # ---------------------------------------------------------------- acoes
    def copiar_texto(self):
        texto = self.txt.get("1.0", tk.END).strip()
        if not texto:
            self.set_status(self.t("st_nada_copiar"), "warn")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(texto)
        self.root.update()
        self.set_status(self.t("st_copiado"), "ok")

    def limpar_texto(self):
        self.txt.delete("1.0", tk.END)
        self._set_nivel(0)
        self.set_status(self.t("st_limpo"), "idle")

    def salvar_comando(self):
        texto = self.txt.get("1.0", tk.END).strip()
        if not texto:
            messagebox.showwarning(self.t("dlg_vazio_t"), self.t("dlg_vazio"))
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
            messagebox.showerror(self.t("dlg_erro_salvar"), str(exc))
            return
        pasta_nome = os.path.basename(save_dir) or save_dir
        self.set_status(self.t("st_salvo", pasta=pasta_nome), "ok")


def main():
    root = tk.Tk()
    VozComandaApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
