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
- F8 e F9 são registrados no sistema com `RegisterHotKey`: não existe hook de teclado, ele não lê
  o que você digita.
- Roda com prioridade abaixo do normal para não pesar no jogo.
- **Não** lê nem altera a memória do jogo, **não** acessa a internet e **não** precisa de
  administrador para abrir. Todo o código está aqui, em texto, sem nada criptografado. O
  `Farm.exe` é gerado no seu PC a partir deste código, pelo `gerar_exe.bat`.

## Instalar

Precisa de Windows 10 ou 11. Há dois jeitos de rodar.

### Pelo Farm.exe (sem instalar nada para usar)

1. Rode o `gerar_exe.bat` uma vez. Ele precisa do Python ([python.org](https://www.python.org/downloads/),
   marque "Add python.exe to PATH") só para gerar o exe e instala sozinho o `numpy`, o `Pillow` e o
   `PyInstaller` se faltarem. Leva 1 ou 2 minutos.
2. O programa fica em `dist\Farm\`: abra o **Farm.exe**. Ele roda sem Python e sem biblioteca
   nenhuma instalada.
3. Pode mover ou copiar a pasta `Farm` inteira para onde quiser (até para outro PC). O `Farm.exe`
   precisa da pasta `_internal` ao lado dele. Os botões capturados e os ajustes ficam nessa mesma
   pasta.

Depois de mudar o código, rode o `gerar_exe.bat` de novo (com o farm fechado): ele troca só o
programa e mantém os botões, os ajustes e os registros que estão em `dist\Farm\`.

### Pelo código

Com o Python instalado, instale as bibliotecas uma vez e abra o `iniciar.bat`:

```bash
pip install -r requirements.txt
```

## Primeira vez: capturar os botões

O farm reconhece os botões por imagem, então as imagens têm que sair do **seu** jogo, na sua
resolução e no seu idioma (português).

1. No Fortnite, use **Modo de janela: Tela cheia em janela** e deixe o jogo no monitor principal.
2. Abra o farm (`Farm.exe` ou `iniciar.bat`).
3. Na lista **1. Imagens dos botões**, clique em **Capturar** ao lado do botão. Você tem 3 s para
   voltar ao jogo com o botão aparecendo na tela.
4. A tela congela e escurece. Arraste um retângulo **justo em volta do texto do botão** (ex.: só
   o "JOGAR"): a área escolhida fica clara e mostra o tamanho. Esc ou botão direito cancela.
5. Repita para os outros. Só **Jogar** é obrigatório; os que ficarem como "falta" são ignorados.
6. Use **Testar na tela do jogo (3 s)** para conferir: ele mostra a nota de cada botão ao lado
   dele (verde a partir de 0,80 é encontrado) e diz se reconheceu a janela do Fortnite em foco.

As imagens ficam na pasta `botoes/`, ao lado do `Farm.exe` (ou do `farm.py`). Se mudar a resolução, a escala da interface ou o idioma do
jogo, capture de novo.

## Usar

1. Deixe o Fortnite no saguão, no modo que você quer jogar.
2. Aperte **F8** (ou o botão Iniciar). F8 de novo para.
3. O topo da janela mostra o que ele está fazendo (procurando botões, na partida, pausado) e a
   faixa colorida em cima muda de cor junto. O registro mostra cada clique.

## Gravar prints da partida (F9)

Material para ensinar o farm a jogar a partida (ir para a zona segura, achar baú). Com o farm
aberto, jogue uma partida normal você mesmo e aperte **F9** quando aparecer algo útil: ele salva
um print da tela inteira, sem perda, em `gravacao/` (ao lado do `Farm.exe` ou do `farm.py`) e dá
um bipe. Não precisa iniciar o farm para isso.

O que vale gravar, cada um algumas vezes e em lugares diferentes do mapa:

- a bússola no topo da tela, olhando para lados diferentes;
- o minimapa com o círculo da zona, com você dentro e fora dela;
- você dentro da tempestade;
- com "Visualizar efeitos sonoros" ligado, o ícone de baú em volta da mira;
- o aviso para abrir um baú, quando chega perto dele.

Com o farm aberto, o F9 é dele: o jogo não recebe essa tecla. A pasta nunca é limpa sozinha.

## Problemas comuns

| Sintoma | O que fazer |
|---|---|
| Acha o botão mas o clique não pega | Abra o `Farm.exe` (ou o `iniciar.bat`) como administrador: botão direito > Executar como administrador. O Windows bloqueia cliques de programas comuns em janelas com mais permissão. |
| Antivírus bloqueou ou apagou o `Farm.exe` | É falso positivo comum em exe feito com PyInstaller que mexe no mouse. Restaure da quarentena do Windows Defender e libere a pasta `Farm`, ou rode pelo `iniciar.bat`. |
| "O Windows protegeu o computador" em outro PC | Aparece quando a pasta veio pela internet. Clique em Mais informações > Executar assim mesmo. |
| Nunca acha o botão | Capture de novo, mais justo no texto. Confira com o Testar. Baixe a precisão para 0,75. |
| Clica no lugar errado | Suba a precisão para 0,85–0,90 e capture um pedaço com mais desenho. |
| Print sai preto | Use "Tela cheia em janela" em vez de "Tela cheia". O farm avisa quando isso acontece. |
| Fica em PAUSADO com o jogo na frente | Rode o Testar com o jogo aberto e veja que janela ele mostra em foco. Se for o Fortnite com outro nome, desligue "Pausar quando o Fortnite sair do primeiro plano" e avise para ajustar. |
| Parou sozinho: "cliquei 3 vezes" | O jogo não aceitou o clique. Abra como administrador. Se o botão aceita o clique mas continua igual na tela, capture outro pedaço dele. |
| Apareceu print em `prints/` | Ele ficou 10 min sem reconhecer nada. Abra o print, veja qual botão estava na tela e capture. |
| F8 não funciona | Outro programa já usa F8; use o botão Iniciar/Parar. |
| F9 não dá bipe | Veja o registro: outro programa pode estar usando o F9, ou o som do Windows está mudo (o print é salvo do mesmo jeito). |

## Ajustes

Ficam salvos em `ajustes.json`, na pasta do programa (ao lado do `Farm.exe` ou do `farm.py`).

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
| `gerar_exe.bat` / `gerar_exe.py` | Geram `dist\Farm\Farm.exe` com o PyInstaller |
| `testes/` | Testes da busca, dos ajustes, do laço, do anti-AFK e da troca do exe (`python -m unittest discover -s testes`) |
| `registro.log` | Registro de tudo o que ele fez (o anterior fica em `registro.log.1`) |
| `prints/` | Prints de quando ele travou (guarda os 20 mais novos) |
| `gravacao/` | Prints que você salvou com o F9 (nunca apaga) |
