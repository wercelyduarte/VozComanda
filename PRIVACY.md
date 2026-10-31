# Política de privacidade / Privacy policy

*Última atualização / Last updated: 2026-10-31 (v1.2.5)*

## Português

O VozComanda não tem conta, anúncios nem rastreamento, e **não envia nenhum dado para servidores do desenvolvedor**. O que sai do seu computador vai direto para os serviços abaixo, e só quando você usa o recurso correspondente.

**O que o app acessa, e por quê**

| Acesso | Para quê |
|---|---|
| Microfone | Gravar sua voz enquanto o botão **Gravar** está ativo. Nada é gravado fora disso, e o áudio não é salvo em disco |
| Google Speech (modo **Google online**) | Transcrever o áudio gravado. O áudio é enviado ao Google. No modo **offline (Whisper)** a transcrição roda no seu PC e nenhum áudio sai dele |
| MyMemory (`mymemory.translated.net`) e, se ele falhar, Google Tradutor | Traduzir o texto, quando você liga a tradução ou clica em **⇔ Traduzir**. O texto é enviado ao serviço. Se você informar um e-mail, ele é enviado ao MyMemory para aumentar o limite diário |
| Voz online da Microsoft (serviço de leitura do Microsoft Edge) | Ler o texto em voz alta quando você clica em **🔊 Ouvir** no modo **Google online**. O texto é enviado à Microsoft. No modo **offline**, a leitura usa as vozes do próprio sistema (Windows ou espeak-ng no Linux) e nada sai do PC |
| Hugging Face (`huggingface.co`) | Baixar o modelo offline escolhido, uma única vez. Nenhum dado seu é enviado |
| Pasta que você escolher | Salvar `comando.txt` e o histórico em `historico/` |
| `%LOCALAPPDATA%\VozComanda` (Windows) ou `~/snap/vozcomanda/common` (Linux) | Guardar preferências (`config.json`, incluindo o e-mail, se informado) e os modelos baixados |

**Serviços de terceiros.** Google, MyMemory e Microsoft recebem os dados acima conforme as políticas deles: [Google](https://policies.google.com/privacy), [MyMemory](https://mymemory.translated.net/doc/en/tos.php) e [Microsoft](https://privacy.microsoft.com/). Para não enviar nada, use um modelo offline e deixe a tradução desligada.

**Contato:** abra uma issue em https://github.com/wercelyduarte/VozComanda/issues

## English

VozComanda has no account, ads or tracking, and **sends no data to the developer's servers**. What leaves your computer goes straight to the services below, and only when you use the matching feature.

**What the app accesses, and why**

| Access | Purpose |
|---|---|
| Microphone | Record your voice while **Record** is on. Nothing is recorded otherwise, and the audio is not saved to disk |
| Google Speech (**Google online** mode) | Transcribe the recorded audio. The audio is sent to Google. In **offline (Whisper)** mode transcription runs on your PC and no audio leaves it |
| MyMemory (`mymemory.translated.net`) and, if it fails, Google Translate | Translate the text when you turn translation on or click **⇔ Translate**. The text is sent to the service. If you enter an e-mail, it is sent to MyMemory to raise the daily limit |
| Microsoft online voice (Microsoft Edge read-aloud service) | Read the text aloud when you click **🔊 Listen** in **Google online** mode. The text is sent to Microsoft. In **offline** mode, reading uses the system's own voices (Windows, or espeak-ng on Linux) and nothing leaves your PC |
| Hugging Face (`huggingface.co`) | Download the chosen offline model, once. None of your data is sent |
| A folder you choose | Save `comando.txt` and the history in `historico/` |
| `%LOCALAPPDATA%\VozComanda` (Windows) or `~/snap/vozcomanda/common` (Linux) | Keep preferences (`config.json`, including the e-mail if entered) and the downloaded models |

**Third-party services.** Google, MyMemory and Microsoft receive the data above under their own policies: [Google](https://policies.google.com/privacy), [MyMemory](https://mymemory.translated.net/doc/en/tos.php) and [Microsoft](https://privacy.microsoft.com/). To send nothing, use an offline model and leave translation off.

**Contact:** open an issue at https://github.com/wercelyduarte/VozComanda/issues
