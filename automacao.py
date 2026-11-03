"""Laço do farm: lê a tela, clica no botão que aparecer e mexe o personagem durante a partida."""
import random
import threading
import time

import entrada
import visao
from config import BOTOES

# Botões que só aparecem depois que a partida acabou
FIM_DE_PARTIDA = {"voltar", "pular", "continuar"}


class Automacao:
    def __init__(self, ajustes, modelos, avisar):
        self.ajustes = ajustes
        self.modelos = modelos  # chave do botão -> visao.Modelo
        self.avisar = avisar    # manda texto para o registro (chamado de outra thread)
        self.parar = threading.Event()
        self.em_partida = False
        self.partidas = 0
        self._ultimo_clique = 0.0
        self._threads = []

    @property
    def rodando(self):
        return not self.parar.is_set() and any(t.is_alive() for t in self._threads)

    def iniciar(self):
        for alvo in (self._laco, self._anti_afk):
            t = threading.Thread(target=alvo, daemon=True)
            t.start()
            self._threads.append(t)

    def encerrar(self):
        self.parar.set()
        for t in self._threads:
            t.join(timeout=3)
        entrada.soltar_tudo()

    def _laco(self):
        while not self.parar.is_set():
            inicio = time.monotonic()
            try:
                self._passo()
            except Exception as e:  # um ciclo com erro não derruba o farm
                self.avisar(f"Erro: {e}")
            self.parar.wait(max(0.2, self.ajustes.intervalo - (time.monotonic() - inicio)))

    def _passo(self):
        if time.monotonic() - self._ultimo_clique < self.ajustes.pausa_cliques:
            return  # dá tempo da tela trocar depois do último clique
        quadro = visao.Quadro(visao.capturar_tela())
        for botao in BOTOES:  # já está em ordem de prioridade
            modelo = self.modelos.get(botao.chave)
            if modelo is None:
                continue
            nota, x, y = visao.procurar(quadro, modelo)
            if nota < self.ajustes.limiar or self.parar.is_set():
                continue
            entrada.clicar(x, y)
            self._ultimo_clique = time.monotonic()
            if botao.chave == "jogar":
                self.em_partida = True
                self.partidas += 1
            elif botao.chave in FIM_DE_PARTIDA:
                self.em_partida = False
            self.avisar(f"Cliquei em {botao.nome} (nota {nota:.2f})")
            return

    def _anti_afk(self):
        proximo = time.monotonic() + self.ajustes.afk_a_cada
        while not self.parar.wait(0.25):
            agora = time.monotonic()
            if not (self.ajustes.anti_afk and self.em_partida):
                proximo = agora + self.ajustes.afk_a_cada  # conta a partir do início da partida
                continue
            if agora < proximo:
                continue
            try:
                self._segurar(random.choice("wasd"))
            except OSError as e:
                self.avisar(f"Anti-AFK falhou: {e}")
            proximo = time.monotonic() + self.ajustes.afk_a_cada

    def _segurar(self, tecla):
        """Segura a tecla; solta antes se o farm parar ou a partida acabar."""
        entrada.apertar(tecla)
        try:
            fim = time.monotonic() + self.ajustes.afk_segurar
            while time.monotonic() < fim and self.em_partida and not self.parar.wait(0.1):
                pass
        finally:
            entrada.soltar(tecla)
