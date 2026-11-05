"""Testes sem mexer no mouse nem no teclado: busca de botões, recorte, ajustes, laço do farm,
anti-AFK e atalho global."""
import ctypes
import json
import os
import queue
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
import farm  # noqa: E402
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

    def test_gravacao_sem_perda_e_sem_apagar(self):
        tela = _tela_falsa(320, 180)
        with tempfile.TemporaryDirectory() as pasta:
            for _ in range(25):  # mais que os 20 que o salvar_print guarda
                caminho = visao.salvar_gravacao(tela, os.path.join(pasta, "gravacao"))
                time.sleep(0.002)
            self.assertEqual(len(os.listdir(os.path.dirname(caminho))), 25)
            with Image.open(caminho) as lida:
                self.assertEqual(np.asarray(lida.convert("RGB")).tobytes(), np.asarray(tela.convert("RGB")).tobytes())
            self.assertTrue(os.path.basename(caminho).startswith("partida-"))
            auto = visao.salvar_gravacao(tela, os.path.join(pasta, "gravacao"), "auto")
            self.assertTrue(os.path.basename(auto).startswith("auto-"))

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
        a = self._carregar(json.dumps(
            {"limiar": 5, "intervalo": "rápido", "anti_afk": "sim", "afk_a_cada": 0, "gravar_a_cada": 1}
        ))
        self.assertEqual(a.limiar, 0.99)
        self.assertEqual(a.intervalo, Ajustes().intervalo)
        self.assertIs(a.anti_afk, True)
        self.assertEqual(a.afk_a_cada, 1.0)
        self.assertEqual(a.gravar_a_cada, 5.0)

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
        self.viradas = []  # quanto o mouse andou em cada passo da câmera
        self.prints = []
        self.gravados = []

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

    def virar(self, dx, dy=0):
        self.viradas.append(dx)

    def salvar_print(self, img):
        self.prints.append(img)
        return os.path.join("prints", f"travado-{len(self.prints)}.jpg")

    def salvar_gravacao(self, img):
        self.gravados.append(img)
        return os.path.join("gravacao", f"auto-{len(self.gravados)}.png")

    def salvar_seguido(self, img):
        self.gravados.append(img)
        return os.path.join("gravacao", f"seguido-{len(self.gravados)}.png")


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
        # tempos do anti-AFK exatamente iguais aos ajustes: o teste não depende da sorte
        self._sem_sorteio = mock.patch.object(automacao, "_sortear", lambda base: base)
        self._sem_sorteio.start()
        self.addCleanup(self._sem_sorteio.stop)

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

    def _afk(self, segundos):
        """Roda o anti-AFK como a thread dele faz: um passo a cada 0,1 s."""
        for _ in range(round(segundos * 10)):
            self.sistema.tempo += 0.1
            self.farm._passo_afk()

    def _apertadas(self):
        return [t for acao, t in self.sistema.teclas if acao == "apertar"]

    def _soltas(self):
        return [t for acao, t in self.sistema.teclas if acao == "soltar"]

    def test_anti_afk_so_na_partida(self):
        a = self.farm.ajustes
        a.afk_variado = False
        self._afk(a.afk_a_cada * 3)
        self.assertEqual(self.sistema.teclas, [])

        self.farm.em_partida = True
        self._afk(a.afk_a_cada + 0.2)  # folga de dois passos de 0,1 s
        self.assertIn(tuple(self._apertadas()), automacao.DIRECOES)
        self.assertEqual(self._soltas(), [])
        self._afk(a.afk_segurar)
        self.assertEqual(self._soltas(), self._apertadas())
        self.assertEqual(self.sistema.viradas, [])

    def test_anti_afk_mexe_varias_vezes(self):
        a = self.farm.ajustes
        self.farm.em_partida = True
        with mock.patch.object(self.farm, "_comecar_movimento", wraps=self.farm._comecar_movimento) as comecar:
            self._afk(60)
        # um movimento a cada afk_segurar + afk_a_cada (4 s no padrão), mais a folga dos passos de 0,1 s
        self.assertGreaterEqual(comecar.call_count, int(60 / (a.afk_segurar + a.afk_a_cada + 0.2)) - 1)

    def test_tempos_sorteados_em_volta_do_ajuste(self):
        self._sem_sorteio.stop()
        try:
            tempos = [automacao._sortear(2.0) for _ in range(50)]
        finally:
            self._sem_sorteio.start()
        menor, maior = automacao.VARIACAO
        self.assertTrue(all(2.0 * menor <= t <= 2.0 * maior for t in tempos))
        self.assertGreater(len(set(tempos)), 1)

    def test_anti_afk_pula_e_vira_a_camera(self):
        a = self.farm.ajustes
        self._afk(0.1)  # um passo no saguão: a pausa começa a contar quando a partida começa
        self.farm.em_partida = True
        with mock.patch.object(automacao.random, "random", return_value=0.0):  # o sorteio sempre cai em pular e virar
            self._afk(a.afk_a_cada + 0.2 + a.afk_segurar + 0.2)  # um movimento inteiro
        total = sum(self.sistema.viradas)
        self.assertTrue(automacao.VIRAR[0] <= abs(total) <= automacao.VIRAR[1])
        self.assertLessEqual(len(self.sistema.viradas), automacao.PASSOS_VIRAR)
        self.assertTrue(all((v > 0) == (total > 0) for v in self.sistema.viradas))  # vira para um lado só
        pulo = self.sistema.teclas.index(("apertar", "espaco"))
        self.assertEqual(self.sistema.teclas[pulo + 1], ("soltar", "espaco"))  # um toque, não fica segurando
        self.assertEqual(sorted(self._apertadas()), sorted(self._soltas()))

    def test_anti_afk_solta_a_tecla_se_o_jogo_sai_do_foco(self):
        self.farm.ajustes.afk_variado = False
        self.farm.em_partida = True
        self._afk(self.farm.ajustes.afk_a_cada + 0.2)
        apertadas = [t for acao, t in self.sistema.teclas if acao == "apertar"]
        self.assertTrue(apertadas)
        self.sistema.foco = False
        self._afk(0.1)
        self.assertEqual([t for acao, t in self.sistema.teclas if acao == "soltar"], apertadas)
        antes = len(self.sistema.teclas)
        self._afk(60)
        self.assertEqual(len(self.sistema.teclas), antes)

    def _com_piloto(self):
        class Sinais:  # só o aviso do ônibus, sempre na tela
            def aviso(self, img, nome):
                return nome == "pular"

            def marcador(self, img):
                return None

            def baus(self, img):
                return []

        self.farm = automacao.Automacao(
            Ajustes(piloto=True), {}, lambda texto, tipo="info": self.avisos.append((tipo, texto)), self.sistema,
            sinais=Sinais(),
        )

    def test_piloto_assume_no_onibus_e_o_anti_afk_para(self):
        self._com_piloto()
        self.farm.em_partida = True
        self.farm._partida_nova.set()
        self.farm._passo_piloto()
        self.assertEqual(self.farm.piloto.fase, "onibus")
        self.assertTrue(self.farm.piloto_no_controle)
        self._afk(30)
        self.assertEqual(self.sistema.teclas, [])  # o anti-AFK não mexe enquanto o piloto está no controle

    def test_partida_nova_recomeca_o_piloto(self):
        self._com_piloto()
        self.farm.piloto.fase = "fim"
        self._tela(jogar=_visivel())
        self._tela(jogar=_sumiu())  # o Jogar sumiu: partida nova
        self.farm._passo_piloto()
        self.assertEqual(self.farm.piloto.fase, "onibus")

    def test_com_piloto_o_anti_afk_nao_pula(self):
        self._com_piloto()
        self.farm.em_partida = True
        self.farm.piloto.fase = "fim"  # fora do controle do piloto: o anti-AFK anda
        with mock.patch.object(automacao.random, "random", return_value=0.0):
            self._afk(self.farm.ajustes.afk_a_cada + 0.2 + self.farm.ajustes.afk_segurar + 0.2)
        self.assertTrue(self._apertadas())
        self.assertNotIn("espaco", self._apertadas())  # pular no ônibus é com o piloto

    def test_piloto_desligado_nos_ajustes_nao_mexe(self):
        self._com_piloto()
        self.farm.ajustes.piloto = False
        self.farm.em_partida = True
        with mock.patch.object(self.farm.parar, "wait"):
            self.farm._passo_piloto()
        self.assertEqual(self.farm.piloto.fase, "esperando")

    def test_grava_prints_so_na_partida(self):
        a = self.farm.ajustes
        a.gravar_partida = True
        for _ in range(3):
            self.sistema.tempo += a.gravar_a_cada
            self.farm._passo()
        self.assertEqual(self.sistema.gravados, [])  # no saguão não grava

        self.farm.em_partida = True
        self.farm._passo()
        self.assertEqual(self.sistema.gravados, [])  # o primeiro sai gravar_a_cada depois do início
        self.sistema.tempo += a.gravar_a_cada
        self.farm._passo()
        self.sistema.tempo += 1
        self.farm._passo()
        self.assertEqual(self.sistema.gravados, [self.sistema.tela])
        self.sistema.tempo += a.gravar_a_cada
        self.farm._passo()
        self.assertEqual(len(self.sistema.gravados), 2)

        a.gravar_partida = False
        self.sistema.tempo += a.gravar_a_cada
        self.farm._passo()
        self.assertEqual(len(self.sistema.gravados), 2)

    def test_gravacao_para_no_limite(self):
        self.farm.ajustes.gravar_partida = True
        self.farm.em_partida = True
        self.farm.gravados = automacao.GRAVAR_NO_MAXIMO - 1
        for _ in range(3):
            self.sistema.tempo += self.farm.ajustes.gravar_a_cada
            self.farm._passo()
        self.assertEqual(len(self.sistema.gravados), 1)
        self.assertEqual(sum("Gravação parada" in texto for _, texto in self.avisos), 1)


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

    def test_dois_atalhos_ao_mesmo_tempo(self):
        # como F8 e F9 na janela; F23 e F24 porque ninguém usa
        atalhos = [entrada.AtalhoGlobal(lambda: None, vk=vk) for vk in (0x86, 0x87)]
        try:
            self.assertEqual([a.iniciar() for a in atalhos], [None, None])
        finally:
            for a in atalhos:
                a.encerrar()
                a.join(2)
        self.assertFalse(any(a.is_alive() for a in atalhos))


class TestGravacaoF9(unittest.TestCase):
    """O F9 com um print falso: não olha a tela de verdade nem toca bipe."""

    class _App:
        def __init__(self):
            self.fila = queue.Queue()

    def _apertar_f9(self, tela):
        app, bipes = self._App(), []
        with tempfile.TemporaryDirectory() as pasta, \
                mock.patch.object(visao, "capturar_tela", lambda: tela), \
                mock.patch.object(farm.winsound, "MessageBeep", bipes.append), \
                mock.patch.object(farm, "PASTA_GRAVACAO", pasta):
            farm.App._gravar(app)
            _, (texto, tipo) = app.fila.get(timeout=5)  # o PNG é gravado em outra thread
            return texto, tipo, bipes, os.listdir(pasta)

    def test_salva_e_avisa(self):
        texto, tipo, bipes, arquivos = self._apertar_f9(_tela_falsa(320, 180))
        self.assertEqual(tipo, "ok")
        self.assertEqual(len(arquivos), 1)
        self.assertIn(arquivos[0], texto)
        self.assertEqual(bipes, [farm.winsound.MB_OK])

    def test_print_preto_nao_salva(self):
        texto, tipo, bipes, arquivos = self._apertar_f9(Image.new("RGB", (320, 180)))
        self.assertEqual((tipo, arquivos), ("erro", []))
        self.assertEqual(bipes, [farm.winsound.MB_ICONHAND])


class TestGravacaoSeguida(unittest.TestCase):
    """O F10 com tela e relógio falsos."""

    def setUp(self):
        self.sistema = SistemaFalso()
        self.avisos = []
        self.gravacao = automacao.GravacaoSeguida(lambda texto, tipo="info": self.avisos.append((tipo, texto)), self.sistema)

    def test_grava_so_com_o_jogo_na_frente(self):
        self.gravacao.passo()
        self.sistema.foco = False
        self.gravacao.passo()
        self.assertEqual(len(self.sistema.gravados), 1)  # nunca tira print de outra janela
        self.sistema.foco = True
        self.sistema.tela = Image.new("RGB", (320, 180))
        self.gravacao.passo()
        self.assertEqual(len(self.sistema.gravados), 1)  # print preto não serve

    def test_para_sozinho_no_limite(self):
        self.gravacao.gravados = automacao.SEGUIDO_NO_MAXIMO - 1
        for _ in range(3):
            self.gravacao.passo()
        self.assertEqual(len(self.sistema.gravados), 1)
        self.assertTrue(self.gravacao.parar.is_set())

    def test_liga_e_desliga(self):
        with mock.patch.object(automacao, "SEGUIDO_A_CADA", 0.05):
            self.assertTrue(self.gravacao.alternar())
            time.sleep(0.3)
            self.assertFalse(self.gravacao.alternar())
            self.gravacao._thread.join(2)
        self.assertFalse(self.gravacao._thread.is_alive())
        self.assertGreater(len(self.sistema.gravados), 1)
        self.assertIn("gravação parada", self.avisos[-1][1])
        # liga de novo depois de parar
        self.assertTrue(self.gravacao.alternar())
        self.gravacao.alternar()
        self.gravacao._thread.join(2)


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
