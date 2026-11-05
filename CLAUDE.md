# Farm Automático — Fortnite

Bot em Python que farma partidas do Fortnite em português: reconhece os botões na tela por imagem
e clica sozinho. Repositório público: https://github.com/Baiazo/farm-fortnite

## Origem

Feito em 2026-11-03 para substituir o `pk-auto.exe` do repo `ppkk12/fortnite-automatic-lap`. O
Python publicado lá era limpo, mas o .exe trazia o código criptografado com PyArmor e não dava para
confirmar que era o mesmo. Este projeto foi escrito do zero, sem copiar código de lá.

## Como rodar

- Abrir pelo exe: `gerar_exe.bat` gera `dist\Farm\Farm.exe` (PyInstaller 6, `--onedir`, escolha do
  Matheus: abre na hora e o antivírus barra menos que o arquivo único). O exe roda sem Python.
- Abrir pelo código: `iniciar.bat` (roda `pythonw farm.py`). Python 3.12 instalado no PC do Matheus.
- Testes: `python -m unittest discover -s testes -v`
- Pelo exe, `config.PASTA` é a pasta do `Farm.exe` (`sys.frozen`): botões, ajustes e registros
  ficam ao lado dele. Gerar de novo troca só `Farm.exe` e `_internal` e nunca apaga esses dados.

## Arquitetura

| Arquivo | Papel |
|---|---|
| `farm.py` | Janela Tk com tema próprio (cores em `COR`, fontes Bahnschrift/Segoe UI), captura dos botões, teste na tela, F9 (um print) e F10 (um print por segundo) para gravar a partida, ciclo de vida |
| `automacao.py` | Thread que lê a tela, clica e grava prints da partida (opção, `auto-*.png`, até 200 por vez) + thread do anti-AFK (anda, pula e vira a câmera com mouse relativo, tempos sorteados) + `GravacaoSeguida` do F10 (`seguido-*.png`, só com o jogo em foco, até 300). Tudo que mexe fora do programa passa por `Sistema`, que os testes trocam por um falso |
| `visao.py` | Correlação normalizada (mesma conta do `TM_CCOEFF_NORMED`) via FFT com numpy, em meia resolução (ou `escala=1` para ícones pequenos); `procurar_varios`; print preto e prints de travamento |
| `leitura.py` | Leitor da partida: pino do marcador pela cor (22,124,231) + distância lida com modelos dos dígitos, ícone de baú no anel da mira (ângulo), avisos PULAR e VASCULHAR. Modelos em `sinais/` |
| `piloto.py` | Piloto (opção `piloto`, desligada por padrão): fases esperando → onibus → queda/a_pe → baus → fim; distância só vale com duas leituras que concordam, saltos de leitura descartados. Roda numa thread da `Automacao`; o anti-AFK para e não pula enquanto ele existe |
| `entrada.py` | `SendInput` com scan codes, F8, F9 e F10 por `RegisterHotKey` (id = tecla), janela em foco (título e classe, sem abrir o processo do jogo); DPI real e prioridade abaixo do normal |
| `config.py` | `BOTOES` (a ordem é a prioridade de clique; `max_cliques` por botão), `Ajustes` salvos em `ajustes.json`, `LIMITES` |
| `gerar_exe.py` | Chama o PyInstaller (ícone e versão gerados na hora em `build/`) e troca o programa em `dist\Farm\` mantendo os dados |

## Regras

- Comentários, textos da interface e README em português do Brasil.
- Dependências: só `numpy` e `Pillow` (mais o `PyInstaller`, só para gerar o exe). Biblioteca nova
  só com OK do Matheus, antes de baixar.
- Nada de acesso à rede, leitura de memória do jogo, hook de teclado ou código ofuscado.
- O exe só sai do `gerar_exe.bat`, no PC, a partir deste código: nunca baixado pronto, nunca
  ofuscado e nunca no git (`build/` e `dist/` estão no `.gitignore`).
- Testes nunca mexem no mouse nem apertam tecla de verdade (o atalho é testado com F24).
- Não abrir o Fortnite nem clicar na tela do Matheus sem pedir.
- `botoes/`, `sinais/`, `prints/`, `gravacao/`, `ajustes.json`, `registro.log` e `erro.log` ficam
  fora do git: são prints do jogo e dados da máquina. Por isso os testes do leitor desenham telas
  falsas em vez de usar os prints.
- O repositório é público desde a criação (2026-11-03), por escolha do Matheus. Tudo que vai para o
  git fica aberto: nada de print do jogo, dado da máquina, senha ou chave.
- Automatizar o jogo viola os termos da Epic e pode banir a conta: avisar quando uma mudança aumentar esse risco.

## Estado

- 67 testes passando; janela, estados e captura conferidos por print com botões falsos.
- `Farm.exe` gerado e aberto aqui (abre em ~4 s, dados ao lado do exe, fecha sem erro).
- Primeiro teste no Fortnite de verdade em 2026-11-03, pelo `Farm.exe`: pausou com o jogo fora de
  foco e voltou sozinho, clicou em Jogar (nota 0,98), a partida começou, o personagem morreu em ~4
  min e o farm clicou em Voltar ao saguão (0,92) e em Jogar de novo. Continuar e Pop-up têm imagem
  mas ainda não apareceram; Resgatar tudo e Pular estão sem imagem. As imagens que ele capturou em
  Pop-up e Continuar são do botão PULAR, e a do Continuar pegou junto um texto de outro programa
  que fica por cima da tela.
- Noite de 2026-11-03 para 04, com o anti-AFK novo: 36 partidas seguidas sem erro (22:47 a 07:18,
  ~14 min cada) e 281 prints `auto-`. Ele joga em esquadrão (3 colegas); depois de morrer o jogo
  fica no modo espectador por 5 a 10 min até aparecer o Voltar ao saguão. Quase sempre morre na
  tempestade. O pulo do anti-AFK também sai no ônibus, então ele salta cedo e cai muito no mar.
- Próxima fase, decidida com o Matheus em 2026-11-04: cair sempre no mesmo lugar e abrir baús,
  guiado por marcador. Repetir os comandos dele não serve, porque a rota do ônibus muda a cada
  partida. Plano: abrir o mapa (M) e marcar o lugar; no ônibus, ler a distância até o marcador na
  bússola e pular quando ela parar de cair; na queda, virar a câmera até o marcador ficar no centro
  da bússola e segurar W; no chão, andar até o aviso "Abrir" e segurar E. Tudo por imagem, com
  modelos recortados dos prints dele (F9/F10). Gravar o teclado dele foi descartado: precisaria
  mudar a regra do hook. NitroGen fica só como curiosidade (ver memória `nitrogen-teste`). Mirar ou
  atirar em jogador fica de fora. Já foi avisado: andar e lootear sozinho aumenta bastante o risco
  de ban.
- Partida solo gravada por ele em 2026-11-05 (F9 + F10, 200 prints, marcador no Resort da
  Borracha, 5 baús na Enseada do Saque). O que se aprendeu: o marcador aparece no mundo como pino
  azul com a distância ("982 m") desde o ônibus, e na borda da tela quando está fora dela; no
  ônibus aparece "Espaço PARA PULAR"; o aviso do baú é "VASCULHAR" e a tecla de interagir dele é
  X; o "Visualizar efeitos sonoros" põe o ícone de baú num anel de 261 px em volta da mira; o zoom
  e a posição do mapa (M) mudam entre aberturas, então marcar o lugar vai exigir achar a ilha no
  mapa por imagem. Na queda aparece também um pino fixo com "TRAJETÓRIA", sem distância (ignorado).
- Leitor (`leitura.py`) testado nesses prints: distância certa em 20 de 23 rótulos conferidos,
  sequência da queda coerente (911 → 8 m), VASCULHAR e PULAR sem alarme falso, baú no anel com
  ângulo de +8° a +13° na hora de vasculhar. Erros que sobram: leituras soltas com um "1" a mais
  (o controle vai ter que ignorar saltos). Custa ~200 ms o marcador, ~100 ms o baú e ~200 ms os
  dois avisos por print. Os modelos e as ferramentas que os montaram (`fazer_sinais.py`,
  `avaliar.py`...) estão em `sinais/` e `sinais/ferramentas/`, fora do git.
- Mouse relativo do `SendInput` vira a câmera no Fortnite: nos prints `auto-` da madrugada, com o
  personagem vivo, o rumo da bússola muda a cada print (andar com W/A/S/D não muda o rumo).
- Piloto (`piloto.py`) ensaiado nos 200 prints de 2026-11-05 com sistema falso: guia a queda de
  852 a 21 m com viradas pequenas, muda para baús a 21 m, segura X nos 4 VASCULHAR e encerra no
  tempo. Ganhos chutados (0,8 unidade de mouse por pixel, 10 por grau): conferir no primeiro teste
  de verdade. Ainda não testado: a hora do pulo do ônibus (só há 1 print de ônibus) e tudo ao vivo.
- Próximo passo: teste ao vivo com ele pondo o marcador à mão; depois, o farm pôr o marcador no
  mapa sozinho (achar a ilha no mapa por imagem, porque o zoom muda).
