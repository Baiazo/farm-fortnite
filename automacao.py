"""Laço do farm: lê a tela, clica no botão que aparecer e mexe o personagem durante a partida."""
import os
import random
import threading
import time

import entrada
import visao
from config import BOTOES, PASTA_PRINTS

# Botões que só aparecem depois que a partida acabou
FIM_DE_PARTIDA = {"voltar", "pular", "continuar"}
# Prints pretos seguidos (uns 10 s) antes de avisar: telas de carregamento piscam preto
PRETAS_PARA_AVISAR = 5
# Segundos sem reconhecer botão nenhum até salvar um print da tela. Na partida é normal
# passar muito tempo sem botão, então o limite é maior.
TRAVADO_FORA = 10 * 60
TRAVADO_NA_PARTIDA = 35 * 60


class Sistema:
    """O que o farm faz fora dele: relógio, print, janela em foco, mouse e teclado.

    Os testes trocam por um falso, então nunca mexem no mouse nem apertam tecla de verdade.
    """

    agora = staticmethod(time.monotonic)
    capturar_tela = staticmethod(visao.capturar_tela)
    jogo_em_foco = staticmethod(entrada.jogo_em_foco)
    clicar = staticmethod(entrada.clicar)
    apertar = staticmethod(entrada.apertar)
    soltar = staticmethod(entrada.soltar)
    soltar_tudo = staticmethod(entrada.soltar_tudo)

    @staticmethod
    def salvar_print(img):
        return visao.salvar_print(img, PASTA_PRINTS)


class Automacao:
    def __init__(self, ajustes, modelos, avisar, sistema=None):
        self.ajustes = ajustes
        self.modelos = modelos  # chave do botão -> visao.Modelo
        self.avisar = avisar    # avisar(texto, tipo) manda para o registro (chamado de outra thread)
        self.sistema = sistema or Sistema()
        self.parar = threading.Event()
        self.em_partida = False
        self.situacao = "procurando"  # "procurando", "pausado" (jogo fora de foco) ou "preto"
        self.partidas = 0
        self.cliques = 0
        self.inicio = self.sistema.agora()
        self._ultimo_clique = float("-inf")
        self._clicado = None    # último botão clicado, esperando sumir da tela
        self._tentativas = 0    # prints seguidos em que ele continuou lá
        self._pretas = 0
        self._visto_em = self.inicio  # última vez que algum botão apareceu
        self._tecla = None      # tecla que o anti-AFK está segurando
        self._soltar_em = 0.0
        self._proximo_afk = 0.0
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
        self.sistema.soltar_tudo()

    def _foco_ok(self):
        return not self.ajustes.so_com_jogo_em_foco or self.sistema.jogo_em_foco()

    # ---------- leitura da tela e cliques ----------

    def _laco(self):
        while not self.parar.is_set():
            inicio = time.monotonic()
            try:
                self._passo()
            except Exception as e:  # um ciclo com erro não derruba o farm
                self.avisar(f"Erro: {e}", "erro")
            self.parar.wait(max(0.2, self.ajustes.intervalo - (time.monotonic() - inicio)))

    def _passo(self):
        agora = self.sistema.agora()
        if agora - self._ultimo_clique < self.ajustes.pausa_cliques:
            return  # dá tempo da tela trocar depois do último clique
        if not self._foco_ok():
            if self.situacao != "pausado":
                self.avisar("Pausado: o Fortnite não está em primeiro plano.", "aviso")
                self.situacao = "pausado"
            self._visto_em = agora  # tempo pausado não conta como travado
            return
        if self.situacao == "pausado":
            self.avisar("Fortnite em primeiro plano de novo. Continuando.")
            self.situacao = "procurando"

        img = self.sistema.capturar_tela()
        if visao.tela_preta(img):
            self._pretas += 1
            if self._pretas >= PRETAS_PARA_AVISAR:
                if self.situacao != "preto":
                    self.avisar('O print está saindo preto. No Fortnite, use "Tela cheia em janela".', "aviso")
                self.situacao = "preto"
            return
        self._pretas = 0
        self.situacao = "procurando"

        quadro = visao.Quadro(img)
        self.processar({chave: visao.procurar(quadro, m) for chave, m in self.modelos.items()}, img)

    def processar(self, notas, img=None):
        """Age sobre as notas da tela atual ({chave: (nota, x, y)}): confere se o último clique
        pegou, atualiza se está na partida e clica no botão visível de maior prioridade."""
        agora = self.sistema.agora()
        vistos = {chave for chave, (nota, _, _) in notas.items() if nota >= self.ajustes.limiar}
        if not self._conferir_clique(vistos):
            return
        if "jogar" in vistos or vistos & FIM_DE_PARTIDA:
            self.em_partida = False

        if not vistos:
            limite = TRAVADO_NA_PARTIDA if self.em_partida else TRAVADO_FORA
            if agora - self._visto_em >= limite:
                self._visto_em = agora
                self._avisar_travado(img, limite)
            return
        self._visto_em = agora

        botao = next(b for b in BOTOES if b.chave in vistos)  # BOTOES já está em ordem de prioridade
        if self.parar.is_set() or not self._foco_ok():
            return
        if botao != self._clicado:
            self._clicado, self._tentativas = botao, 0
        nota, x, y = notas[botao.chave]
        self.sistema.clicar(x, y)
        self._ultimo_clique = self.sistema.agora()
        self.cliques += 1
        self.avisar(f"Cliquei em {botao.nome} (nota {_nota(nota)})", "ok")

    def _conferir_clique(self, vistos):
        """Vê se o botão clicado por último sumiu da tela. Devolve False quando é para desistir."""
        botao = self._clicado
        if botao is None:
            return True
        if botao.chave not in vistos:
            self._clicado, self._tentativas = None, 0
            if botao.chave == "jogar":
                self.partidas += 1
                self.em_partida = True
                self.avisar(f"Partida {self.partidas} iniciada.", "partida")
            return True
        self._tentativas += 1
        if self._tentativas < botao.max_cliques:
            return True
        self.avisar(
            f"Cliquei {botao.max_cliques} vezes em {botao.nome} e ele continuou na tela, então parei. "
            "Se o jogo não responde aos cliques, abra o farm como administrador.",
            "erro",
        )
        self.parar.set()
        return False

    def _avisar_travado(self, img, limite):
        try:
            caminho = self.sistema.salvar_print(img)
        except OSError as e:
            self.avisar(f"Nenhum botão reconhecido há {limite // 60} min e não consegui salvar o print: {e}", "erro")
            return
        self.avisar(
            f"Nenhum botão reconhecido há {limite // 60} min. Print salvo em prints\\{os.path.basename(caminho)}: "
            "veja se falta capturar algum botão.",
            "aviso",
        )

    # ---------- anti-AFK ----------

    def _anti_afk(self):
        try:
            while not self.parar.wait(0.1):
                try:
                    self._passo_afk()
                except OSError as e:
                    self.avisar(f"Anti-AFK falhou: {e}", "erro")
        finally:
            try:
                self._largar_tecla()
            except OSError:
                pass  # o encerrar() ainda solta todas as teclas

    def _passo_afk(self):
        """Segura uma tecla W/A/S/D de tempos em tempos, só na partida e com o jogo em foco."""
        agora = self.sistema.agora()
        ativo = self.ajustes.anti_afk and self.em_partida and not self.parar.is_set() and self._foco_ok()
        if self._tecla:
            if not ativo or agora >= self._soltar_em:
                self._largar_tecla()
                self._proximo_afk = agora + self.ajustes.afk_a_cada
            return
        if not ativo:
            self._proximo_afk = agora + self.ajustes.afk_a_cada  # conta a partir do início da partida
            return
        if agora >= self._proximo_afk:
            self._proximo_afk = agora + self.ajustes.afk_a_cada  # se apertar falhar, só tenta na próxima vez
            tecla = random.choice("wasd")
            self.sistema.apertar(tecla)
            self._tecla = tecla
            self._soltar_em = agora + self.ajustes.afk_segurar

    def _largar_tecla(self):
        tecla, self._tecla = self._tecla, None
        if tecla:
            self.sistema.soltar(tecla)


def _nota(nota):
    return f"{nota:.2f}".replace(".", ",")
