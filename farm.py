"""Farm Automático para Fortnite: clica sozinho em Jogar, Pular e Voltar ao saguão.

Só olha a tela e mexe mouse/teclado. Não lê a memória do jogo e não acessa a internet.
"""
import os
import queue
import sys
import time
import tkinter as tk
from tkinter import messagebox, ttk

try:
    import numpy  # noqa: F401
    from PIL import ImageTk
except ImportError:
    tk.Tk().withdraw()
    messagebox.showerror(
        "Farm Automático",
        "Faltam bibliotecas. Abra o terminal nesta pasta e rode:\n\npip install -r requirements.txt",
    )
    sys.exit(1)

import entrada
import visao
from automacao import Automacao
from config import BOTOES, LIMITES, PASTA, PASTA_BOTOES, Ajustes, caminho_botao

TITULO = "Farm Automático — Fortnite"


def _formatar(numero):
    return f"{numero:g}"


class Recorte:
    """Print congelado em tela cheia; o usuário arrasta um retângulo em volta do botão."""

    def __init__(self, root, botao, ao_terminar):
        self.botao = botao
        self.ao_terminar = ao_terminar
        self.print = visao.capturar_tela()
        larg, alt = self.print.size

        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)
        self.top.geometry(f"{larg}x{alt}+0+0")
        self.top.attributes("-topmost", True)
        self.foto = ImageTk.PhotoImage(self.print)
        self.tela = tk.Canvas(self.top, width=larg, height=alt, highlightthickness=0, cursor="crosshair")
        self.tela.pack()
        self.tela.create_image(0, 0, image=self.foto, anchor="nw")
        # faixa de instrução desenhada só no canvas, fora do print que vai ser recortado
        self.fundo = self.tela.create_rectangle(0, 0, 0, 0, fill="#111111", outline="")
        self.faixa = self.tela.create_text(larg // 2, 36, fill="white", font=("Segoe UI", 15, "bold"))
        self._mensagem(f"Arraste em volta do botão “{botao.nome}”   ·   Esc ou botão direito cancela")

        self.inicio = None
        self.caixa = None
        self.tela.bind("<ButtonPress-1>", self._apertar)
        self.tela.bind("<B1-Motion>", self._arrastar)
        self.tela.bind("<ButtonRelease-1>", self._soltar)
        self.tela.bind("<Button-3>", lambda e: self._fechar(False, "Captura cancelada"))
        self.top.bind("<Escape>", lambda e: self._fechar(False, "Captura cancelada"))
        self.top.focus_force()

    def _mensagem(self, texto):
        self.tela.itemconfig(self.faixa, text=texto)
        x0, y0, x1, y1 = self.tela.bbox(self.faixa)
        self.tela.coords(self.fundo, x0 - 16, y0 - 8, x1 + 16, y1 + 8)

    def _apertar(self, e):
        self.inicio = (e.x, e.y)
        if self.caixa:
            self.tela.delete(self.caixa)
        self.caixa = self.tela.create_rectangle(e.x, e.y, e.x, e.y, outline="#ff3b30", width=2)

    def _arrastar(self, e):
        if self.inicio:
            self.tela.coords(self.caixa, *self.inicio, e.x, e.y)

    def _soltar(self, e):
        if not self.inicio:
            return
        pedaco, erro = visao.recortar(self.print, *self.inicio, e.x, e.y)
        self.inicio = None
        if erro:
            # deixa tentar de novo sem sair da captura
            self.tela.delete(self.caixa)
            self.caixa = None
            self._mensagem(f"{erro}. Tente de novo   ·   Esc cancela")
            return
        os.makedirs(PASTA_BOTOES, exist_ok=True)
        pedaco.save(caminho_botao(self.botao.chave))
        self._fechar(True, f"{self.botao.nome}: imagem salva ({pedaco.width}x{pedaco.height})")

    def _fechar(self, salvou, mensagem):
        self.top.destroy()
        self.ao_terminar(salvou, mensagem)


class App:
    def __init__(self):
        self.ajustes = Ajustes.carregar()
        self.fila = queue.Queue()  # recados das outras threads: registro e atalho F8
        self.automacao = None
        self.partidas = 0
        self.capturando = False  # F8 não inicia o farm no meio de uma captura
        self.atalho = entrada.AtalhoGlobal(lambda: self.fila.put(("alternar", None)))
        self._vars = []  # o Tk perde a variável se ninguém guardar referência

        self.root = tk.Tk()
        self.root.title(TITULO)
        self.root.report_callback_exception = self._erro_interface
        escala = self.root.winfo_fpixels("1i") / 96
        self.root.geometry(f"{int(470 * escala)}x{int(690 * escala)}")
        self.root.minsize(int(430 * escala), int(560 * escala))
        self.root.attributes("-topmost", self.ajustes.sempre_no_topo)
        self.root.protocol("WM_DELETE_WINDOW", self.sair)
        self._montar()

    # ---------- interface ----------

    def _montar(self):
        r = self.root
        estilo = ttk.Style(r)
        estilo.configure("Titulo.TLabel", font=("Segoe UI", 15, "bold"))
        estilo.configure("Dica.TLabel", foreground="#6b6b6b")
        estilo.configure("Ok.TLabel", foreground="#1a7f37")
        estilo.configure("Falta.TLabel", foreground="#b42318")

        topo = ttk.Frame(r, padding=(12, 10, 12, 0))
        topo.pack(fill="x")
        ttk.Label(topo, text="Farm Automático", style="Titulo.TLabel").pack(anchor="w")
        self.estado_var = tk.StringVar(value="Parado")
        ttk.Label(topo, textvariable=self.estado_var).pack(anchor="w")

        linha = ttk.Frame(r, padding=(12, 8, 12, 4))
        linha.pack(fill="x")
        self.botao_iniciar = ttk.Button(linha, text="Iniciar (F8)", width=14, command=self.alternar)
        self.botao_iniciar.pack(side="left")
        self.topo_var = tk.BooleanVar(value=self.ajustes.sempre_no_topo)
        ttk.Checkbutton(linha, text="Sempre no topo", variable=self.topo_var, command=self._mudar_topo).pack(
            side="left", padx=12
        )

        quadro = ttk.LabelFrame(r, text="1. Imagens dos botões (tiradas do seu jogo)", padding=8)
        quadro.pack(fill="x", padx=12, pady=6)
        quadro.columnconfigure(1, weight=1)
        self.status_botoes = {}
        for i, b in enumerate(BOTOES):
            ttk.Label(quadro, text=b.nome).grid(row=i, column=0, sticky="w")
            ttk.Label(quadro, text=b.dica, style="Dica.TLabel").grid(row=i, column=1, sticky="w", padx=8)
            status = ttk.Label(quadro, width=7)
            status.grid(row=i, column=2)
            self.status_botoes[b.chave] = status
            ttk.Button(quadro, text="Capturar", width=9, command=lambda b=b: self.capturar(b)).grid(
                row=i, column=3, pady=1
            )
        ttk.Button(quadro, text="Testar na tela do jogo (3 s)", command=self.testar).grid(
            row=len(BOTOES), column=0, columnspan=4, sticky="ew", pady=(8, 0)
        )
        self._atualizar_status_botoes()

        aj = ttk.LabelFrame(r, text="2. Ajustes", padding=8)
        aj.pack(fill="x", padx=12, pady=6)
        aj.columnconfigure(1, weight=1)
        ttk.Label(aj, text="Precisão mínima").grid(row=0, column=0, sticky="w")
        self.limiar_var = tk.DoubleVar(value=self.ajustes.limiar)
        ttk.Scale(aj, from_=LIMITES["limiar"][0], to=0.95, variable=self.limiar_var, command=self._mudar_limiar).grid(
            row=0, column=1, sticky="ew", padx=8
        )
        self.limiar_txt = ttk.Label(aj, text=f"{self.ajustes.limiar:.2f}", width=5)
        self.limiar_txt.grid(row=0, column=2)

        leitura = ttk.Frame(aj)
        leitura.grid(row=1, column=0, columnspan=3, sticky="w", pady=4)
        ttk.Label(leitura, text="Ler a tela a cada").pack(side="left")
        self._numero(leitura, "intervalo", 0.5).pack(side="left", padx=4)
        ttk.Label(leitura, text="s").pack(side="left")

        self.afk_var = tk.BooleanVar(value=self.ajustes.anti_afk)
        ttk.Checkbutton(
            aj,
            text="Anti-AFK na partida (segura W/A/S/D aleatório)",
            variable=self.afk_var,
            command=lambda: setattr(self.ajustes, "anti_afk", self.afk_var.get()),
        ).grid(row=2, column=0, columnspan=3, sticky="w")
        afk = ttk.Frame(aj)
        afk.grid(row=3, column=0, columnspan=3, sticky="w", padx=(22, 0), pady=(2, 0))
        ttk.Label(afk, text="segurar por").pack(side="left")
        self._numero(afk, "afk_segurar", 0.5).pack(side="left", padx=4)
        ttk.Label(afk, text="s, a cada").pack(side="left")
        self._numero(afk, "afk_a_cada", 1).pack(side="left", padx=4)
        ttk.Label(afk, text="s").pack(side="left")

        registro = ttk.LabelFrame(r, text="Registro", padding=6)
        registro.pack(fill="both", expand=True, padx=12, pady=6)
        self.log_txt = tk.Text(registro, height=8, state="disabled", font=("Consolas", 9), wrap="word", relief="flat")
        self.log_txt.pack(fill="both", expand=True)

        admin = "Rodando como administrador." if entrada.eh_admin() else (
            "Sem administrador: se os cliques não pegarem no jogo, abra como administrador."
        )
        ttk.Label(r, text=f"F8 inicia/para de qualquer lugar.  {admin}", style="Dica.TLabel", wraplength=440).pack(
            anchor="w", padx=12, pady=(0, 8)
        )

    def _numero(self, pai, campo, passo):
        """Caixa numérica ligada a um ajuste; aceita vírgula e ignora valor fora da faixa."""
        menor, maior = LIMITES[campo]
        var = tk.StringVar(value=_formatar(getattr(self.ajustes, campo)))
        self._vars.append(var)

        def mudou(*_):
            try:
                valor = float(var.get().replace(",", "."))
            except ValueError:
                return
            if menor <= valor <= maior:
                setattr(self.ajustes, campo, valor)

        var.trace_add("write", mudou)
        return ttk.Spinbox(pai, from_=menor, to=maior, increment=passo, width=6, textvariable=var)

    def _mudar_limiar(self, _valor):
        self.ajustes.limiar = round(self.limiar_var.get(), 2)
        self.limiar_txt.config(text=f"{self.ajustes.limiar:.2f}")

    def _mudar_topo(self):
        self.ajustes.sempre_no_topo = self.topo_var.get()
        self.root.attributes("-topmost", self.ajustes.sempre_no_topo)

    def _atualizar_status_botoes(self):
        for b in BOTOES:
            tem = os.path.isfile(caminho_botao(b.chave))
            self.status_botoes[b.chave].config(text="ok" if tem else "falta", style="Ok.TLabel" if tem else "Falta.TLabel")

    def log(self, texto):
        self.log_txt.config(state="normal")
        self.log_txt.insert("end", f"{time.strftime('%H:%M:%S')}  {texto}\n")
        # registro não cresce sem fim em sessões longas
        if int(self.log_txt.index("end-1c").split(".")[0]) > 400:
            self.log_txt.delete("1.0", "101.0")
        self.log_txt.see("end")
        self.log_txt.config(state="disabled")

    def _erro_interface(self, _tipo, valor, _tb):
        self.log(f"Erro: {valor}")

    # ---------- farm ----------

    def _carregar_modelos(self):
        modelos = {}
        for b in BOTOES:
            caminho = caminho_botao(b.chave)
            if not os.path.isfile(caminho):
                continue
            try:
                modelos[b.chave] = visao.carregar_modelo(caminho)
            except (OSError, ValueError) as e:
                self.log(f"Imagem de {b.nome} inválida ({e}). Capture de novo.")
        return modelos

    @property
    def rodando(self):
        return bool(self.automacao and self.automacao.rodando)

    def alternar(self):
        if self.capturando:
            return
        if self.rodando:
            self.parar()
        else:
            self.iniciar()

    def iniciar(self):
        modelos = self._carregar_modelos()
        if "jogar" not in modelos:
            self.log("Capture pelo menos o botão Jogar antes de iniciar.")
            self.root.bell()
            return
        faltam = [b.nome for b in BOTOES if b.chave not in modelos]
        if faltam:
            self.log("Sem imagem, serão ignorados: " + ", ".join(faltam))
        self._salvar_ajustes()
        self.automacao = Automacao(self.ajustes, modelos, lambda texto: self.fila.put(("log", texto)))
        self.automacao.iniciar()
        self.botao_iniciar.config(text="Parar (F8)")
        self.log("Iniciado. Deixe o Fortnite aberto no saguão.")

    def parar(self):
        if not self.automacao:
            return
        self.automacao.encerrar()
        self.partidas += self.automacao.partidas
        self.automacao = None
        self.botao_iniciar.config(text="Iniciar (F8)")
        self.log("Parado.")

    def _ocupado(self):
        if self.rodando:
            self.log("Pare o farm antes de capturar ou testar.")
            return True
        return False

    def _contagem(self, texto, segundos, depois):
        """Esconde a janela e mostra uma contagem no topo da tela para dar tempo de abrir o jogo."""
        self.capturando = True
        self.root.withdraw()
        aviso = tk.Toplevel(self.root)
        aviso.overrideredirect(True)
        aviso.attributes("-topmost", True)
        rotulo = tk.Label(aviso, font=("Segoe UI", 14, "bold"), bg="#111111", fg="white", padx=18, pady=8)
        rotulo.pack()

        def tique(n):
            if n == 0:
                aviso.destroy()
                # espera a contagem sumir da tela antes do print
                self.root.after(200, depois)
                return
            rotulo.config(text=f"{texto}… {n}")
            aviso.update_idletasks()
            x = (self.root.winfo_screenwidth() - aviso.winfo_reqwidth()) // 2
            aviso.geometry(f"+{x}+40")
            self.root.after(1000, tique, n - 1)

        tique(segundos)

    def capturar(self, botao):
        if self._ocupado():
            return
        self._contagem(f"Deixe o “{botao.nome}” visível no jogo", 3, lambda: self._abrir_recorte(botao))

    def _abrir_recorte(self, botao):
        try:
            Recorte(self.root, botao, self._fim_recorte)
        except Exception as e:
            self._fim_recorte(False, f"Erro na captura: {e}")

    def _fim_recorte(self, _salvou, mensagem):
        self.capturando = False
        self.root.deiconify()
        self.log(mensagem)
        self._atualizar_status_botoes()

    def testar(self):
        if self._ocupado():
            return
        modelos = self._carregar_modelos()
        if not modelos:
            self.log("Nenhuma imagem capturada ainda.")
            return
        self._contagem("Abra o jogo", 3, lambda: self._fazer_teste(modelos))

    def _fazer_teste(self, modelos):
        try:
            quadro = visao.Quadro(visao.capturar_tela())
            self.log("Teste na tela atual:")
            for b in BOTOES:
                if b.chave not in modelos:
                    continue
                nota, x, y = visao.procurar(quadro, modelos[b.chave])
                if nota >= self.ajustes.limiar:
                    self.log(f"  {b.nome}: {nota:.2f}  ACHOU em ({x}, {y})")
                else:
                    self.log(f"  {b.nome}: {nota:.2f}  não está na tela")
        finally:
            self.capturando = False
            self.root.deiconify()

    # ---------- ciclo de vida ----------

    def _tique(self):
        while True:
            try:
                tipo, valor = self.fila.get_nowait()
            except queue.Empty:
                break
            if tipo == "log":
                self.log(valor)
            elif tipo == "alternar":
                self.alternar()
        if self.rodando:
            a = self.automacao
            onde = "na partida" if a.em_partida else "procurando botões"
            self.estado_var.set(f"Rodando — {onde}  ·  partidas iniciadas: {self.partidas + a.partidas}")
        else:
            self.estado_var.set(f"Parado  ·  partidas iniciadas: {self.partidas}")
        self.root.after(200, self._tique)

    def _salvar_ajustes(self):
        try:
            self.ajustes.salvar()
        except OSError as e:
            self.log(f"Não consegui salvar os ajustes: {e}")

    def rodar(self):
        erro = self.atalho.iniciar()
        if erro:
            self.log(f"F8 indisponível ({erro}). Use o botão Iniciar/Parar.")
        if os.path.isfile(caminho_botao("jogar")):
            self.log("Pronto. Abra o Fortnite no saguão e aperte F8.")
        else:
            self.log("Primeiro passo: capture as imagens dos botões (pelo menos Jogar).")
        self.root.after(200, self._tique)
        self.root.mainloop()

    def sair(self):
        self.parar()
        self.atalho.encerrar()
        self._salvar_ajustes()
        self.root.destroy()


def main():
    entrada.preparar_processo()  # antes de criar a janela
    try:
        App().rodar()
    except Exception:
        # com pythonw não há console: deixa o erro num arquivo
        import traceback

        with open(os.path.join(PASTA, "erro.log"), "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise


if __name__ == "__main__":
    main()
