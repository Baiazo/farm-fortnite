"""Piloto da partida: do ônibus até os baús, guiado pelo marcador que já está no mapa.

Fases, uma depois da outra em cada partida:
- marcando: com um lugar escolhido (sinais/lugar.json), abre o mapa, aperta REDEFINIR para ver a
  ilha inteira, clica no lugar, confere o pino e fecha. Só clica com o mapa aberto no mesmo print.
- esperando: na ilha de espera. Sai quando aparece "Espaço PARA PULAR" (portas do ônibus abertas).
- onibus: lê a distância até o marcador e pula quando ela parar de cair (o ônibus passou do ponto
  mais perto) ou quando já está perto.
- queda: segura W e vira a câmera até o pino ficar no meio da tela. O planador abre sozinho.
- a_pe: caiu longe do marcador; anda até ele do mesmo jeito.
- baus: segue o ícone de baú do anel em volta da mira e segura a tecla de interagir no
  "VASCULHAR", até abrir a quantidade de baús pedida ou o tempo acabar.
- fim: solta tudo e devolve a partida para o anti-AFK.

Só mexe com teclado e mouse pelo `sistema`, como a automação; os testes trocam por um falso.
Nunca aperta o botão de atirar nem mira em ninguém.
"""
from dataclasses import replace

SALTAR_PERTO = 650      # m: com o marcador a essa distância já dá para pular e planar até lá
SUBIU = 15              # m acima da menor distância vista no ônibus: passou do ponto mais perto
CHEGOU = 25             # m do marcador: chegou, agora é procurar baú
VELOCIDADE_MAX = 60     # m/s: leitura que muda mais que isso é erro de leitura (um "1" a mais)
GANHO_X = 0.8           # unidades de mouse por pixel do pino fora do meio da tela
GANHO_ANGULO = 10       # unidades de mouse por grau do ícone de baú fora da frente
VIRAR_MAX = 300         # por passo, para a câmera não dar tranco
VIRAR_PROCURANDO = 150  # sem pino ou sem baú à vista: vai girando devagar
FRENTE = 35             # graus: com o baú dentro disso, anda para ele; fora, só vira
SEGURAR_INTERAGIR = 1.2  # s segurando a tecla no "VASCULHAR"
PAUSA_DEPOIS_DO_BAU = 2.0
SEM_MARCADOR_NO_ONIBUS = 15  # s sem ver o marcador no ônibus: não tem marcador no mapa
PARADO_NA_QUEDA = 5     # s sem a distância cair: já está no chão, longe do marcador
TEMPO_A_PE = 90
TEMPO_DE_BAUS = 120
SEM_BAU = 30            # s sem nenhum ícone de baú: acabaram os baús por perto
TENTAR_MAPA = 3.0       # s entre um M e outro enquanto a partida carrega
ESPERA_MAPA = 0.7       # s para o mapa reagir ao REDEFINIR e ao clique
TENTATIVAS_MAPA = 3
TEMPO_MARCANDO = 150    # s tentando abrir o mapa; depois disso o marcador fica com o jogador
NO_CONTROLE = ("marcando", "onibus", "queda", "a_pe", "baus")


class Piloto:
    def __init__(self, sinais, sistema, avisar, ajustes):
        self.sinais = sinais    # leitura.Sinais (ou um falso nos testes)
        self.sistema = sistema
        self.avisar = avisar
        self.ajustes = ajustes  # usa baus_por_partida e tecla_interagir
        self._presas = set()
        self._tocar = []        # teclas apertadas para soltar no passo seguinte (um toque)
        self.reiniciar()

    @property
    def no_controle(self):
        """O piloto está mexendo no personagem (o anti-AFK tem que ficar parado)."""
        return self.fase in NO_CONTROLE

    @property
    def distancia(self):
        """Última distância confirmada até o marcador, em metros (None se ainda não leu)."""
        return self._dist

    def reiniciar(self):
        """Nova partida: põe o marcador (se tem lugar escolhido) e espera o ônibus."""
        self.largar()
        self.fase = "marcando" if getattr(self.sinais, "tem_lugar", False) else "esperando"
        self._mapa = None           # etapa no mapa: None, "abrindo", "redefinido", "clicado", "fechando"
        self._mapa_ate = 0.0
        self._tentativas_mapa = 0
        self._alvo = None
        self.abertos = 0
        self._desde = None          # quando entrou na fase atual
        self._menor = None          # menor distância vista no ônibus
        self._sem_pular = 0
        self._dist = None           # última distância aceita e quando
        self._dist_t = 0.0
        self._candidata = None      # primeira leitura, esperando outra que concorde
        self._rejeitados = 0
        self._visto = None          # última vez que viu o marcador
        self._progresso = (None, 0.0)  # (distância, quando) da última vez que ela caiu
        self._visto_bau = 0.0
        self._segurando_ate = None
        self._pausa_ate = 0.0

    def largar(self):
        """Solta todas as teclas (jogo fora de foco, farm parado); a fase continua."""
        for tecla in list(self._presas) + self._tocar:
            try:
                self.sistema.soltar(tecla)
            except OSError:
                pass  # o encerrar() da automação ainda solta todas as teclas
        self._presas.clear()
        self._tocar = []

    def passo(self, img):
        """Uma leitura da tela e o que fazer com ela."""
        if self.fase == "fim":
            return
        agora = self.sistema.agora()
        for tecla in self._tocar:
            self.sistema.soltar(tecla)
        self._tocar = []
        if self._desde is None:
            self._desde = agora
        getattr(self, f"_{self.fase}")(img, agora)

    # ---------- fases ----------

    def _marcando(self, img, agora):
        if agora - self._desde >= TEMPO_MARCANDO and self._mapa != "fechando":
            self._mudar("esperando", agora)
            self.avisar("Piloto: não consegui abrir o mapa; ponha o marcador à mão.", "aviso")
            return
        aberto = self.sinais.aviso(img, "mapa")
        if not aberto:
            if self._mapa == "fechando":
                self._mudar("esperando", agora)
            elif agora >= self._mapa_ate:
                # a partida ainda pode estar carregando, e aí o M não faz nada: tenta de novo daqui a pouco
                self._tocar_tecla("m")
                self._mapa, self._mapa_ate = "abrindo", agora + TENTAR_MAPA
            return
        if self._mapa in (None, "abrindo"):
            self._tocar_tecla("shift")  # REDEFINIR: zoom do começo, com a ilha inteira à vista
            self._mapa, self._mapa_ate = "redefinido", agora + ESPERA_MAPA
        elif agora < self._mapa_ate:
            return
        elif self._mapa == "redefinido":
            alvo = self.sinais.lugar_no_mapa(img)
            if alvo is None:
                self._falhou_no_mapa(agora, "não achei a ilha no mapa")
                return
            # na outra tentativa clica um pouco ao lado: clicar em cima do marcador tira ele
            self._alvo = (alvo[0], alvo[1] + 12 * self._tentativas_mapa)
            self.sistema.clicar(*self._alvo)  # o mapa está aberto neste mesmo print
            self._mapa, self._mapa_ate = "clicado", agora + ESPERA_MAPA
        elif self._mapa == "clicado":
            if self.sinais.marcador_no_mapa(img, *self._alvo):
                self._fechar_mapa(agora)
                self.avisar(f"Piloto: marcador posto em {self.sinais.lugar['nome']}.", "partida")
            else:
                self._falhou_no_mapa(agora, "o marcador não apareceu no mapa")
        elif self._mapa == "fechando":
            self._fechar_mapa(agora)  # o M não fechou o mapa: aperta de novo

    def _esperando(self, img, agora):
        if self.sinais.aviso(img, "pular"):
            self._mudar("onibus", agora)
            self.avisar("Piloto: no ônibus, procurando o marcador.", "partida")
            self._onibus(img, agora)

    def _onibus(self, img, agora):
        if self.sinais.aviso(img, "pular"):
            self._sem_pular = 0
        else:
            self._sem_pular += 1
            if self._sem_pular >= 3:  # o jogo jogou para fora no fim da rota, ou alguém pulou por nós
                self._mudar("queda", agora)
                self.avisar("Piloto: saí do ônibus sem pular; seguindo para o marcador.", "aviso")
                return
        m, confirmada = self._ler_marcador(img, agora)
        if m is None:
            if agora - self._desde >= SEM_MARCADOR_NO_ONIBUS:
                self._terminar("não vi o marcador. Ponha o marcador no mapa antes do ônibus sair.", "aviso")
            return
        if not confirmada:
            return
        self._menor = m.distancia if self._menor is None else min(self._menor, m.distancia)
        if m.distancia <= SALTAR_PERTO or m.distancia >= self._menor + SUBIU:
            self._tocar_tecla("espaco")
            self._mudar("queda", agora)
            self.avisar(f"Piloto: pulei do ônibus a {m.distancia} m do marcador.", "partida")

    def _queda(self, img, agora):
        self._ir_ao_marcador(img, agora)
        if self.fase != "queda":
            return
        dist, quando = self._progresso
        if dist is not None and agora - quando >= PARADO_NA_QUEDA:
            self._mudar("a_pe", agora)
            self.avisar(f"Piloto: caí a {dist} m do marcador; indo a pé.", "aviso")

    def _a_pe(self, img, agora):
        self._ir_ao_marcador(img, agora)
        if self.fase == "a_pe" and agora - self._desde >= TEMPO_A_PE:
            self._chegar(agora, "não cheguei no marcador; procurando baús por aqui.")

    def _baus(self, img, agora):
        if self._segurando_ate is not None:
            if agora < self._segurando_ate:
                return
            self._segurar(self.ajustes.tecla_interagir, False)
            self._segurando_ate = None
            self.abertos += 1
            self._pausa_ate = agora + PAUSA_DEPOIS_DO_BAU
            self._visto_bau = agora
            self.avisar(f"Piloto: baú {self.abertos} vasculhado.", "ok")
            if self.abertos >= self.ajustes.baus_por_partida:
                self._terminar(f"{self.abertos} baús vasculhados.")
            return
        if agora < self._pausa_ate:
            return
        if agora - self._desde >= TEMPO_DE_BAUS:
            self._terminar(f"tempo dos baús acabou ({self.abertos} vasculhados).")
            return
        if self.sinais.aviso(img, "vasculhar"):
            self._segurar("w", False)
            self._segurar(self.ajustes.tecla_interagir, True)
            self._segurando_ate = agora + SEGURAR_INTERAGIR
            return
        icones = self.sinais.baus(img)
        if icones:
            bau = min(icones, key=lambda i: abs(i.angulo))
            self._visto_bau = agora
            self._virar(GANHO_ANGULO * bau.angulo)
            self._segurar("w", abs(bau.angulo) < FRENTE)
        elif agora - self._visto_bau >= SEM_BAU:
            self._terminar(f"não achei mais baús ({self.abertos} vasculhados).")
        else:
            self._segurar("w", True)  # anda girando devagar até um baú aparecer no anel
            self._virar(VIRAR_PROCURANDO)

    # ---------- ajudas ----------

    def _fechar_mapa(self, agora):
        self._tocar_tecla("m")
        self._mapa, self._mapa_ate = "fechando", agora + TENTAR_MAPA

    def _falhou_no_mapa(self, agora, motivo):
        self._tentativas_mapa += 1
        if self._tentativas_mapa >= TENTATIVAS_MAPA:
            self._fechar_mapa(agora)
            self.avisar(f"Piloto: {motivo}; ponha o marcador à mão.", "aviso")
        else:
            self._tocar_tecla("shift")
            self._mapa, self._mapa_ate = "redefinido", agora + ESPERA_MAPA

    def _ir_ao_marcador(self, img, agora):
        self._segurar("w", True)
        m, confirmada = self._ler_marcador(img, agora)
        if m is None:
            if self._visto is None or agora - self._visto >= 2:
                self._virar(VIRAR_PROCURANDO)
            return
        larg, alt = img.size
        if m.na_borda:  # fora da tela: vira para o lado em que o jogo pôs o pino
            self._virar(-VIRAR_MAX if m.x < larg / 2 else VIRAR_MAX)
        else:
            self._virar(GANHO_X * (m.x - larg / 2))
        if not confirmada:
            return
        dist, _ = self._progresso
        if dist is None or m.distancia < dist - 2:
            self._progresso = (m.distancia, agora)
        if m.distancia <= CHEGOU:
            self._chegar(agora, f"cheguei no marcador ({m.distancia} m). Procurando baús.")

    def _chegar(self, agora, texto):
        self._segurar("w", False)
        self._mudar("baus", agora)
        self._visto_bau = agora
        self.avisar(f"Piloto: {texto}", "partida")

    def _ler_marcador(self, img, agora):
        """(Marcador ou None, distância confirmada?). A distância só vale depois que duas leituras
        concordam; depois disso, uma leitura que pula demais (erro do leitor, um "1" a mais) fica
        com a distância anterior, a não ser que se repita três vezes. A posição do pino sempre vale."""
        m = self.sinais.marcador(img)
        if m is None:
            return None, False
        self._visto = agora
        if self._dist is None:
            if self._candidata is not None and _perto(m.distancia, *self._candidata, agora):
                self._dist, self._dist_t = m.distancia, agora
                return m, True
            self._candidata = (m.distancia, agora)
            return m, False
        if not _perto(m.distancia, self._dist, self._dist_t, agora) and self._rejeitados < 2:
            self._rejeitados += 1
            return replace(m, distancia=self._dist), True
        self._rejeitados = 0
        self._dist, self._dist_t = m.distancia, agora
        return m, True

    def _mudar(self, fase, agora):
        self.fase = fase
        self._desde = agora

    def _terminar(self, texto, tipo="ok"):
        self.largar()
        self.fase = "fim"
        self.avisar(f"Piloto: {texto}", tipo)

    def _virar(self, dx):
        dx = round(max(-VIRAR_MAX, min(VIRAR_MAX, dx)))
        if abs(dx) >= 3:
            self.sistema.virar(dx)

    def _segurar(self, tecla, apertada):
        if apertada and tecla not in self._presas:
            self.sistema.apertar(tecla)
            self._presas.add(tecla)
        elif not apertada and tecla in self._presas:
            self._presas.discard(tecla)
            self.sistema.soltar(tecla)

    def _tocar_tecla(self, tecla):
        self.sistema.apertar(tecla)
        self._tocar.append(tecla)


def _perto(distancia, anterior, quando, agora):
    """A distância nova é possível, vindo da anterior no tempo que passou?"""
    return abs(distancia - anterior) <= 15 + VELOCIDADE_MAX * (agora - quando)
