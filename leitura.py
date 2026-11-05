"""Leitura do que o jogo mostra durante a partida, para o farm se guiar atÃ© o marcador e os baÃºs.

- O pino azul do marcador e a distÃ¢ncia ao lado dele ("524 m"). Fora da tela, o jogo pÃµe o pino
  na borda, tambÃ©m com a distÃ¢ncia.
- O Ã­cone de baÃº do "Visualizar efeitos sonoros", no anel em volta da mira: o lugar dele no anel
  diz para que lado o baÃº estÃ¡.
- Os avisos "PARA PULAR" (no Ã´nibus) e "VASCULHAR" (perto do baÃº).

Tudo por imagem, em resoluÃ§Ã£o cheia (os Ã­cones tÃªm de 10 a 25 px), com modelos recortados dos
prints do prÃ³prio jogador. Os modelos ficam em sinais/, fora do git, como os botÃµes.
"""
import math
import os
from collections import deque
from dataclasses import dataclass

import numpy as np
from PIL import Image

import visao
from config import PASTA_SINAIS

COR_PINO = np.array([22, 124, 231])  # azul do pino do marcador, o mesmo em todo print
TOLERANCIA_COR = 12
BRANCO = 200       # o texto da distÃ¢ncia Ã© branco com sombra preta
ALTURA_TEXTO = 11  # linhas da faixa do texto da distÃ¢ncia, em 1080p
NOTA_CARACTERE = 0.55
NOTA_M = 0.60
NOTA_BAU = 0.70
NOTA_AVISO = 0.75
# Anel do "Visualizar efeitos sonoros": raio em fraÃ§Ã£o da altura da tela (261 px em 1080p)
ANEL = (0.22, 0.27)
# Onde procurar cada aviso, em fraÃ§Ã£o da tela (x0, y0, x1, y1)
REGIAO_AVISOS = {
    "pular": (0.45, 0.40, 0.80, 0.70),
    "vasculhar": (0.30, 0.20, 0.85, 0.85),
}


@dataclass(frozen=True)
class Marcador:
    x: int
    y: int
    distancia: int  # metros
    na_borda: bool  # fora da tela: o jogo mostra o pino na beira, do lado em que ele estÃ¡


@dataclass(frozen=True)
class IconeBau:
    angulo: float  # graus: 0 em cima da mira (Ã  frente), 90 Ã  direita, -90 Ã  esquerda, Â±180 atrÃ¡s
    raio: float    # pixels da mira atÃ© o Ã­cone
    nota: float


def _componentes(m):
    """Componentes conectados (vizinhanÃ§a 8) de uma mÃ¡scara pequena: lista de (ys, xs)."""
    h, w = m.shape
    visto = np.zeros_like(m, dtype=bool)
    saida = []
    for y0, x0 in zip(*np.nonzero(m)):
        if visto[y0, x0]:
            continue
        fila, ys, xs = deque([(y0, x0)]), [], []
        visto[y0, x0] = True
        while fila:
            y, x = fila.popleft()
            ys.append(y)
            xs.append(x)
            for yy in (y - 1, y, y + 1):
                for xx in (x - 1, x, x + 1):
                    if 0 <= yy < h and 0 <= xx < w and m[yy, xx] and not visto[yy, xx]:
                        visto[yy, xx] = True
                        fila.append((yy, xx))
        saida.append((np.array(ys), np.array(xs)))
    return saida


def achar_pinos(a):
    """Centros dos pinos azuis na tela (array RGB), fora do minimapa: lista de (x, y)."""
    h, w = a.shape[:2]
    f = h / 1080
    m = np.abs(a.astype(np.int16) - COR_PINO).max(axis=2) <= TOLERANCIA_COR
    m[: round(0.21 * h), round(0.88 * w):] = False  # o minimapa e a legenda do mapa tambÃ©m tÃªm o pino
    m[: round(0.07 * h)] = False  # faixa de cima (bÃºssola, barra de nÃ­vel): azuis que nÃ£o sÃ£o o pino
    # blocos de 4x4 com a cor do pino; os componentes sÃ³ sÃ£o montados em volta deles
    b = m[: h // 4 * 4, : w // 4 * 4].reshape(h // 4, 4, w // 4, 4).sum(axis=(1, 3))
    usados = np.zeros(b.shape, dtype=bool)
    achados = []
    for by, bx in zip(*np.nonzero(b >= 4)):
        if usados[by, bx]:
            continue
        y0, x0 = max(0, by - 6), max(0, bx - 6)
        usados[y0:by + 7, x0:bx + 7] = True
        for ys, xs in _componentes(m[y0 * 4:(by + 7) * 4, x0 * 4:(bx + 7) * 4]):
            larg, alt = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
            # cabeÃ§a do pino: uns 12 x 18 px, maior quando estÃ¡ na borda da tela
            if 35 * f * f <= len(ys) <= 160 * f * f and 7 * f <= larg <= 18 * f and 9 * f <= alt <= 24 * f:
                achados.append((int(xs.mean()) + x0 * 4, int(ys.mean()) + y0 * 4))
    return achados


def faixa_da_distancia(a, x, y):
    """Mapa de branco (float) das linhas do texto Ã  direita do pino em (x, y), ou None.
    Devolve (faixa, x da primeira coluna da faixa na tela)."""
    h, w = a.shape[:2]
    x0, x1, y0, y1 = x + 3, min(w, x + 80), max(0, y - 4), min(h, y + 26)
    if x1 - x0 < 20 or y1 - y0 < ALTURA_TEXTO:
        return None
    branco = a[y0:y1, x0:x1].min(axis=2).astype(np.float64)
    linhas = (branco >= BRANCO).sum(axis=1)
    soma = np.convolve(linhas, np.ones(ALTURA_TEXTO), mode="valid")
    if soma.max() < 12:
        return None
    topo = int(np.argmax(soma))
    return branco[topo:topo + ALTURA_TEXTO], x0


def _nota(pedaco, modelo):
    p = pedaco - pedaco.mean()
    norma = np.sqrt((p * p).sum()) * modelo.norma
    return float((p * modelo.centrado).sum() / norma) if norma > 0 else 0.0


class _Caractere:
    def __init__(self, faixa):
        self.largura = faixa.shape[1]
        self.centrado = faixa - faixa.mean()
        self.norma = float(np.sqrt((self.centrado ** 2).sum()))


class Digitos:
    """Modelos dos caracteres da distÃ¢ncia: "0" a "9" e "m", cada um com ALTURA_TEXTO linhas."""

    def __init__(self, modelos):
        self.modelos = {c: _Caractere(np.asarray(f, dtype=np.float64)) for c, f in modelos.items()}
        if "m" not in self.modelos:
            raise ValueError('falta o modelo do "m"')

    @classmethod
    def carregar(cls, pasta=os.path.join(PASTA_SINAIS, "digitos")):
        modelos = {}
        for nome in os.listdir(pasta):
            c, ext = os.path.splitext(nome)
            if ext == ".png" and (c.isdigit() and len(c) == 1 or c == "m"):
                with Image.open(os.path.join(pasta, nome)) as img:
                    modelos[c] = np.asarray(img.convert("L"), dtype=np.float64)
        return cls(modelos)

    def ler(self, faixa):
        """LÃª "524" de uma faixa com "524 m". Devolve None se nÃ£o achar nÃºmeros seguidos do "m".

        O itÃ¡lico encosta um nÃºmero no outro, entÃ£o em vez de separar os pedaÃ§os brancos ele
        testa as divisÃµes possÃ­veis (cada nÃºmero comeÃ§a de 1 px antes a 2 px depois do anterior,
        o "m" vem depois de um espaÃ§o) e fica com a de melhor nota no conjunto.
        """
        larg = faixa.shape[1]
        colunas = np.nonzero((faixa >= BRANCO).any(axis=0))[0]
        if not len(colunas):
            return None
        notas = {
            c: [_nota(faixa[:, x:x + m.largura], m) for x in range(larg - m.largura + 1)]
            for c, m in self.modelos.items()
        }
        larguras = {c: m.largura for c, m in self.modelos.items()}
        tem_branco = np.concatenate([[0], np.cumsum((faixa >= BRANCO).any(axis=0))])

        def nota(c, x):
            return notas[c][x] if 0 <= x < len(notas[c]) else -1.0

        def buraco(x0, x1):
            # colunas brancas que ficaram sem caractere: um "1" no lugar de um nÃºmero largo deixa sobra
            return 0.15 * float(tem_branco[min(max(x1, 0), larg)] - tem_branco[min(max(x0, 0), larg)])

        # fim do Ãºltimo nÃºmero (x) -> (soma das notas - 0,5 por caractere, texto, pior nota)
        estados = {}
        inicio = int(colunas[0])
        # o primeiro nÃºmero pode vir depois de um pedaÃ§o branco que nÃ£o Ã© texto (o ponto do pino)
        for x in range(inicio - 2, inicio + 14):
            for c in "0123456789":
                if c in notas and nota(c, x) > NOTA_CARACTERE - 0.2:
                    _guardar(estados, x + larguras[c], nota(c, x) - 0.5 - buraco(inicio, x), c, nota(c, x))
        melhor = None
        for _ in range(4):  # atÃ© 4 nÃºmeros (9999 m)
            novos = {}
            for fim, (soma, texto, pior) in estados.items():
                for x in range(fim + 1, fim + 7):  # o "m" vem depois de um espaÃ§o
                    n = nota("m", x)
                    total = soma + n - 0.5 - buraco(fim, x)
                    # o "m" tem que ser bem nÃ­tido: o pÃ© de um nÃºmero parece um "m" pela metade
                    if n >= NOTA_M and pior >= NOTA_CARACTERE - 0.2 and (melhor is None or total > melhor[0]):
                        melhor = (total, texto, min(pior, n))
                for x in range(fim - 1, fim + 3):
                    for c in "0123456789":
                        if c in notas and nota(c, x) > NOTA_CARACTERE - 0.2:
                            n = nota(c, x)
                            _guardar(novos, x + larguras[c], soma + n - 0.5 - buraco(fim, x), texto + c, min(pior, n))
            estados = novos
        if melhor is None or melhor[0] <= 0:
            return None
        return melhor[1]


def _guardar(estados, fim, soma, texto, pior):
    if fim not in estados or soma > estados[fim][0]:
        estados[fim] = (soma, texto, pior)


def achar_marcador(img, digitos):
    """O marcador na tela: Marcador ou None. Pinos sem distÃ¢ncia ao lado (o da "TRAJETÃ“RIA" na
    queda, por exemplo) sÃ£o ignorados."""
    a = np.asarray(img.convert("RGB"))
    h, w = a.shape[:2]
    for x, y in achar_pinos(a):
        faixa = faixa_da_distancia(a, x, y)
        if faixa is None:
            continue
        texto = digitos.ler(faixa[0])
        if texto:
            na_borda = x < 0.05 * w or x > 0.95 * w or y > 0.92 * h
            return Marcador(x, y, int(texto), na_borda)
    return None


def _recorte(img, regiao):
    larg, alt = img.size
    x0, y0, x1, y1 = (round(v * t) for v, t in zip(regiao, (larg, alt, larg, alt)))
    return img.crop((x0, y0, x1, y1)), x0, y0


def ver_aviso(img, modelo, nome):
    """O aviso `nome` ("pular" ou "vasculhar") estÃ¡ na tela? Devolve (nota, x, y)."""
    pedaco, x0, y0 = _recorte(img, REGIAO_AVISOS[nome])
    nota, x, y = visao.procurar(visao.Quadro(pedaco, escala=1), modelo)
    return nota, x + x0, y + y0


def icones_de_bau(img, modelo):
    """Ãcones de baÃº no anel em volta da mira, do mais nÃ­tido para o menos: lista de IconeBau."""
    larg, alt = img.size
    cx, cy, r = larg / 2, alt / 2, ANEL[1] * alt
    pedaco = img.crop((round(cx - r), round(cy - r), round(cx + r), round(cy + r)))
    icones = []
    for nota, x, y in visao.procurar_varios(visao.Quadro(pedaco, escala=1), modelo, NOTA_BAU):
        dx, dy = x - r, y - r
        raio = math.hypot(dx, dy)
        if ANEL[0] * alt <= raio <= r:
            icones.append(IconeBau(math.degrees(math.atan2(dx, -dy)), raio, nota))
    return icones


class Sinais:
    """Todos os modelos de sinais/ carregados de uma vez."""

    def __init__(self, pasta=PASTA_SINAIS):
        self.digitos = Digitos.carregar(os.path.join(pasta, "digitos"))
        self.bau = visao.carregar_modelo(os.path.join(pasta, "bau.png"), escala=1)
        self.avisos = {
            nome: visao.carregar_modelo(os.path.join(pasta, f"{nome}.png"), escala=1) for nome in REGIAO_AVISOS
        }

    def marcador(self, img):
        return achar_marcador(img, self.digitos)

    def baus(self, img):
        return icones_de_bau(img, self.bau)

    def aviso(self, img, nome):
        nota, _, _ = ver_aviso(img, self.avisos[nome], nome)
        return nota >= NOTA_AVISO
