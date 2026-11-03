# Farm Automático — Fortnite

Bot em Python que farma partidas do Fortnite em português: reconhece os botões na tela por imagem
e clica sozinho. Repositório privado: https://github.com/Baiazo/farm-fortnite

## Origem

Feito em 2026-11-03 para substituir o `pk-auto.exe` do repo `ppkk12/fortnite-automatic-lap`. O
Python publicado lá era limpo, mas o .exe trazia o código criptografado com PyArmor e não dava para
confirmar que era o mesmo. Este projeto foi escrito do zero, sem copiar código de lá.

## Como rodar

- Abrir: `iniciar.bat` (roda `pythonw farm.py`). Python 3.12 instalado no PC do Matheus.
- Testes: `python -m unittest discover -s testes -v`

## Arquitetura

| Arquivo | Papel |
|---|---|
| `farm.py` | Janela Tk com tema próprio (cores em `COR`, fontes Bahnschrift/Segoe UI), captura dos botões, teste na tela, ciclo de vida |
| `automacao.py` | Thread que lê a tela e clica + thread do anti-AFK. Tudo que mexe fora do programa passa por `Sistema`, que os testes trocam por um falso |
| `visao.py` | Correlação normalizada (mesma conta do `TM_CCOEFF_NORMED`) via FFT com numpy, em meia resolução; print preto e prints de travamento |
| `entrada.py` | `SendInput` com scan codes, F8 por `RegisterHotKey`, janela em foco (título e classe, sem abrir o processo do jogo); DPI real e prioridade abaixo do normal |
| `config.py` | `BOTOES` (a ordem é a prioridade de clique; `max_cliques` por botão), `Ajustes` salvos em `ajustes.json`, `LIMITES` |

## Regras

- Comentários, textos da interface e README em português do Brasil.
- Dependências: só `numpy` e `Pillow`. Biblioteca nova só com OK do Matheus, antes de baixar.
- Nada de acesso à rede, leitura de memória do jogo, hook de teclado, código ofuscado ou .exe compilado.
- Testes nunca mexem no mouse nem apertam tecla de verdade (o atalho é testado com F24).
- Não abrir o Fortnite nem clicar na tela do Matheus sem pedir.
- `botoes/`, `prints/`, `ajustes.json`, `registro.log` e `erro.log` ficam fora do git: são prints do
  jogo e dados da máquina.
- O repositório é privado. Só tornar público se o Matheus pedir.
- Automatizar o jogo viola os termos da Epic e pode banir a conta: avisar quando uma mudança aumentar esse risco.

## Estado

- 24 testes passando; janela, estados e captura conferidos por print com botões falsos.
- Ainda não testado no Fortnite de verdade. No primeiro teste, conferir: se o Testar reconhece a
  janela do jogo (classe `UnrealWindow`, título começando com "Fortnite"), se os cliques pegam e se
  o Jogar some da tela depois do clique (senão o farm para após 3 cliques).
