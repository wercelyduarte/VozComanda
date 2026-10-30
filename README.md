# 🎤 VozComanda

**Ditado por voz para agentes IA** — converte a fala do microfone em texto, traduz se você quiser e salva como comando para um agente executar (ex.: Kiro, Claude Code).

---

## O que faz

| Etapa | Ação |
|-------|------|
| 1 | Captura o áudio do microfone em tempo real |
| 2 | Transcreve com Google (online) ou faster-whisper (offline), em 10 idiomas |
| 3 | Traduz o texto para outro idioma, se a opção estiver ligada |
| 4 | Exibe o texto numa caixa editável para revisão |
| 5 | Salva em `comando.txt`, na pasta que você escolher — o agente lê e executa |

Também **lê o texto em voz alta** (🔊 Ouvir ou F6): útil para conferir o que foi ditado, para quem tem dificuldade de leitura ou para ouvir a resposta do agente.

Também funciona como **tradutor de texto**: cole qualquer texto na caixa (por exemplo, a resposta de um agente em inglês) e clique em **⇔ Traduzir**.

---

## Modos de reconhecimento

### Google (online)
- Não baixa nada, resultado rápido
- Requer conexão com a internet
- Áudio enviado ao servidor do Google

### Offline — faster-whisper
| Modelo    | Tamanho  | Indicado para        |
|-----------|----------|----------------------|
| tiny      | ~75 MB   | Testes rápidos       |
| base      | ~145 MB  | Uso geral leve       |
| small     | ~480 MB  | Boa precisão         |
| medium    | ~1,5 GB  | Alta precisão        |
| large-v3  | ~3 GB    | Precisão máxima      |

Download feito uma única vez, ficando em `models_whisper/` (ou `%LOCALAPPDATA%\VozComanda\` no executável).

---

## Idiomas e tradução

### Idioma da interface
Português, inglês ou espanhol. Na primeira vez, o app segue o idioma do Windows; para trocar, clique no botão **PT / EN / ES** ao lado do tema.

### Idioma de voz
Escolha o idioma em que você vai falar: Português BR, Português PT, Inglês, Espanhol, Francês, Alemão, Italiano, Japonês, Chinês ou Árabe. Vale para os dois modos de reconhecimento.

### Traduzir ao ditar
Marque **Traduzir para** e escolha o idioma de destino. O texto já aparece traduzido na caixa. Se a tradução falhar, o texto original é mantido e a barra de status avisa.

### Botão ⇔ Traduzir
Traduz o texto da caixa entre o inglês e o seu idioma de voz (se a voz for inglês, o idioma de destino). A direção é detectada automaticamente: texto em inglês vira o seu idioma; qualquer outro vira inglês. A barra de status mostra a direção usada (ex.: `EN → PT`). Textos longos são aceitos.

### Limites da tradução
A tradução usa o [MyMemory](https://mymemory.translated.net/), gratuito e sem chave de API. Ela precisa de internet e envia o texto ao MyMemory.

| Uso        | Limite diário     |
|------------|-------------------|
| Sem e-mail | 5.000 caracteres  |
| Com e-mail | 50.000 caracteres |

Na primeira tradução, o app pede um e-mail opcional para aumentar o limite. O e-mail fica salvo em `config.json` e é enviado ao MyMemory em cada tradução. Para trocar ou remover, apague a linha `mm_email` do `config.json`: o app pergunta de novo na próxima tradução.

A qualidade é boa, mas o MyMemory às vezes escolhe o sentido errado de uma palavra. Revise o texto antes de salvar.

---

## Leitura em voz alta

O botão **🔊 Ouvir** (ou **F6**) lê o texto da caixa; clique de novo para parar. O idioma da leitura é detectado pelo texto (inglês ou o seu idioma).

| Modo              | Voz usada                                                                 |
|-------------------|---------------------------------------------------------------------------|
| Google (online)   | Voz neural da Microsoft, natural, em todos os idiomas. Envia o texto à Microsoft. Sem internet, usa a voz do Windows |
| Offline (Whisper) | Voz do Windows instalada para o idioma. Nada sai do computador            |

Se o Windows não tiver voz para o idioma, instale em *Configurações > Hora e idioma > Fala*.

## Pontuação

A caixa **Pontuação** controla a formatação do texto transcrito:

| Modo              | Marcada                                  | Desmarcada                                  |
|-------------------|------------------------------------------|---------------------------------------------|
| Offline (Whisper) | Pontuação e maiúsculas do próprio modelo | Pontuação removida                          |
| Google (online)   | Ponto nas pausas longas, vírgula nas curtas, maiúscula no início das frases | Texto como o Google devolve, sem pontuação  |

Os acentos são sempre mantidos. O Google gratuito não devolve pontuação nenhuma: com a caixa marcada, o app corta o áudio nas pausas, reconhece cada trecho e junta com vírgula ou ponto conforme a duração da pausa. Ele não acerta pontos de interrogação; para pontuação completa, use um modelo offline (`small` ou maior).

---

## Requisitos

- **Windows 10 ou 11**
- **Python 3.10+** — [download](https://www.python.org/downloads/) (marque *Add python.exe to PATH*)
- Microfone funcionando
- Internet para o modo Google e para a tradução

Dependências instaladas automaticamente pelo launcher:

```
faster-whisper    >= 1.0.0
sounddevice       >= 0.4.6
numpy             >= 1.21
SpeechRecognition >= 3.10
deep-translator   >= 1.11.4
sv-ttk            >= 2.6
edge-tts          >= 7.0
comtypes          >= 1.4
```

---

## Como usar

### Opção mais fácil — duplo clique em `rodar.bat`

Instala as dependências na primeira vez e abre o aplicativo.

### Via terminal

```bash
python vozComanda_bootstrap.py
```

### Fluxo de uso

1. Selecione o modelo (padrão: **Google online**) e o **idioma de voz**
2. Clique **Gravar** ou pressione **F5**
3. Fale normalmente
4. Clique **Parar** ou pressione **F5** novamente
5. Revise/edite o texto na caixa
6. Pressione **Ctrl+S** ou clique **Salvar** — na primeira vez, o app pede a pasta onde salvar
7. Peça ao agente: *"lê o comando.txt e executa"*

### Atalhos de teclado

| Tecla     | Ação                    |
|-----------|-------------------------|
| `F5`      | Gravar / Parar          |
| `Space`   | Gravar / Parar (fora da caixa de texto) |
| `F6`      | Ouvir / parar a leitura |
| `Ctrl+S`  | Salvar comando          |
| `Ctrl+L`  | Limpar texto            |

### Onde os arquivos ficam

- `comando.txt` e a pasta `historico/` vão para a pasta escolhida no primeiro salvamento. Se você cancelar a escolha, eles vão para a pasta do app e a pergunta se repete no próximo salvamento. Para trocar a pasta depois, clique no **⚙** ao lado da caixa Pontuação.
- As preferências (modelo, idiomas, pontuação, pasta e e-mail) ficam em `config.json`: na pasta do app quando ele roda pelo Python, ou em `%LOCALAPPDATA%\VozComanda\` no executável.

---

## Integração com Kiro / outros agentes

O aplicativo salva o comando em `comando.txt` (UTF-8), na pasta que você escolheu.
O agente pode monitorar este arquivo ou você pede explicitamente:

```
"lê o arquivo comando.txt e executa o que estiver lá"
```

Exemplo de leitura no agente:

```python
with open("comando.txt", encoding="utf-8") as f:
    comando = f.read().strip()
```

Um histórico com timestamp é mantido em `historico/comando_YYYYMMDD_HHMMSS.txt`, na mesma pasta.

---

## Build — gerar executável Windows

```bat
build.bat        # gera build\VozComanda\VozComanda.exe
build.bat msi    # gera também o instalador .msi em dist\
```

Requer instalação prévia das dependências de build:

```bash
pip install -r requirements-build.txt
```

### Linux (Snap)

```bash
sudo snap install vozcomanda        # quando estiver publicado na Snap Store
```

O snap é gerado pelo workflow `.github/workflows/snap.yml` (em toda tag `vX.Y.Z`, ou manualmente em *Actions*), a partir de [snap/snapcraft.yaml](snap/snapcraft.yaml). No Linux a voz offline do botão Ouvir é o espeak-ng (já vem no snap) e os dados ficam em `~/snap/vozcomanda/common`. Fora do snap, rode `python3 vozComanda_bootstrap.py` (precisa de `python3-tk`, `libportaudio2` e, para a voz offline, `espeak-ng`).

Para o workflow publicar sozinho, gere a credencial uma vez e salve como segredo `SNAPCRAFT_STORE_CREDENTIALS` no GitHub:

```bash
snapcraft export-login --snaps=vozcomanda --acls package_access,package_push,package_update,package_release -
```

### Microsoft Store (.msix)

```bash
python setup.py build_exe
python build_msix.py     # gera dist\VozComanda-X.Y.Z.msix (requer o Windows SDK)
```

O pacote sai sem assinatura: a Store assina ao publicar. O workflow de release também gera o `.msix`, como artefato da execução. Os textos da Store estão em [docs/store-listing.md](docs/store-listing.md) e a política de privacidade em [PRIVACY.md](PRIVACY.md).

---

## Estrutura do projeto

```
vozComanda/
├── vozComanda.py               # aplicativo principal
├── vozComanda_bootstrap.py     # instala dependências e abre o app
├── rodar.bat               # launcher Windows (duplo clique)
├── build.bat               # gera o executável (.exe / .msi)
├── setup.py                # configuração cx_Freeze
├── requirements.txt        # dependências de runtime
├── requirements-build.txt  # dependências de build (cx_Freeze)
├── vozComanda_icone.py         # recria icone.ico (opcional)
├── icone.ico               # ícone da janela
└── config.json             # preferências  [gerado em uso]
```

`comando.txt` e `historico/` são criados na pasta que você escolher.

---

## Detalhes técnicos

- Áudio capturado a **16 kHz mono** (formato nativo do Whisper)
- **Normalização de volume** antes da transcrição: garante que o áudio não seja muito fraco nem muito alto, melhorando a taxa de acerto
- **Padding de silêncio** de 150 ms no início e 600 ms no final: evita que o decodificador corte a primeira e a última sílaba ao parar a gravação bruscamente
- **VAD com bordas ampliadas** (speech_pad = 400 ms): menos cortes em palavras no modo offline
- Modo offline usa `beam_size=5` e `temperature=0.0`: boa precisão com velocidade otimizada
- **Tradução em blocos** de até 480 caracteres (o MyMemory recusa pedidos acima de 500), sem perder as quebras de linha
- **Detecção de idioma local** (PT/EN), por contagem de palavras frequentes: nenhum serviço externo é chamado para isso
- Se o MyMemory falhar, o app tenta o Google Translate como reserva

---

## Licença

MIT — uso livre, inclusive comercial.

## Licença

[MIT](LICENSE) — uso, cópia e modificação livres, mantendo o aviso de copyright.
