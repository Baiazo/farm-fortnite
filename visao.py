"""Print da tela e busca dos botões por correlação cruzada normalizada, só com numpy.

A conta é a mesma do OpenCV (TM_CCOEFF_NORMED): nota 1.0 é encaixe perfeito, perto de 0 é
nada a ver. A correlação sai da FFT e a normalização de imagens integrais, então cada botão
custa poucas dezenas de milissegundos mesmo em tela 1440p.
"""
import os
from datetime import datetime

import numpy as np
from PIL import Image, ImageGrab

# Busca em meia resolução: 4x menos pixels e precisão de sobra para achar um botão
ESCALA = 0.5


def capturar_tela():
    """Print do monitor principal, em pixels físicos."""
    return ImageGrab.grab()


def tela_preta(img):
    """Print todo preto: é o que sai quando o jogo está em "Tela cheia" exclusiva."""
    amostra = np.asarray(img.convert("L").resize((160, 90), Image.BOX))
    return int(amostra.max()) <= 12


def salvar_print(img, pasta, manter=20):
    """Guarda o print em `pasta` e apaga os mais antigos, para a pasta não crescer sem fim."""
    os.makedirs(pasta, exist_ok=True)
    nome = datetime.now().strftime("travado-%Y%m%d-%H%M%S-%f")[:-3] + ".jpg"
    caminho = os.path.join(pasta, nome)
    img.convert("RGB").save(caminho, quality=90)
    salvos = sorted(f for f in os.listdir(pasta) if f.startswith("travado-") and f.endswith(".jpg"))
    for antigo in salvos[:-manter]:
        os.remove(os.path.join(pasta, antigo))
    return caminho


def _preparar(img):
    """Cinza, reduzido pela ESCALA, em float64."""
    cinza = img.convert("L")
    larg, alt = cinza.size
    tamanho = (max(1, round(larg * ESCALA)), max(1, round(alt * ESCALA)))
    return np.asarray(cinza.resize(tamanho, Image.BOX), dtype=np.float64)


def _integral(a):
    ii = np.zeros((a.shape[0] + 1, a.shape[1] + 1))
    np.cumsum(np.cumsum(a, axis=0), axis=1, out=ii[1:, 1:])
    return ii


def _soma_janelas(ii, h, w):
    """Soma de cada janela h x w, para todas as posições válidas."""
    return ii[h:, w:] - ii[:-h, w:] - ii[h:, :-w] + ii[:-h, :-w]


class Modelo:
    """Imagem de um botão pronta para busca."""

    def __init__(self, img):
        t = _preparar(img)
        self.altura, self.largura = t.shape
        self.centrado = t - t.mean()
        self.norma = float(np.sqrt((self.centrado ** 2).sum()))
        # desvio menor que 2 tons de cinza: não tem desenho para reconhecer
        if self.norma < 2 * np.sqrt(t.size):
            raise ValueError("imagem lisa demais, inclua o texto do botão")
        self._fft = {}  # cache por tamanho de tela

    def fft(self, forma):
        if forma not in self._fft:
            self._fft[forma] = np.conj(np.fft.rfft2(self.centrado, s=forma))
        return self._fft[forma]


def carregar_modelo(caminho):
    with Image.open(caminho) as img:
        return Modelo(img)


class Quadro:
    """Tela preparada uma vez e reaproveitada na busca de todos os botões."""

    def __init__(self, img):
        dados = _preparar(img)
        self.forma = dados.shape
        self.fft = np.fft.rfft2(dados)
        self.soma = _integral(dados)
        self.soma2 = _integral(dados ** 2)


def procurar(quadro, modelo):
    """Melhor encaixe do botão na tela: (nota, x, y), com x/y no centro, em pixels da tela."""
    H, W = quadro.forma
    h, w = modelo.altura, modelo.largura
    if h > H or w > W:
        return 0.0, 0, 0
    # correlação circular; nas posições válidas o molde não dá a volta na borda
    corr = np.fft.irfft2(quadro.fft * modelo.fft(quadro.forma), s=quadro.forma)[: H - h + 1, : W - w + 1]
    n = h * w
    s1 = _soma_janelas(quadro.soma, h, w)
    var = _soma_janelas(quadro.soma2, h, w) - s1 * s1 / n
    nota = np.zeros_like(corr)
    # região lisa da tela não tem como bater com o botão e daria divisão instável
    ok = var > n
    nota[ok] = corr[ok] / (modelo.norma * np.sqrt(var[ok]))
    y, x = np.unravel_index(int(np.argmax(nota)), nota.shape)
    melhor = float(np.clip(nota[y, x], -1.0, 1.0))
    return melhor, round((x + w / 2) / ESCALA), round((y + h / 2) / ESCALA)


def recortar(img, x0, y0, x1, y1):
    """Recorta a área arrastada pelo usuário. Devolve (imagem, None) ou (None, motivo)."""
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    larg, alt = img.size
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(larg, x1), min(alt, y1)
    if x1 - x0 < 12 or y1 - y0 < 12:
        return None, "Área pequena demais"
    if (x1 - x0) * (y1 - y0) > 0.15 * larg * alt:
        return None, "Área grande demais: arraste só em volta do botão"
    pedaco = img.crop((x0, y0, x1, y1))
    try:
        Modelo(pedaco)
    except ValueError as e:
        return None, str(e).capitalize()
    return pedaco, None
