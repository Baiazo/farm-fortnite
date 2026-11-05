"""Testes do leitor da partida com telas desenhadas aqui: os prints do jogo não vão para o git.

Os números são de blocos (3x5 aumentados 2x), com sombra preta como no jogo, e os modelos saem
de uma tela desenhada do mesmo jeito, como o fazer dos modelos de verdade a partir dos prints.
"""
import math
import os
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import leitura  # noqa: E402
import visao  # noqa: E402

BLOCOS = {
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "001", "001"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    "m": ("11110", "10101", "10101"),
}
ESPACO_M = 4  # espaço antes do "m", como em "524 m"


def _fundo(semente, larg=1920, alt=1080):
    """Cenário cinza com ruído: sem branco nem o azul do pino."""
    rng = np.random.default_rng(semente)
    return Image.fromarray(rng.integers(60, 120, (alt, larg, 3), dtype=np.uint8))


def _letra(a, x, y, c):
    """Desenha um caractere de blocos 2x com sombra preta; devolve a largura."""
    linhas = BLOCOS[c]
    topo = y + (10 - 2 * len(linhas))  # o "m" fica embaixo, na linha de base
    for i, linha in enumerate(linhas):
        for j, b in enumerate(linha):
            if b == "1":
                a[topo + 2 * i + 1:topo + 2 * i + 3, x + 2 * j + 1:x + 2 * j + 3] = 0  # sombra
    for i, linha in enumerate(linhas):
        for j, b in enumerate(linha):
            if b == "1":
                a[topo + 2 * i:topo + 2 * i + 2, x + 2 * j:x + 2 * j + 2] = 255
    return 2 * len(linhas[0])


def _texto(a, x, y, texto):
    """Escreve "352 m" a partir de (x, y); devolve as caixas (x0, largura) de cada caractere."""
    caixas = []
    for c in texto:
        if c == " ":
            x += ESPACO_M - 2
            continue
        larg = _letra(a, x, y, c)
        caixas.append((x, larg))
        x += larg + 2
    return caixas


def _pino(img, x, y):
    d = ImageDraw.Draw(img)
    d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=(0, 0, 0))
    d.polygon([(x - 5, y + 3), (x + 5, y + 3), (x, y + 13)], fill=(0, 0, 0))
    d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=tuple(int(v) for v in leitura.COR_PINO))
    d.ellipse((x - 2, y - 3, x + 2, y + 1), fill=(0, 0, 0))


def _tela(pinos, semente=1):
    """Tela com pinos [(x, y, texto ou None)]."""
    img = _fundo(semente)
    for x, y, _ in pinos:
        _pino(img, x, y)
    a = np.array(img)
    for x, y, texto in pinos:
        if texto:
            _texto(a, x + 10, y + 4, texto)
    return Image.fromarray(a)


def _digitos():
    """Modelos tirados de uma tela desenhada, como os de verdade saem dos prints."""
    a = np.array(_tela([(900, 300, None), (900, 600, None)], semente=7))
    modelos = {}
    for y, texto in ((300, "01234 m"), (600, "56789 m")):
        caixas = _texto(a, 910, y + 4, texto)
        faixa, x0 = leitura.faixa_da_distancia(a, 900, y)
        for c, (cx, larg) in zip(texto.replace(" ", ""), caixas):
            modelos[c] = faixa[:, cx - x0:cx - x0 + larg + 1]
    return modelos


def _icone_bau(img, x, y):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x - 12, y - 10, x + 12, y + 4), radius=4, fill=(250, 250, 250))
    d.rectangle((x - 1, y - 7, x + 1, y), fill=(200, 120, 20))  # fechadura
    d.rounded_rectangle((x - 12, y + 6, x + 12, y + 11), radius=2, fill=(250, 250, 250))


class TestDistancia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.digitos = leitura.Digitos(_digitos())

    def test_le_a_distancia_do_marcador(self):
        m = leitura.achar_marcador(_tela([(900, 500, "352 m")]), self.digitos)
        self.assertEqual(m.distancia, 352)
        self.assertLessEqual(abs(m.x - 900) + abs(m.y - 500), 3)
        self.assertFalse(m.na_borda)

    def test_quatro_numeros_e_pino_na_borda(self):
        m = leitura.achar_marcador(_tela([(47, 600, "1018 m")]), self.digitos)
        self.assertEqual(m.distancia, 1018)
        self.assertTrue(m.na_borda)  # fora da tela, o jogo põe o pino na beira

    def test_varios_valores(self):
        for valor in ("7", "40", "96", "123", "580", "2468"):
            with self.subTest(valor=valor):
                m = leitura.achar_marcador(_tela([(700, 400, f"{valor} m")], semente=int(valor)), self.digitos)
                self.assertEqual(m.distancia if m else None, int(valor))

    def test_ignora_pino_sem_distancia_minimapa_e_faixa_de_cima(self):
        tela = _tela([(900, 500, None), (1800, 100, "120 m"), (600, 30, "77 m")])
        self.assertIsNone(leitura.achar_marcador(tela, self.digitos))

    def test_texto_sem_m_nao_conta(self):
        self.assertIsNone(leitura.achar_marcador(_tela([(900, 500, "352")]), self.digitos))

    def test_sem_pino(self):
        self.assertIsNone(leitura.achar_marcador(_fundo(3), self.digitos))


class TestBauNoAnel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        molde = _fundo(9, 200, 200)
        _icone_bau(molde, 100, 100)
        cls.modelo = visao.Modelo(molde.crop((84, 86, 116, 115)), escala=1)

    def _tela(self, angulo, raio=261, semente=2):
        img = _fundo(semente)
        a = math.radians(angulo)
        _icone_bau(img, round(960 + raio * math.sin(a)), round(540 - raio * math.cos(a)))
        return img

    def test_angulo_do_icone(self):
        for angulo in (0, 90, -45, 170):
            with self.subTest(angulo=angulo):
                icones = leitura.icones_de_bau(self._tela(angulo), self.modelo)
                self.assertEqual(len(icones), 1)
                diferenca = (icones[0].angulo - angulo + 180) % 360 - 180
                self.assertLess(abs(diferenca), 3)

    def test_fora_do_anel_nao_conta(self):
        self.assertEqual(leitura.icones_de_bau(self._tela(30, raio=120), self.modelo), [])


class TestAvisos(unittest.TestCase):
    def _com_aviso(self, semente, x, y):
        img = _fundo(semente)
        d = ImageDraw.Draw(img)
        d.rectangle((x - 6, y - 4, x + 120, y + 22), fill=(30, 30, 30))
        d.text((x, y), "VASCULHAR", fill=(255, 255, 255), font=ImageFont.load_default(size=16))
        return img

    def test_ve_o_aviso_e_onde_ele_esta(self):
        modelo = visao.Modelo(self._com_aviso(4, 100, 100).crop((96, 98, 210, 120)), escala=1)
        nota, x, y = leitura.ver_aviso(self._com_aviso(5, 1200, 600), modelo, "vasculhar")
        self.assertGreater(nota, 0.9)
        self.assertLessEqual(abs(x - 1257) + abs(y - 609), 6)
        nota, _, _ = leitura.ver_aviso(_fundo(6), modelo, "vasculhar")
        self.assertLess(nota, 0.6)


class TestMapa(unittest.TestCase):
    def _ilha(self):
        """Uma "ilha" de manchas coloridas, como o mapa do jogo visto de cima."""
        rng = np.random.default_rng(21)
        img = Image.new("RGB", (220, 200), (20, 60, 140))
        d = ImageDraw.Draw(img)
        for _ in range(60):
            x, y, r = rng.integers(10, 210), rng.integers(10, 190), rng.integers(6, 22)
            d.ellipse((x - r, y - r, x + r, y + r), fill=tuple(int(c) for c in rng.integers(40, 250, 3)))
        return img

    def test_acha_o_lugar_em_outro_zoom(self):
        molde = self._ilha()
        for escala, (x0, y0) in ((1.3, (700, 300)), (0.8, (1200, 600))):
            with self.subTest(escala=escala):
                tela = Image.new("RGB", (1920, 1080), (10, 30, 70))
                larg, alt = round(220 * escala), round(200 * escala)
                tela.paste(molde.resize((larg, alt), Image.LANCZOS), (x0, y0))
                x, y = leitura.ponto_no_mapa(tela, molde, (100, 90))
                self.assertLessEqual(abs(x - (x0 + 100 * escala)) + abs(y - (y0 + 90 * escala)), 8)

    def test_sem_ilha_nao_clica_em_lugar_nenhum(self):
        self.assertIsNone(leitura.ponto_no_mapa(_fundo(13), self._ilha(), (100, 90)))

    def test_pino_do_marcador_no_lugar_do_clique(self):
        tela = _fundo(14)
        _pino(tela, 800, 400)  # a ponta do pino fica uns 13 px abaixo do centro
        self.assertTrue(leitura.pino_perto(tela, 800, 413))
        self.assertFalse(leitura.pino_perto(tela, 1100, 413))


class TestSinais(unittest.TestCase):
    def test_carrega_os_modelos_da_pasta(self):
        with tempfile.TemporaryDirectory() as pasta:
            os.makedirs(os.path.join(pasta, "digitos"))
            for c, f in _digitos().items():
                Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)).save(os.path.join(pasta, "digitos", f"{c}.png"))
            molde = _fundo(9, 200, 200)
            _icone_bau(molde, 100, 100)
            molde.crop((84, 86, 116, 115)).save(os.path.join(pasta, "bau.png"))
            for nome in leitura.REGIAO_AVISOS:
                TestAvisos._com_aviso(None, 4, 100, 100).crop((96, 98, 210, 120)).save(os.path.join(pasta, f"{nome}.png"))
            sinais = leitura.Sinais(pasta)
        self.assertEqual(sinais.marcador(_tela([(900, 500, "64 m")])).distancia, 64)
        self.assertFalse(sinais.aviso(_fundo(8), "vasculhar"))


class TestProcurarVarios(unittest.TestCase):
    def test_acha_os_dois_e_nao_repete(self):
        img = _fundo(11, 800, 600)
        for x, y in ((150, 120), (600, 420)):
            _icone_bau(img, x, y)
        molde = _fundo(9, 200, 200)
        _icone_bau(molde, 100, 100)
        modelo = visao.Modelo(molde.crop((84, 86, 116, 115)), escala=1)
        achados = visao.procurar_varios(visao.Quadro(img, escala=1), modelo, 0.8)
        self.assertEqual(len(achados), 2)
        lugares = sorted((x, y) for _, x, y in achados)
        self.assertLessEqual(abs(lugares[0][0] - 150) + abs(lugares[0][1] - 120), 4)
        self.assertLessEqual(abs(lugares[1][0] - 600) + abs(lugares[1][1] - 420), 4)


if __name__ == "__main__":
    unittest.main()
