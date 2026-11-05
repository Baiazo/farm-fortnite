"""Laço do farm: lê a tela, clica no botão que aparecer e mexe o personagem durante a partida."""
import os
import random
import threading
import time

import entrada
import visao
from config import BOTOES, PASTA_GRAVACAO, PASTA_PRINTS

# Botões que só aparecem depois que a partida acabou
FIM_DE_PARTIDA = {"voltar", "pular", "continuar"}
# Prints pretos seguidos (uns 10 s) antes de avisar: telas de carregamento piscam preto
PRETAS_PARA_AVISAR = 5
# Segundos sem reconhecer botão nenhum até salvar um print da tela. Na partida é normal
# passar muito tempo sem botão, então o limite é maior.
TRAVADO_FORA = 10 * 60
TRAVADO_NA_PARTIDA = 35 * 60
# Gravação automática: prints por vez que o farm é iniciado (cada um tem uns 3 MB em 1080p)
GRAVAR_NO_MAXIMO = 200
# F10: um print por segundo enquanto você joga; para sozinho depois de uns 5 min
SEGUIDO_A_CADA = 1.0
SEGUIDO_NO_MAXIMO = 300

# Anti-AFK. Para a frente aparece mais vezes porque é o que um jogador mais faz.
DIRECOES = (("w",), ("w",), ("w", "a"), ("w", "d"), ("a",), ("d",), ("s",))
VARIACAO = (0.6, 1.4)  # tempos sorteados em volta do ajuste, para não repetir um ritmo fixo
CHANCE_PULO = 0.35
CHANCE_VIRAR = 0.5
# Quanto a câmera vira, em unidades do mouse (quantos graus dá depende da sensibilidade do jogo).
# A virada é dividida em passos de 0,1 s para não ser um tranco.
VIRAR = (300, 1500)
PASSOS_VIRAR = 6


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
    virar = staticmethod(entrada.virar)

    @staticmethod
    def salvar_print(img):
        return visao.salvar_print(img, PASTA_PRINTS)

    @staticmethod
    def salvar_gravacao(img):
        return visao.salvar_gravacao(img, PASTA_GRAVACAO, "auto")

    @staticmethod
    def salvar_seguido(img):
        return visao.salvar_gravacao(img, PASTA_GRAVACAO, "seguido")


class GravacaoSeguida:
    """F10: um print por segundo em gravacao/ enquanto você joga, até apertar de novo ou chegar
    ao limite. Não aperta nada e não lê teclado; só grava com o Fortnite em primeiro plano, então
    nunca tira print de outra janela."""

    def __init__(self, avisar, sistema=None):
        self.avisar = avisar  # chamado de outra thread
        self.sistema = sistema or Sistema()
        self.parar = threading.Event()
        self.gravados = 0
        self._thread = None

    @property
    def rodando(self):
        return self._thread is not None and self._thread.is_alive() and not self.parar.is_set()

    def alternar(self):
        """Liga ou desliga. Devolve True quando ligou."""
        if self.rodando:
            self.parar.set()
            return False
        self.parar = threading.Event()  # um evento novo: a thread antiga, se ainda não saiu, continua parada
        self.gravados = 0
        self._thread = threading.Thread(target=self._laco, args=(self.parar,), daemon=True)
        self._thread.start()
        return True

    def _laco(self, parar):
        while not parar.is_set():
            inicio = time.monotonic()
            try:
                self.passo()
            except OSError as e:
                self.avisar(f"F10: não consegui salvar o print ({e}).", "erro")
            parar.wait(max(0.1, SEGUIDO_A_CADA - (time.monotonic() - inicio)))
        self.avisar(f"F10: gravação parada, {self.gravados} prints em gravacao (seguido-...png).", "ok")

    def passo(self):
        if self.gravados >= SEGUIDO_NO_MAXIMO:
            self.parar.set()
            return
        if not self.sistema.jogo_em_foco():
            return
        img = self.sistema.capturar_tela()
        if visao.tela_preta(img):
            return
        self.sistema.salvar_seguido(img)
        self.gravados += 1


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
        self.gravados = 0       # prints da gravação automática nesta vez
        self._proxima_gravacao = 0.0
        self._presas = []       # teclas que o anti-AFK está segurando
        self._mexendo_ate = None  # fim do movimento atual do anti-AFK
        self._pulo_em = None    # quando pular no meio do movimento
        self._virar = 0         # quanto ainda falta virar a câmera
        self._passo_virar = 0
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
        self._gravar_partida(img)

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

    def _gravar_partida(self, img):
        """Com a opção ligada, guarda um print da partida de tempos em tempos em gravacao/:
        o mesmo material do F9, sem precisar apertar nada."""
        agora = self.sistema.agora()
        if not (self.ajustes.gravar_partida and self.em_partida):
            self._proxima_gravacao = agora + self.ajustes.gravar_a_cada  # conta a partir do início da partida
            return
        if agora < self._proxima_gravacao or self.gravados >= GRAVAR_NO_MAXIMO:
            return
        self._proxima_gravacao = agora + self.ajustes.gravar_a_cada
        try:
            self.sistema.salvar_gravacao(img)
        except OSError as e:
            self.avisar(f"Não consegui salvar o print da partida: {e}", "erro")
            return
        self.gravados += 1
        if self.gravados == GRAVAR_NO_MAXIMO:
            self.avisar(
                f"Gravação parada: {GRAVAR_NO_MAXIMO} prints desta vez já estão em gravacao. "
                "Para gravar mais, pare e inicie o farm de novo.",
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
                self._parar_movimento()
            except OSError:
                pass  # o encerrar() ainda solta todas as teclas

    def _passo_afk(self):
        """Mexe o personagem de tempos em tempos, só na partida e com o jogo em foco: anda numa
        direção sorteada e, com a opção ligada, às vezes pula ou vira a câmera no caminho."""
        agora = self.sistema.agora()
        ativo = self.ajustes.anti_afk and self.em_partida and not self.parar.is_set() and self._foco_ok()
        if self._mexendo_ate is not None:
            if not ativo or agora >= self._mexendo_ate:
                self._proximo_afk = agora + _sortear(self.ajustes.afk_a_cada)
                self._parar_movimento()
            else:
                self._no_caminho(agora)
            return
        if not ativo:
            self._proximo_afk = agora + _sortear(self.ajustes.afk_a_cada)  # conta a partir do início da partida
            return
        if agora >= self._proximo_afk:
            self._comecar_movimento(agora)

    def _comecar_movimento(self, agora):
        duracao = _sortear(self.ajustes.afk_segurar)
        self._mexendo_ate = agora + duracao  # marcado antes de apertar: se falhar, só perde esta vez
        if self.ajustes.afk_variado:
            if random.random() < CHANCE_PULO:
                self._pulo_em = agora + random.uniform(0, duracao * 0.7)
            if random.random() < CHANCE_VIRAR:
                self._virar = random.choice((-1, 1)) * random.randint(*VIRAR)
                self._passo_virar = -(-abs(self._virar) // PASSOS_VIRAR)  # divide arredondando para cima
        for tecla in random.choice(DIRECOES):
            self.sistema.apertar(tecla)
            self._presas.append(tecla)

    def _no_caminho(self, agora):
        """Pulo e virada de câmera no meio de um movimento (o _passo_afk roda a cada 0,1 s)."""
        if self._virar:
            passo = max(-self._passo_virar, min(self._passo_virar, self._virar))
            self._virar -= passo
            try:
                self.sistema.virar(passo)
            except OSError:
                self._virar = 0  # um erro por movimento basta no registro
                raise
        if self._pulo_em is not None and agora >= self._pulo_em:
            self._pulo_em = None
            self.sistema.apertar("espaco")
            self._presas.append("espaco")
        elif "espaco" in self._presas:
            self._presas.remove("espaco")  # um toque: solta no passo seguinte, 0,1 s depois
            self.sistema.soltar("espaco")

    def _parar_movimento(self):
        """Solta tudo o que o anti-AFK segura; tenta todas as teclas mesmo se uma falhar."""
        self._mexendo_ate, self._pulo_em, self._virar = None, None, 0
        presas, self._presas = self._presas, []
        erro = None
        for tecla in presas:
            try:
                self.sistema.soltar(tecla)
            except OSError as e:
                erro = e
        if erro:
            raise erro


def _sortear(base):
    return base * random.uniform(*VARIACAO)


def _nota(nota):
    return f"{nota:.2f}".replace(".", ",")
