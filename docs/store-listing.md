# Microsoft Store listing

Texts pasted into Partner Center → Listagens da Store. The package declares pt-BR (the app's interface language); English and Spanish are extra listing languages, and both say the interface is in Portuguese. All three use the same screenshots. Keep this file in sync when the app changes.

## Português (Brasil) — pt-br

**Nome:** VozComanda

**Descrição**

Fale em vez de digitar: o VozComanda transforma sua voz em texto pronto para mandar a um agente de IA, como Claude Code, Kiro, Cursor ou ChatGPT.

Clique em Gravar (ou aperte F5), fale e clique em Parar. O texto aparece numa caixa para você revisar. Com Ctrl+S ele vai para o arquivo comando.txt, na pasta do seu projeto, e o agente lê e executa. Ou copie e cole onde quiser.

• Reconhecimento online pelo Google, rápido e sem download
• Modo offline com Whisper: a voz não sai do seu computador
• 10 idiomas de voz, incluindo português, inglês e espanhol
• Fale em português e receba o texto já traduzido para o inglês
• Botão Traduzir: cole a resposta do agente em inglês e leia em português
• Histórico de todos os comandos salvos, com data e hora
• Atalhos de teclado, tema claro e escuro

Feito para quem prefere ditar, tem dificuldade para digitar ou quer conversar com a IA em português e mandar o pedido em inglês.

Gratuito e de código aberto. Sem conta, sem anúncios.

**Recursos do produto** (um por linha)

- Ditado por voz com um clique ou com F5
- Modo offline (Whisper): a voz não sai do computador
- 10 idiomas de voz
- Tradução automática ao ditar
- Tradução de textos colados, português ⇄ inglês
- Salva em comando.txt para agentes de IA, com histórico
- Tema claro e escuro

**Descrição resumida:** Fale em vez de digitar: transforme sua voz em comandos para agentes de IA como Claude Code, Kiro e Cursor, com tradução automática para o inglês e modo offline.

**Termos de pesquisa** (até 7)

ditado por voz · voz para texto · claude code · whisper · transcrição · tradutor · agente ia

**Notas de direitos autorais:** © 2026 WD Software

**URL da política de privacidade:** https://github.com/wercelyduarte/VozComanda/blob/master/PRIVACY.md

**Requisitos de hardware:** Microfone (obrigatório).

**Capturas de tela** (1366×768, em [store-screens/](store-screens/)), nesta ordem:

1. `1-ditado-escuro.png` — Texto ditado em português, salvo para o agente
2. `2-traducao-escuro.png` — Fale em português, receba em inglês
3. `3-offline-claro.png` — Modo offline com Whisper, tema claro

## English — en (additional listing language)

**Description**

Talk instead of typing: VozComanda turns your voice into text ready to send to an AI coding agent such as Claude Code, Kiro, Cursor or ChatGPT.

Click Record (or press F5), speak and click Stop. The text shows up in a box for you to review. Ctrl+S saves it to comando.txt in your project folder, where the agent reads and runs it. Or copy and paste it anywhere.

• Online recognition with Google: fast, nothing to download
• Offline mode with Whisper: your voice never leaves your computer
• 10 voice languages, including English, Spanish and Portuguese
• Speak in one language and get the text already translated into another
• Translate button: paste the agent's answer and read it in Portuguese
• History of every saved command, with date and time
• Keyboard shortcuts, light and dark theme

Made for people who would rather dictate, find typing hard, or want to talk to AI in their own language and send the request in English.

The interface is in Portuguese.

Free and open source. No account, no ads.

**Short description:** Talk instead of typing: turn your voice into commands for AI agents like Claude Code, Kiro and Cursor, with automatic translation and an offline mode.

**Product features**

- Voice dictation with one click or F5
- Offline mode (Whisper): your voice stays on your PC
- 10 voice languages
- Automatic translation while you dictate
- Translate pasted text between Portuguese and English
- Saves to comando.txt for AI agents, with history
- Light and dark theme

**Keywords:** voice dictation · speech to text · claude code · whisper · voice typing · translator · ai agent

## Español — es (additional listing language)

**Descripción**

Habla en lugar de escribir: VozComanda convierte tu voz en texto listo para enviar a un agente de IA, como Claude Code, Kiro, Cursor o ChatGPT.

Haz clic en Grabar (o pulsa F5), habla y haz clic en Parar. El texto aparece en un cuadro para que lo revises. Con Ctrl+S se guarda en el archivo comando.txt, en la carpeta de tu proyecto, y el agente lo lee y lo ejecuta. O cópialo y pégalo donde quieras.

• Reconocimiento en línea con Google: rápido y sin descargas
• Modo sin conexión con Whisper: tu voz no sale de tu computadora
• 10 idiomas de voz, entre ellos español, inglés y portugués
• Habla en un idioma y recibe el texto ya traducido a otro
• Botón Traducir: pega la respuesta del agente y léela en portugués
• Historial de todos los comandos guardados, con fecha y hora
• Atajos de teclado, tema claro y oscuro

Pensado para quien prefiere dictar, tiene dificultad para escribir o quiere hablar con la IA en su idioma y enviar el pedido en inglés.

La interfaz está en portugués.

Gratis y de código abierto. Sin cuenta y sin anuncios.

**Descripción breve:** Habla en lugar de escribir: convierte tu voz en comandos para agentes de IA como Claude Code, Kiro y Cursor, con traducción automática y modo sin conexión.

**Características del producto**

- Dictado por voz con un clic o con F5
- Modo sin conexión (Whisper): tu voz no sale del PC
- 10 idiomas de voz
- Traducción automática al dictar
- Traducción de textos pegados entre portugués e inglés
- Guarda en comando.txt para agentes de IA, con historial
- Tema claro y oscuro

**Palabras clave:** dictado por voz · voz a texto · claude code · whisper · transcripción · traductor · agente ia

## Restricted capability justification (Opções de envio, 500 characters)

**runFullTrust**

> VozComanda is a Win32 desktop app (Python/Tkinter, Desktop Bridge). It records the microphone through PortAudio, runs speech recognition locally with faster-whisper (CTranslate2/ONNX native libraries) or sends it to Google, and writes the transcribed command to comando.txt in a folder the user picks, usually an AI coding agent's project folder, so the agent can read it. None of this works inside the AppContainer sandbox.
