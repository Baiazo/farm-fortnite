"""Testes sem mexer no mouse nem no teclado: busca de botões, recorte, ajustes, laço do farm,
anti-AFK e atalho global."""
import ctypes
import json
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import automacao  # noqa: E402
import config  # noqa: E402
import entrada  # noqa: E402
import gerar_exe  # noqa: E402
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

    def test_tela_preta(self):
        self.assertTrue(visao.tela_preta(Image.new("RGB", (1920, 1080))))
        self.assertFalse(visao.tela_preta(_tela_falsa()))

    def test_salvar_print_mantem_so_os_ultimos(self):
        with tempfile.TemporaryDirectory() as pasta:
            for _ in range(3):
                visao.salvar_print(_tela_falsa(320, 180), pasta, manter=2)
                time.sleep(0.002)  # nomes vêm do relógio, em milissegundos
            self.assertEqual(len(os.listdir(pasta)), 2)

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

    def test_dados_ficam_ao_lado_do_exe(self):
        self.assertEqual(config._pasta_do_programa(), os.path.dirname(os.path.abspath(config.__file__)))
        exe = os.path.join(tempfile.gettempdir(), "Farm", "Farm.exe")
        with mock.patch.object(sys, "frozen", True, create=True), mock.patch.object(sys, "executable", exe):
            self.assertEqual(config._pasta_do_programa(), os.path.dirname(exe))


class SistemaFalso:
    """Faz o papel de tela, mouse, teclado e relógio, e anota tudo o que o farm pediu."""

    def __init__(self):
        self.tempo = 1000.0
        self.foco = True
        self.tela = _tela_falsa(320, 180)
        self.cliques = []
        self.teclas = []  # ("apertar" ou "soltar", tecla)
        self.prints = []

    def agora(self):
        return self.tempo

    def capturar_tela(self):
        return self.tela

    def jogo_em_foco(self):
        return self.foco

    def clicar(self, x, y):
        self.cliques.append((x, y))

    def apertar(self, tecla):
        self.teclas.append(("apertar", tecla))

    def soltar(self, tecla):
        self.teclas.append(("soltar", tecla))

    def soltar_tudo(self):
        pass

    def salvar_print(self, img):
        self.prints.append(img)
        return os.path.join("prints", f"travado-{len(self.prints)}.jpg")


def _visivel(x=100, y=200):
    return (0.95, x, y)


def _sumiu():
    return (0.3, 0, 0)


class TestAutomacao(unittest.TestCase):
    def setUp(self):
        self.sistema = SistemaFalso()
        self.avisos = []
        self.farm = automacao.Automacao(
            Ajustes(), {}, lambda texto, tipo="info": self.avisos.append((tipo, texto)), self.sistema
        )

    def _tela(self, **notas):
        """Uma leitura da tela, alguns segundos depois da anterior."""
        self.sistema.tempo += 5
        self.farm.processar({chave: n for chave, n in notas.items()})

    def test_clica_no_botao_de_maior_prioridade(self):
        self._tela(jogar=_visivel(10, 10), aviso=_visivel(50, 60))
        self.assertEqual(self.sistema.cliques, [(50, 60)])

    def test_partida_so_conta_quando_jogar_some(self):
        self._tela(jogar=_visivel())
        self.assertEqual((self.farm.partidas, self.farm.em_partida), (0, False))
        self._tela(jogar=_sumiu())
        self.assertEqual((self.farm.partidas, self.farm.em_partida), (1, True))
        self._tela(voltar=_visivel())
        self.assertFalse(self.farm.em_partida)
        self.assertEqual(len(self.sistema.cliques), 2)

    def test_para_quando_o_clique_nao_pega(self):
        for _ in range(4):
            self._tela(jogar=_visivel())
        self.assertEqual(len(self.sistema.cliques), 3)
        self.assertEqual(self.farm.partidas, 0)
        self.assertTrue(self.farm.parar.is_set())
        self.assertIn("administrador", self.avisos[-1][1])

    def test_popups_seguidos_tem_mais_folga(self):
        for _ in range(5):
            self._tela(resgatar=_visivel())
        self.assertFalse(self.farm.parar.is_set())
        self.assertEqual(len(self.sistema.cliques), 5)

    def test_nao_clica_sem_o_jogo_em_foco(self):
        self.sistema.foco = False
        self._tela(jogar=_visivel())
        self.assertEqual(self.sistema.cliques, [])
        # com a opção desligada, clica mesmo assim
        self.farm.ajustes.so_com_jogo_em_foco = False
        self._tela(jogar=_visivel())
        self.assertEqual(len(self.sistema.cliques), 1)

    def test_pausa_e_volta_com_o_foco(self):
        self.sistema.foco = False
        self.farm._passo()
        self.farm._passo()
        self.assertEqual(self.farm.situacao, "pausado")
        self.assertEqual(sum("Pausado" in texto for _, texto in self.avisos), 1)
        self.sistema.foco = True
        self.farm._passo()
        self.assertEqual(self.farm.situacao, "procurando")

    def test_avisa_print_preto_uma_vez(self):
        self.sistema.tela = Image.new("RGB", (320, 180))
        for _ in range(automacao.PRETAS_PARA_AVISAR + 3):
            self.farm._passo()
        self.assertEqual(self.farm.situacao, "preto")
        self.assertEqual(sum("preto" in texto for _, texto in self.avisos), 1)
        self.sistema.tela = _tela_falsa(320, 180)
        self.farm._passo()
        self.assertEqual(self.farm.situacao, "procurando")

    def test_salva_print_quando_nada_aparece(self):
        self.sistema.tempo += automacao.TRAVADO_FORA - 10
        self.farm.processar({}, "print")
        self.assertEqual(self.sistema.prints, [])
        self.sistema.tempo += 20
        self.farm.processar({}, "print")
        self.farm.processar({}, "print")
        self.assertEqual(self.sistema.prints, ["print"])
        self.assertIn("prints", self.avisos[-1][1])

    def test_anti_afk_so_na_partida(self):
        a = self.farm.ajustes
        for _ in range(3):
            self.sistema.tempo += a.afk_a_cada
            self.farm._passo_afk()
        self.assertEqual(self.sistema.teclas, [])

        self.farm.em_partida = True
        self.farm._passo_afk()
        self.sistema.tempo += a.afk_a_cada
        self.farm._passo_afk()
        self.assertEqual(self.sistema.teclas[0][0], "apertar")
        self.sistema.tempo += a.afk_segurar
        self.farm._passo_afk()
        self.assertEqual(self.sistema.teclas[1], ("soltar", self.sistema.teclas[0][1]))

    def test_anti_afk_solta_a_tecla_se_o_jogo_sai_do_foco(self):
        self.farm.em_partida = True
        self.farm._passo_afk()
        self.sistema.tempo += self.farm.ajustes.afk_a_cada
        self.farm._passo_afk()
        self.sistema.foco = False
        self.sistema.tempo += 0.1
        self.farm._passo_afk()
        self.assertEqual([acao for acao, _ in self.sistema.teclas], ["apertar", "soltar"])
        self.sistema.tempo += 60
        self.farm._passo_afk()
        self.assertEqual(len(self.sistema.teclas), 2)


class TestEntrada(unittest.TestCase):
    def test_reconhece_so_a_janela_do_jogo(self):
        self.assertTrue(entrada.eh_janela_do_jogo("Fortnite  ", "UnrealWindow"))
        self.assertFalse(entrada.eh_janela_do_jogo("Fortnite - YouTube - Google Chrome", "Chrome_WidgetWin_1"))
        self.assertFalse(entrada.eh_janela_do_jogo("Fortnite.txt - Bloco de Notas", "Notepad"))
        self.assertFalse(entrada.eh_janela_do_jogo("", ""))

    def test_tamanho_da_estrutura_input(self):
        # SendInput rejeita o evento se o tamanho não bater com o do Windows
        self.assertEqual(ctypes.sizeof(entrada.INPUT), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)

    def test_atalho_global_registra_e_encerra(self):
        atalho = entrada.AtalhoGlobal(lambda: None, vk=0x87)  # F24: tecla que ninguém usa
        self.assertIsNone(atalho.iniciar())
        atalho.encerrar()
        atalho.join(2)
        self.assertFalse(atalho.is_alive())


def _escrever(caminho, texto=""):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(texto)


def _ler(caminho):
    with open(caminho, encoding="utf-8") as f:
        return f.read()


class TestGerarExe(unittest.TestCase):
    def _trocar(self, raiz, saida, novo):
        with mock.patch.object(gerar_exe, "AQUI", raiz), mock.patch.object(gerar_exe, "SAIDA", saida):
            gerar_exe._trocar_programa(novo)

    def test_gerar_de_novo_mantem_os_dados(self):
        with tempfile.TemporaryDirectory() as raiz:
            saida, novo = os.path.join(raiz, "dist", "Farm"), os.path.join(raiz, "novo")
            _escrever(os.path.join(saida, "Farm.exe"), "velho")
            _escrever(os.path.join(saida, "_internal", "velho.pyd"))
            _escrever(os.path.join(saida, "botoes", "jogar.png"), "capturado no exe")
            _escrever(os.path.join(saida, "ajustes.json"), "{}")
            _escrever(os.path.join(novo, "Farm.exe"), "novo")
            _escrever(os.path.join(novo, "_internal", "novo.pyd"))
            _escrever(os.path.join(raiz, "botoes", "jogar.png"), "capturado no .py")
            self._trocar(raiz, saida, novo)
            self.assertEqual(_ler(os.path.join(saida, "Farm.exe")), "novo")
            self.assertEqual(os.listdir(os.path.join(saida, "_internal")), ["novo.pyd"])
            self.assertEqual(_ler(os.path.join(saida, "botoes", "jogar.png")), "capturado no exe")
            self.assertTrue(os.path.exists(os.path.join(saida, "ajustes.json")))

    def test_primeira_vez_copia_os_botoes_do_projeto(self):
        with tempfile.TemporaryDirectory() as raiz:
            saida, novo = os.path.join(raiz, "dist", "Farm"), os.path.join(raiz, "novo")
            _escrever(os.path.join(novo, "Farm.exe"))
            os.makedirs(os.path.join(novo, "_internal"))
            _escrever(os.path.join(raiz, "botoes", "jogar.png"), "capturado no .py")
            self._trocar(raiz, saida, novo)
            self.assertEqual(_ler(os.path.join(saida, "botoes", "jogar.png")), "capturado no .py")
            self.assertFalse(os.path.exists(os.path.join(saida, "ajustes.json")))


if __name__ == "__main__":
    unittest.main()
