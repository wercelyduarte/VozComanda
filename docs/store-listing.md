# Microsoft Store listing

Texts pasted into Partner Center → Listagens da Store. The app's interface is in Portuguese, so the package and the listing are pt-BR only. Keep this file in sync when the app changes.

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

**Termos de pesquisa** (até 7)

ditado por voz · voz para texto · claude code · whisper · transcrição · tradutor · agente ia

**Notas de direitos autorais:** © 2026 WD Software

**URL da política de privacidade:** https://github.com/wercelyduarte/VozComanda/blob/master/PRIVACY.md

**Requisitos de hardware:** Microfone (obrigatório).

**Capturas de tela** (1366×768, em [store-screens/](store-screens/)), nesta ordem:

1. `1-ditado-escuro.png` — Texto ditado em português, salvo para o agente
2. `2-traducao-escuro.png` — Fale em português, receba em inglês
3. `3-offline-claro.png` — Modo offline com Whisper, tema claro

## Restricted capability justification (Opções de envio, 500 characters)

**runFullTrust**

> VozComanda is a Win32 desktop app (Python/Tkinter, Desktop Bridge). It records the microphone through PortAudio, runs speech recognition locally with faster-whisper (CTranslate2/ONNX native libraries) or sends it to Google, and writes the transcribed command to comando.txt in a folder the user picks, usually an AI coding agent's project folder, so the agent can read it. None of this works inside the AppContainer sandbox.
