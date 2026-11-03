# Farm Automático — Fortnite

Programa em português que joga partidas em sequência sozinho: clica em **Jogar**, nos pop-ups,
em **Pular** e em **Voltar ao saguão**, e começa de novo. Durante a partida ele pode segurar
W/A/S/D de vez em quando para o jogo não te expulsar por inatividade.

> **Aviso:** automatizar o jogo vai contra os termos de uso do Fortnite e a conta pode ser
> suspensa. Use por sua conta e risco.

## O que ele faz e o que ele não faz

- Tira um print do monitor principal a cada 2 s e procura as imagens dos botões que **você**
  capturou do seu jogo.
- Clica pelo `SendInput` do Windows, o mesmo caminho de um mouse de verdade, e devolve o cursor
  para onde estava.
- Só clica e só aperta W/A/S/D com o Fortnite em primeiro plano. Se você trocar de janela, ele
  pausa sozinho e volta quando o jogo voltar para a frente: o anti-AFK nunca digita no navegador
  nem no WhatsApp.
- Confere cada clique: a partida só conta quando o Jogar some da tela. Se o mesmo botão continuar
  lá depois de 3 cliques (10 nos pop-ups, que às vezes vêm vários seguidos), ele para e avisa.
- Se passar 10 min sem reconhecer nenhum botão (35 min durante a partida), salva um print em
  `prints/` para você ver qual tela travou e capturar o botão que falta.
- Guarda o registro em `registro.log`, para conferir depois o que aconteceu numa sessão longa.
- F8 é registrado no sistema com `RegisterHotKey`: não existe hook de teclado, ele não lê o que
  você digita.
- Roda com prioridade abaixo do normal para não pesar no jogo.
- **Não** lê nem altera a memória do jogo, **não** acessa a internet e **não** precisa de
  administrador para abrir. Todo o código está aqui, em texto, sem nada compilado ou criptografado.

## Requisitos

- Windows 10 ou 11
- Python 3.10 ou mais novo ([python.org](https://www.python.org/downloads/), marque
  "Add python.exe to PATH" na instalação)
- Bibliotecas `numpy` e `Pillow`:

```bash
pip install -r requirements.txt
```

## Primeira vez: capturar os botões

O farm reconhece os botões por imagem, então as imagens têm que sair do **seu** jogo, na sua
resolução e no seu idioma (português).

1. No Fortnite, use **Modo de janela: Tela cheia em janela** e deixe o jogo no monitor principal.
2. Abra o farm com `iniciar.bat`.
3. Na lista **1. Imagens dos botões**, clique em **Capturar** ao lado do botão. Você tem 3 s para
   voltar ao jogo com o botão aparecendo na tela.
4. A tela congela e escurece. Arraste um retângulo **justo em volta do texto do botão** (ex.: só
   o "JOGAR"): a área escolhida fica clara e mostra o tamanho. Esc ou botão direito cancela.
5. Repita para os outros. Só **Jogar** é obrigatório; os que ficarem como "falta" são ignorados.
6. Use **Testar na tela do jogo (3 s)** para conferir: ele mostra a nota de cada botão ao lado
   dele (verde a partir de 0,80 é encontrado) e diz se reconheceu a janela do Fortnite em foco.

As imagens ficam na pasta `botoes/`. Se mudar a resolução, a escala da interface ou o idioma do
jogo, capture de novo.

## Usar

1. Deixe o Fortnite no saguão, no modo que você quer jogar.
2. Aperte **F8** (ou o botão Iniciar). F8 de novo para.
3. O topo da janela mostra o que ele está fazendo (procurando botões, na partida, pausado) e a
   faixa colorida em cima muda de cor junto. O registro mostra cada clique.

## Problemas comuns

| Sintoma | O que fazer |
|---|---|
| Acha o botão mas o clique não pega | Abra o `iniciar.bat` como administrador (botão direito > Executar como administrador). O Windows bloqueia cliques de programas comuns em janelas com mais permissão. |
| Nunca acha o botão | Capture de novo, mais justo no texto. Confira com o Testar. Baixe a precisão para 0,75. |
| Clica no lugar errado | Suba a precisão para 0,85–0,90 e capture um pedaço com mais desenho. |
| Print sai preto | Use "Tela cheia em janela" em vez de "Tela cheia". O farm avisa quando isso acontece. |
| Fica em PAUSADO com o jogo na frente | Rode o Testar com o jogo aberto e veja que janela ele mostra em foco. Se for o Fortnite com outro nome, desligue "Pausar quando o Fortnite sair do primeiro plano" e avise para ajustar. |
| Parou sozinho: "cliquei 3 vezes" | O jogo não aceitou o clique. Abra como administrador. Se o botão aceita o clique mas continua igual na tela, capture outro pedaço dele. |
| Apareceu print em `prints/` | Ele ficou 10 min sem reconhecer nada. Abra o print, veja qual botão estava na tela e capture. |
| F8 não funciona | Outro programa já usa F8; use o botão Iniciar/Parar. |

## Ajustes

Ficam salvos em `ajustes.json`, na própria pasta.

- **Precisão mínima**: nota mínima para considerar que achou o botão (padrão 0,80).
- **Ler a tela a cada**: intervalo entre os prints (padrão 2 s).
- **Pausar quando o Fortnite sair do primeiro plano**: ligado por padrão. Desligue só se ele não
  reconhecer a janela do jogo.
- **Anti-AFK**: segura uma tecla W/A/S/D aleatória por 3 s a cada 10 s, só durante a partida.

## Arquivos

| Arquivo | Para quê |
|---|---|
| `farm.py` | Janela e fluxo de captura |
| `automacao.py` | Laço que lê a tela, clica e faz o anti-AFK |
| `visao.py` | Print da tela e busca dos botões (correlação normalizada com numpy) |
| `entrada.py` | Mouse, teclado e F8 pela API do Windows |
| `config.py` | Lista de botões e ajustes |
| `testes/` | Testes da busca, dos ajustes, do laço e do anti-AFK (`python -m unittest discover -s testes`) |
| `registro.log` | Registro de tudo o que ele fez (o anterior fica em `registro.log.1`) |
| `prints/` | Prints de quando ele travou (guarda os 20 mais novos) |
