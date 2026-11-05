"""Testes do piloto com leituras de mentira: nada mexe no mouse nem aperta tecla de verdade."""
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import piloto  # noqa: E402
from config import Ajustes  # noqa: E402
from leitura import IconeBau, Marcador  # noqa: E402

TELA = SimpleNamespace(size=(1920, 1080))


class SinaisFalsos:
    """O que o leitor "viu" no print atual; o teste muda antes de cada passo."""

    def __init__(self, tem_lugar=False):
        self.m = None
        self.icones = []
        self.avisos = set()  # "pular", "vasculhar", "mapa" (o mapa está aberto)
        self.tem_lugar = tem_lugar
        self.lugar = {"nome": "Enseada do Saque", "x": 258, "y": 143}
        self.alvo = (1158, 475)  # onde a ilha diz que fica o lugar (None: não achou a ilha)
        self.pino = True          # o marcador apareceu no mapa depois do clique

    def lugar_no_mapa(self, img):
        return self.alvo

    def marcador_no_mapa(self, img, x, y):
        return self.pino

    def marcador(self, img):
        return self.m

    def baus(self, img):
        return self.icones

    def aviso(self, img, nome):
        return nome in self.avisos


class SistemaFalso:
    def __init__(self):
        self.tempo = 100.0
        self.feito = []  # ("apertar"/"soltar", tecla) e ("virar", dx)

    def agora(self):
        return self.tempo

    def apertar(self, tecla):
        self.feito.append(("apertar", tecla))

    def soltar(self, tecla):
        self.feito.append(("soltar", tecla))

    def virar(self, dx, dy=0):
        self.feito.append(("virar", dx))

    def clicar(self, x, y):
        self.feito.append(("clicar", (x, y)))


class TestMarcarNoMapa(unittest.TestCase):
    def setUp(self):
        self.sinais, self.sistema, self.avisos = SinaisFalsos(tem_lugar=True), SistemaFalso(), []
        self.p = piloto.Piloto(self.sinais, self.sistema, lambda t, tipo="info": self.avisos.append(t),
                               Ajustes(tecla_interagir="x"))

    def _passo(self, segundos=1.0, mapa=None):
        if mapa is not None:
            self.sinais.avisos = {"mapa"} if mapa else set()
        self.sistema.tempo += segundos
        self.sistema.feito = []
        self.p.passo(TELA)
        return self.sistema.feito

    def _cliques(self, feito):
        return [lugar for acao, lugar in feito if acao == "clicar"]

    def test_abre_redefine_clica_confere_e_fecha(self):
        self.assertEqual(self.p.fase, "marcando")
        self.assertTrue(self.p.no_controle)  # o anti-AFK fica parado enquanto mexe no mapa
        self.assertEqual(self._passo(mapa=False), [("apertar", "m")])
        self.assertEqual(self._passo(mapa=True), [("soltar", "m"), ("apertar", "shift")])  # REDEFINIR
        feito = self._passo()
        self.assertEqual(self._cliques(feito), [(1158, 475)])
        feito = self._passo()
        self.assertIn(("apertar", "m"), feito)  # fecha o mapa
        self.assertIn("Enseada do Saque", self.avisos[-1])
        self._passo(mapa=False)
        self.assertEqual(self.p.fase, "esperando")

    def test_partida_carregando_tenta_abrir_de_novo(self):
        apertos = 0
        for _ in range(10):
            apertos += self._passo(mapa=False).count(("apertar", "m"))
        self.assertGreaterEqual(apertos, 3)  # a cada TENTAR_MAPA s
        self.assertEqual(self._cliques(self.sistema.feito), [])

    def test_nunca_clica_com_o_mapa_fechado(self):
        cliques = []
        for _ in range(piloto.TEMPO_MARCANDO + 2):
            cliques += self._cliques(self._passo(mapa=False))
        self.assertEqual(cliques, [])
        self.assertEqual(self.p.fase, "esperando")
        self.assertIn("à mão", self.avisos[-1])

    def test_sem_ilha_tenta_tres_vezes_e_desiste(self):
        self.sinais.alvo = None
        self._passo(mapa=False)
        self._passo(mapa=True)
        for _ in range(piloto.TENTATIVAS_MAPA):
            feito = self._passo()
        self.assertIn(("apertar", "m"), feito)
        self.assertIn("ponha o marcador à mão", self.avisos[-1])
        self._passo(mapa=False)
        self.assertEqual(self.p.fase, "esperando")

    def test_marcador_nao_apareceu_clica_de_novo_ao_lado(self):
        self.sinais.pino = False
        self._passo(mapa=False)
        self._passo(mapa=True)
        primeiro = self._cliques(self._passo())
        self._passo()  # conferiu: sem pino; aperta REDEFINIR de novo
        segundo = self._cliques(self._passo())
        self.assertNotEqual(primeiro, segundo)  # ao lado, para não tirar o marcador

    def test_sem_lugar_escolhido_comeca_esperando(self):
        p = piloto.Piloto(SinaisFalsos(), self.sistema, lambda t, tipo="info": None, Ajustes())
        self.assertEqual(p.fase, "esperando")


class TestPiloto(unittest.TestCase):
    def setUp(self):
        self.sinais, self.sistema, self.avisos = SinaisFalsos(), SistemaFalso(), []
        self.p = piloto.Piloto(self.sinais, self.sistema, lambda t, tipo="info": self.avisos.append(t),
                               Ajustes(baus_por_partida=2, tecla_interagir="x"))

    def _passo(self, segundos=1.0, distancia=None, x=960, y=540, borda=False):
        if distancia is not None:
            self.sinais.m = Marcador(x, y, distancia, borda)
        self.sistema.tempo += segundos
        self.sistema.feito = []
        self.p.passo(TELA)
        return self.sistema.feito

    def _virou(self, feito):
        return sum(dx for acao, dx in feito if acao == "virar")

    def _no_onibus(self):
        self.sinais.avisos = {"pular"}
        self._passo()
        self.assertEqual(self.p.fase, "onibus")

    def test_espera_o_onibus_sem_mexer(self):
        for _ in range(5):
            self.assertEqual(self._passo(), [])
        self.assertEqual(self.p.fase, "esperando")
        self.assertFalse(self.p.no_controle)

    def test_pula_quando_o_onibus_passa_do_ponto_mais_perto(self):
        self._no_onibus()
        for d in (1200, 1150, 1100, 1060, 1050, 1058):
            self.assertEqual(self._passo(distancia=d), [])
        feito = self._passo(distancia=1066)  # 16 m acima do menor: passou
        self.assertEqual(feito, [("apertar", "espaco")])
        self.assertEqual(self.p.fase, "queda")
        self.assertIn(("soltar", "espaco"), self._passo(distancia=1040))  # um toque

    def test_pula_logo_quando_ja_esta_perto(self):
        self._no_onibus()
        self._passo(distancia=640)
        self.assertEqual(self.p.fase, "onibus")  # primeira leitura: ainda não confirmada
        self.assertIn(("apertar", "espaco"), self._passo(distancia=630))
        self.assertEqual(self.p.fase, "queda")

    def test_leitura_errada_no_onibus_nao_faz_pular(self):
        self._no_onibus()
        for d in (1300, 1280, 1260):
            self._passo(distancia=d)
        self.assertEqual(self._passo(distancia=126), [])  # "126" no lugar de "1260": ignora
        self.assertEqual(self.p.fase, "onibus")

    def test_sem_marcador_no_onibus_desiste(self):
        self._no_onibus()
        for _ in range(16):
            self._passo()
        self.assertEqual(self.p.fase, "fim")
        self.assertIn("marcador", self.avisos[-1])

    def test_saiu_do_onibus_sem_pular(self):
        self._no_onibus()
        self.sinais.avisos = set()
        for _ in range(3):
            self._passo(distancia=900)
        self.assertEqual(self.p.fase, "queda")

    def _caindo(self):
        self._no_onibus()
        self._passo(distancia=600)
        self._passo(distancia=590)
        self.sinais.avisos = set()
        self.assertEqual(self.p.fase, "queda")

    def test_na_queda_vira_para_o_pino_e_segura_w(self):
        self._caindo()
        feito = self._passo(distancia=560, x=1260)
        self.assertGreater(self._virou(feito), 0)
        self.assertIn(("apertar", "w"), feito)
        self.assertLess(self._virou(self._passo(distancia=530, x=660)), 0)
        self.assertEqual(self._virou(self._passo(distancia=500, x=47, y=600, borda=True)), -piloto.VIRAR_MAX)
        self.assertEqual(self._virou(self._passo(distancia=470, x=961)), 0)  # no meio: não mexe

    def test_chega_no_marcador_e_procura_baus(self):
        self._caindo()
        for d in (400, 250, 120, 40):
            self._passo(distancia=d)
        feito = self._passo(distancia=20)
        self.assertEqual(self.p.fase, "baus")
        self.assertIn(("soltar", "w"), feito)

    def test_caiu_longe_vai_a_pe(self):
        self._caindo()
        # 590 -> 300 de uma vez é salto de leitura: só vale na terceira; depois, 5 s parada
        for _ in range(3 + piloto.PARADO_NA_QUEDA):
            self._passo(distancia=300)
        self.assertEqual(self.p.fase, "a_pe")

    def _nos_baus(self):
        self._caindo()
        for d in (400, 250, 120, 40, 20):
            self._passo(distancia=d)
        self.assertEqual(self.p.fase, "baus")

    def test_vira_para_o_bau_e_so_anda_com_ele_na_frente(self):
        self._nos_baus()
        self.sinais.icones = [IconeBau(60, 261, 0.9)]
        feito = self._passo()
        self.assertEqual(self._virou(feito), piloto.VIRAR_MAX)
        self.assertNotIn(("apertar", "w"), feito)
        self.sinais.icones = [IconeBau(-120, 261, 0.9), IconeBau(10, 261, 0.8)]  # vai no mais à frente
        feito = self._passo()
        self.assertEqual(self._virou(feito), 100)
        self.assertIn(("apertar", "w"), feito)

    def test_vasculha_segurando_a_tecla_e_para_na_meta(self):
        self._nos_baus()
        for numero in (1, 2):
            self.sinais.avisos = {"vasculhar"}
            self.assertIn(("apertar", "x"), self._passo())
            self.assertEqual(self._passo(0.5), [])  # segurando
            self.sinais.avisos = set()
            self.assertIn(("soltar", "x"), self._passo(1.0))
            self.assertEqual(self.p.abertos, numero)
            self._passo(piloto.PAUSA_DEPOIS_DO_BAU)
        self.assertEqual(self.p.fase, "fim")
        self.assertFalse(self.p.no_controle)

    def test_sem_bau_por_perto_desiste(self):
        self._nos_baus()
        for _ in range(piloto.SEM_BAU + 1):
            self._passo()
        self.assertEqual(self.p.fase, "fim")
        self.assertIn("não achei", self.avisos[-1])

    def test_largar_solta_tudo_e_reiniciar_volta_a_esperar(self):
        self._caindo()
        self._passo(distancia=560)
        self.sistema.feito = []
        self.p.largar()
        self.assertIn(("soltar", "w"), self.sistema.feito)
        self.p.reiniciar()
        self.assertEqual(self.p.fase, "esperando")


if __name__ == "__main__":
    unittest.main()
