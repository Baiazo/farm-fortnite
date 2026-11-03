"""Testes sem mexer no mouse nem no teclado: busca de botões, recorte, ajustes e atalho global."""
import ctypes
import json
import os
import sys
import tempfile
import time
import unittest

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import entrada  # noqa: E402
import visao  # noqa: E402
from config import Ajustes  # noqa: E402


def _tela_falsa(larg=1920, alt=1080, semente=0):
    """Fundo com gradiente e ruído leve, parecido com cenário de jogo."""
    rng = np.random.default_rng(semente)
    x = np.linspace(0, 120, larg)[None, :]
    y = np.linspace(0, 60, alt)[:, None]
    base = 60 + x + y + rng.normal(0, 6, (alt, larg))
    rgb = np.clip(np.stack([base, base * 0.9, base * 1.1], axis=2), 0, 255).astype(np.uint8)
    return Image.fromarray(rgb)


def _desenhar_botao(img, x, y, texto):
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x, y, x + 260, y + 80), radius=10, fill=(250, 220, 40))
    d.text((x + 40, y + 25), texto, fill=(20, 20, 20), font_size=32)


class TestVisao(unittest.TestCase):
    def test_acha_botao_em_outra_posicao(self):
        origem = _tela_falsa(semente=1)
        _desenhar_botao(origem, 300, 200, "JOGAR")
        modelo = visao.Modelo(origem.crop((300, 200, 560, 280)))

        tela = _tela_falsa(semente=2)
        _desenhar_botao(tela, 1500, 900, "JOGAR")
        nota, x, y = visao.procurar(visao.Quadro(tela), modelo)
        self.assertGreater(nota, 0.9)
        self.assertLessEqual(abs(x - 1630), 3)
        self.assertLessEqual(abs(y - 940), 3)

    def test_nao_confunde_botao_diferente(self):
        origem = _tela_falsa(semente=1)
        _desenhar_botao(origem, 300, 200, "JOGAR")
        modelo = visao.Modelo(origem.crop((300, 200, 560, 280)))

        tela = _tela_falsa(semente=3)
        _desenhar_botao(tela, 800, 500, "PULAR")
        nota, _, _ = visao.procurar(visao.Quadro(tela), modelo)
        self.assertLess(nota, 0.8)

    def test_tela_sem_botao(self):
        origem = _tela_falsa(semente=1)
        _desenhar_botao(origem, 300, 200, "JOGAR")
        modelo = visao.Modelo(origem.crop((300, 200, 560, 280)))
        nota, _, _ = visao.procurar(visao.Quadro(_tela_falsa(semente=4)), modelo)
        self.assertLess(nota, 0.5)

    def test_modelo_maior_que_tela(self):
        modelo = visao.Modelo(_tela_falsa(400, 300))
        self.assertEqual(visao.procurar(visao.Quadro(_tela_falsa(200, 150)), modelo), (0.0, 0, 0))

    def test_recorte_valida_tamanho_e_conteudo(self):
        tela = _tela_falsa()
        _desenhar_botao(tela, 300, 200, "JOGAR")
        pedaco, erro = visao.recortar(tela, 560, 280, 300, 200)  # arrastado de baixo para cima
        self.assertIsNone(erro)
        self.assertEqual(pedaco.size, (260, 80))
        self.assertIsNotNone(visao.recortar(tela, 10, 10, 15, 15)[1])        # pequeno
        self.assertIsNotNone(visao.recortar(tela, 0, 0, 1900, 1000)[1])      # grande
        lisa = Image.new("RGB", (800, 600), (40, 40, 40))
        self.assertIsNotNone(visao.recortar(lisa, 10, 10, 200, 100)[1])      # sem desenho

    def test_desempenho_seis_botoes_1440p(self):
        origem = _tela_falsa(semente=1)
        _desenhar_botao(origem, 300, 200, "JOGAR")
        modelos = [visao.Modelo(origem.crop((300, 200, 560, 280))) for _ in range(6)]
        tela = _tela_falsa(2560, 1440, semente=5)
        visao.procurar(visao.Quadro(tela), modelos[0])  # aquece o cache de FFT
        inicio = time.perf_counter()
        quadro = visao.Quadro(tela)
        for m in modelos:
            visao.procurar(quadro, m)
        gasto = time.perf_counter() - inicio
        print(f"\n  print 1440p + 6 botões: {gasto * 1000:.0f} ms")
        self.assertLess(gasto, 1.5)


class TestAjustes(unittest.TestCase):
    def _carregar(self, conteudo):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "ajustes.json")
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(conteudo)
            return Ajustes.carregar(caminho)

    def test_json_quebrado_usa_padrao(self):
        self.assertEqual(self._carregar("{nada"), Ajustes())
        self.assertEqual(self._carregar("[1, 2]"), Ajustes())

    def test_tipos_errados_e_faixa(self):
        a = self._carregar(json.dumps({"limiar": 5, "intervalo": "rápido", "anti_afk": "sim", "afk_a_cada": 0}))
        self.assertEqual(a.limiar, 0.99)
        self.assertEqual(a.intervalo, Ajustes().intervalo)
        self.assertIs(a.anti_afk, True)
        self.assertEqual(a.afk_a_cada, 1.0)

    def test_salvar_e_ler(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "ajustes.json")
            Ajustes(limiar=0.85, anti_afk=False).salvar(caminho)
            a = Ajustes.carregar(caminho)
        self.assertEqual((a.limiar, a.anti_afk), (0.85, False))


class TestEntrada(unittest.TestCase):
    def test_tamanho_da_estrutura_input(self):
        # SendInput rejeita o evento se o tamanho não bater com o do Windows
        self.assertEqual(ctypes.sizeof(entrada.INPUT), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)

    def test_atalho_global_registra_e_encerra(self):
        atalho = entrada.AtalhoGlobal(lambda: None, vk=0x87)  # F24: tecla que ninguém usa
        self.assertIsNone(atalho.iniciar())
        atalho.encerrar()
        atalho.join(2)
        self.assertFalse(atalho.is_alive())


if __name__ == "__main__":
    unittest.main()
