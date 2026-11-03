"""Farm Automático para Fortnite: clica sozinho em Jogar, Pular e Voltar ao saguão.

Só olha a tela e mexe mouse/teclado. Não lê a memória do jogo e não acessa a internet.
"""
import ctypes
import os
import queue
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox, ttk

try:
    import numpy  # noqa: F401
    from PIL import Image, ImageDraw, ImageEnhance, ImageTk
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
from config import ARQUIVO_REGISTRO, BOTOES, LIMITES, PASTA, PASTA_BOTOES, Ajustes, caminho_botao

TITULO = "Farm Automático"

# Roxo da tempestade no fundo, dourado só na ação principal e no que pede atenção
COR = {
    "fundo": "#1b1530",
    "cartao": "#241c3f",
    "borda": "#382d5e",
    "campo": "#130e24",
    "botao": "#33295a",
    "botao_hover": "#3f3370",
    "texto": "#f1ecff",
    "suave": "#a497c7",
    "ouro": "#ffc93c",
    "ouro_claro": "#ffd970",
    "ouro_escuro": "#e6ad22",
    "verde": "#4fe3a0",
    "azul": "#6cb8ff",
    "laranja": "#ffa94d",
    "vermelho": "#ff6b6b",
    "vermelho_claro": "#ff8a8a",
}

# Estado mostrado no topo da janela: (texto grande, cor da faixa e do texto)
ESTADOS = {
    "parado": ("PARADO", COR["suave"]),
    "procurando": ("PROCURANDO BOTÕES", COR["azul"]),
    "partida": ("NA PARTIDA", COR["verde"]),
    "pausado": ("PAUSADO", COR["laranja"]),
    "preto": ("PRINT PRETO", COR["vermelho"]),
}

# Cor de cada tipo de linha do registro ("info" fica na cor do texto)
CORES_REGISTRO = {"ok": COR["verde"], "partida": COR["ouro"], "aviso": COR["laranja"], "erro": COR["vermelho"]}

MINIATURA = (84, 30)  # tamanho da prévia de cada botão capturado, antes da escala da tela


def _formatar(numero):
    return f"{numero:g}"


def _nota(nota):
    return f"{nota:.2f}".replace(".", ",")


def _duracao(segundos):
    s = int(segundos)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


def _fontes(root):
    """Bahnschrift condensada (vem no Windows 10 e 11) nos títulos e números, Segoe UI no resto."""
    tem = set(tkfont.families(root))

    def primeira(*nomes):
        return next((n for n in nomes if n in tem), nomes[-1])

    return {
        "titulo": primeira("Bahnschrift SemiBold Condensed", "Segoe UI Semibold"),
        "rotulo": primeira("Bahnschrift SemiBold", "Segoe UI Semibold"),
        "corpo": primeira("Segoe UI Variable Text", "Segoe UI"),
        "corpo_forte": primeira("Segoe UI Variable Text Semibold", "Segoe UI Semibold"),
        "mono": primeira("Cascadia Mono", "Consolas"),
    }


def _barra_escura(root):
    """Barra de título escura e na cor do fundo (Windows 11; no 10 fica só escura)."""
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        dwm = ctypes.windll.dwmapi
        escuro = ctypes.c_int(1)
        dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(escuro), ctypes.sizeof(escuro))
        r, g, b = (int(COR["fundo"][i : i + 2], 16) for i in (1, 3, 5))
        cor = ctypes.c_int(r | g << 8 | b << 16)
        dwm.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(cor), ctypes.sizeof(cor))
    except (AttributeError, OSError):
        pass


def desenhar_icone(lado=64):
    """Play dourado num quadrado arredondado: ícone da janela e, pelo gerar_exe.py, do Farm.exe."""
    k = lado / 64
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(
        (2 * k, 2 * k, 61 * k, 61 * k), radius=14 * k, fill=COR["fundo"], outline=COR["ouro"], width=round(4 * k)
    )
    d.polygon([(24 * k, 17 * k), (24 * k, 47 * k), (48 * k, 32 * k)], fill=COR["ouro"])
    return img


def _girar_registro():
    """Começa um registro novo quando passa de 1 MB, guardando o anterior como registro.log.1."""
    try:
        if os.path.getsize(ARQUIVO_REGISTRO) > 1_000_000:
            os.replace(ARQUIVO_REGISTRO, ARQUIVO_REGISTRO + ".1")
    except OSError:
        pass


class Recorte:
    """Print congelado em tela cheia; o usuário arrasta um retângulo em volta do botão.

    Fora da seleção o print fica escurecido, para destacar o que vai virar a imagem do botão.
    """

    def __init__(self, root, botao, ao_terminar, fontes):
        self.botao = botao
        self.ao_terminar = ao_terminar
        self.fontes = fontes
        self.print = visao.capturar_tela()
        larg, alt = self.print.size

        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)
        self.top.geometry(f"{larg}x{alt}+0+0")
        self.top.attributes("-topmost", True)
        self.escuro = ImageTk.PhotoImage(ImageEnhance.Brightness(self.print).enhance(0.4))
        self.claro = None  # pedaço original dentro da seleção
        self.tela = tk.Canvas(self.top, width=larg, height=alt, highlightthickness=0, cursor="crosshair", bg="black")
        self.tela.pack()
        self.tela.create_image(0, 0, image=self.escuro, anchor="nw")
        self.selecao = self.tela.create_image(0, 0, anchor="nw")
        self.caixa = self.tela.create_rectangle(0, 0, 0, 0, outline=COR["ouro"], width=2, state="hidden")
        self.medida_fundo = self.tela.create_rectangle(0, 0, 0, 0, fill=COR["ouro"], outline="", state="hidden")
        self.medida = self.tela.create_text(0, 0, anchor="nw", fill=COR["fundo"], font=(fontes["rotulo"], 10), state="hidden")

        # faixa de instrução desenhada só no canvas, fora do print que vai ser recortado
        self.faixa_fundo = self.tela.create_rectangle(0, 0, 0, 0, fill=COR["fundo"], outline="")
        self.faixa_linha = self.tela.create_rectangle(0, 0, 0, 0, fill=COR["ouro"], outline="")
        self.faixa = self.tela.create_text(larg // 2, 30, anchor="n", fill=COR["texto"], font=(fontes["titulo"], 18))
        self.faixa_dica = self.tela.create_text(larg // 2, 0, anchor="n", fill=COR["suave"], font=(fontes["corpo"], 10))
        if visao.tela_preta(self.print):
            self._mensagem("O print saiu preto", "No Fortnite, use “Tela cheia em janela” e capture de novo. Esc cancela.", erro=True)
        else:
            self._mensagem(
                f"Arraste em volta do texto de “{botao.nome}”",
                "Pegue só o texto do botão, bem justo. Esc ou botão direito cancela.",
            )

        self.inicio = None
        self.tela.bind("<ButtonPress-1>", self._apertar)
        self.tela.bind("<B1-Motion>", self._arrastar)
        self.tela.bind("<ButtonRelease-1>", self._soltar)
        self.tela.bind("<Button-3>", lambda e: self._fechar(False, "Captura cancelada"))
        self.top.bind("<Escape>", lambda e: self._fechar(False, "Captura cancelada"))
        self.top.focus_force()

    def _mensagem(self, titulo, dica, erro=False):
        t = self.tela
        t.itemconfig(self.faixa, text=titulo, fill=COR["vermelho"] if erro else COR["texto"])
        _, _, _, y1 = t.bbox(self.faixa)
        t.coords(self.faixa_dica, t.coords(self.faixa)[0], y1 + 2)
        t.itemconfig(self.faixa_dica, text=dica)
        x0 = min(t.bbox(self.faixa)[0], t.bbox(self.faixa_dica)[0])
        x1 = max(t.bbox(self.faixa)[2], t.bbox(self.faixa_dica)[2])
        y1 = t.bbox(self.faixa_dica)[3]
        t.coords(self.faixa_fundo, x0 - 28, 18, x1 + 28, y1 + 14)
        t.coords(self.faixa_linha, x0 - 28, 18, x1 + 28, 21)
        t.itemconfig(self.faixa_linha, fill=COR["vermelho"] if erro else COR["ouro"])

    def _apertar(self, e):
        self.inicio = (e.x, e.y)
        self._desenhar(e.x, e.y)

    def _arrastar(self, e):
        if self.inicio:
            self._desenhar(e.x, e.y)

    def _desenhar(self, x, y):
        x0, x1 = sorted((self.inicio[0], x))
        y0, y1 = sorted((self.inicio[1], y))
        t = self.tela
        for item in (self.caixa, self.medida_fundo, self.medida):
            t.itemconfig(item, state="normal")
        t.coords(self.caixa, x0, y0, x1, y1)
        if x1 > x0 and y1 > y0:
            self.claro = ImageTk.PhotoImage(self.print.crop((x0, y0, x1, y1)))
            t.itemconfig(self.selecao, image=self.claro)
            t.coords(self.selecao, x0, y0)
        # medida embaixo da seleção, ou em cima se não couber
        my = y1 + 8 if y1 + 34 < self.print.height else y0 - 30
        t.itemconfig(self.medida, text=f"{x1 - x0} × {y1 - y0}")
        t.coords(self.medida, x0 + 6, my + 3)
        mx0, my0, mx1, my1 = t.bbox(self.medida)
        t.coords(self.medida_fundo, x0, my, mx1 + 6, my1 + 3)

    def _esconder_selecao(self):
        for item in (self.caixa, self.medida_fundo, self.medida):
            self.tela.itemconfig(item, state="hidden")
        self.tela.itemconfig(self.selecao, image="")
        self.claro = None

    def _soltar(self, e):
        if not self.inicio:
            return
        pedaco, erro = visao.recortar(self.print, *self.inicio, e.x, e.y)
        self.inicio = None
        if erro:
            # deixa tentar de novo sem sair da captura
            self._esconder_selecao()
            self._mensagem(erro, "Arraste de novo em volta do texto do botão. Esc cancela.", erro=True)
            return
        os.makedirs(PASTA_BOTOES, exist_ok=True)
        pedaco.save(caminho_botao(self.botao.chave))
        self._fechar(True, f"{self.botao.nome}: imagem salva ({pedaco.width}×{pedaco.height})")

    def _fechar(self, salvou, mensagem):
        self.top.destroy()
        self.ao_terminar(salvou, mensagem)


class App:
    def __init__(self):
        self.ajustes = Ajustes.carregar()
        self.fila = queue.Queue()  # recados das outras threads: registro e atalho F8
        self.automacao = None
        self.partidas = 0
        self.cliques = 0
        self.tempo = 0.0          # segundos rodando nas vezes anteriores, desde que a janela abriu
        self.capturando = False   # F8 não inicia o farm no meio de uma captura
        self.notas_teste = {}     # chave do botão -> nota no último "Testar"
        self.tem_jogar = False
        self.atalho = entrada.AtalhoGlobal(lambda: self.fila.put(("alternar", None)))
        self._vars = []           # o Tk perde a variável se ninguém guardar referência
        self._miniaturas = {}     # chave -> (data do arquivo, imagem), para não reler o PNG à toa
        self._mostrado = None     # último estado desenhado no topo
        _girar_registro()

        self.root = tk.Tk()
        self.root.title(TITULO)
        self.root.configure(bg=COR["fundo"])
        self.root.report_callback_exception = self._erro_interface
        self.escala = self.root.winfo_fpixels("1i") / 96
        alt = min(self._px(640), self.root.winfo_screenheight() - self._px(80))
        self.root.geometry(f"{self._px(880)}x{alt}")
        self.root.minsize(self._px(800), min(self._px(560), alt))
        self.root.attributes("-topmost", self.ajustes.sempre_no_topo)
        self.root.protocol("WM_DELETE_WINDOW", self.sair)
        self.fontes = _fontes(self.root)
        self._estilos()
        self._montar()
        self._icone()
        _barra_escura(self.root)

    def _px(self, n):
        """Pixels de tela para um tamanho pensado em 100% de escala do Windows."""
        return int(round(n * self.escala))

    # ---------- interface ----------

    def _estilos(self):
        f, px = self.fontes, self._px
        e = ttk.Style(self.root)
        e.theme_use("clam")
        e.configure(
            ".",
            background=COR["fundo"], foreground=COR["texto"], font=(f["corpo"], 10),
            bordercolor=COR["borda"], lightcolor=COR["fundo"], darkcolor=COR["fundo"],
            troughcolor=COR["campo"], fieldbackground=COR["campo"], focuscolor=COR["ouro"],
            selectbackground=COR["borda"], selectforeground=COR["texto"],
            insertcolor=COR["texto"], arrowcolor=COR["suave"],
        )
        e.configure("Cartao.TFrame", background=COR["cartao"])
        e.configure("Suave.TLabel", foreground=COR["suave"])
        e.configure("Rodape.TLabel", foreground=COR["suave"], font=(f["corpo"], 9))
        e.configure("Rotulo.TLabel", foreground=COR["suave"], font=(f["rotulo"], 9))
        e.configure("Estado.TLabel", font=(f["titulo"], 30))
        e.configure("Numero.TLabel", font=(f["titulo"], 22))
        e.configure("Cartao.TLabel", background=COR["cartao"])
        e.configure("CartaoForte.TLabel", background=COR["cartao"], font=(f["corpo_forte"], 10))
        e.configure("CartaoSuave.TLabel", background=COR["cartao"], foreground=COR["suave"], font=(f["corpo"], 9))
        e.configure("Secao.TLabel", background=COR["cartao"], foreground=COR["suave"], font=(f["rotulo"], 10))
        for nome, cor in (("Ok", COR["verde"]), ("Falta", COR["vermelho"]), ("Nota", COR["suave"])):
            e.configure(f"{nome}.TLabel", background=COR["cartao"], foreground=cor, font=(f["rotulo"], 10))

        for nome, cor, claro, escuro, texto in (
            ("Primario", COR["ouro"], COR["ouro_claro"], COR["ouro_escuro"], COR["fundo"]),
            ("Parar", COR["vermelho"], COR["vermelho_claro"], COR["vermelho"], COR["fundo"]),
        ):
            e.configure(
                f"{nome}.TButton", background=cor, foreground=texto, font=(f["titulo"], 16),
                bordercolor=cor, lightcolor=cor, darkcolor=cor, focuscolor=texto, padding=(0, px(8)),
            )
            e.map(
                f"{nome}.TButton",
                background=[("pressed", escuro), ("active", claro)],
                lightcolor=[("pressed", escuro), ("active", claro)],
                darkcolor=[("pressed", escuro), ("active", claro)],
                bordercolor=[("pressed", escuro), ("active", claro)],
            )
        e.configure(
            "TButton", background=COR["botao"], foreground=COR["texto"], bordercolor=COR["borda"],
            lightcolor=COR["botao"], darkcolor=COR["botao"], padding=(px(10), px(3)),
        )
        e.map(
            "TButton",
            background=[("pressed", COR["borda"]), ("active", COR["botao_hover"])],
            lightcolor=[("active", COR["botao_hover"])],
            darkcolor=[("active", COR["botao_hover"])],
        )
        self._controles(e)
        e.configure("Cartao.TCheckbutton", background=COR["cartao"])
        e.map("Cartao.TCheckbutton", background=[("active", COR["cartao"])])
        e.configure(
            "TSpinbox", fieldbackground=COR["campo"], background=COR["botao"], foreground=COR["texto"],
            arrowcolor=COR["texto"], bordercolor=COR["borda"], lightcolor=COR["campo"], darkcolor=COR["campo"],
        )
        e.configure("Ouro.Horizontal.TScale", background=COR["cartao"])
        e.configure(
            "Vertical.TScrollbar", background=COR["botao"], troughcolor=COR["campo"], bordercolor=COR["campo"],
            lightcolor=COR["botao"], darkcolor=COR["botao"], arrowcolor=COR["suave"],
        )
        e.map("Vertical.TScrollbar", background=[("active", COR["botao_hover"])])

    def _controles(self, e):
        """Caixinha de marcar e controle deslizante desenhados aqui, no lugar dos do tema clam."""
        t = self._px(16)
        g = t * 4  # desenha 4x maior e reduz, para a borda sair lisa
        self._imagens = []

        def foto(img):
            self._imagens.append(ImageTk.PhotoImage(img.resize((img.width // 4, img.height // 4), Image.LANCZOS)))
            return self._imagens[-1]

        def caixa(fundo, borda, marcada=False):
            img = Image.new("RGBA", (g, g), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.rounded_rectangle((2, 2, g - 3, g - 3), radius=t, fill=fundo, outline=borda, width=6)
            if marcada:
                d.line([(t * 0.95, t * 2.1), (t * 1.75, t * 2.9), (t * 3.1, t * 1.25)], fill=COR["fundo"], width=t // 2, joint="curve")
            return foto(img)

        def bolinha(cor):
            img = Image.new("RGBA", (g, g), (0, 0, 0, 0))
            ImageDraw.Draw(img).ellipse((6, 6, g - 7, g - 7), fill=cor, outline=COR["cartao"], width=8)
            return foto(img)

        trilho = Image.new("RGBA", (g * 3, g), (0, 0, 0, 0))
        ImageDraw.Draw(trilho).rounded_rectangle((4, g // 2 - 12, g * 3 - 5, g // 2 + 12), radius=12, fill=COR["borda"])

        e.element_create(
            "Farm.Checkbutton.indicator", "image", caixa(COR["campo"], COR["borda"]),
            ("selected", caixa(COR["ouro"], COR["ouro"], marcada=True)),
            ("active", caixa(COR["botao"], COR["suave"])),
            width=t + self._px(8), sticky="w",
        )
        e.layout("Cartao.TCheckbutton", [("Checkbutton.padding", {"sticky": "nswe", "children": [
            ("Farm.Checkbutton.indicator", {"side": "left", "sticky": ""}),
            ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [("Checkbutton.label", {"sticky": "nswe"})]}),
        ]})])
        e.element_create("Farm.Scale.trough", "image", foto(trilho), border=(t, 0), sticky="ew")
        e.element_create(
            "Farm.Scale.slider", "image", bolinha(COR["ouro"]),
            ("pressed", bolinha(COR["ouro_escuro"])), ("active", bolinha(COR["ouro_claro"])),
        )
        e.layout("Ouro.Horizontal.TScale", [("Farm.Scale.trough", {"sticky": "nswe", "children": [
            ("Farm.Scale.slider", {"side": "left", "sticky": ""}),
        ]})])

    def _cartao(self, pai, titulo, **posicao):
        borda = tk.Frame(pai, bg=COR["cartao"], highlightthickness=1, highlightbackground=COR["borda"])
        borda.pack(**posicao)
        dentro = ttk.Frame(borda, style="Cartao.TFrame", padding=self._px(14))
        dentro.pack(fill="both", expand=True)
        ttk.Label(dentro, text=titulo, style="Secao.TLabel").pack(anchor="w", pady=(0, self._px(8)))
        return dentro

    def _montar(self):
        r, px = self.root, self._px
        r.columnconfigure(1, weight=1)
        r.rowconfigure(1, weight=1)

        # faixa fina no topo com a cor do estado: dá para ver de longe se está rodando
        self.faixa = tk.Frame(r, height=px(5), bg=COR["suave"])
        self.faixa.grid(row=0, column=0, columnspan=2, sticky="ew")

        esquerda = ttk.Frame(r, padding=(px(22), px(16), px(10), px(14)))
        esquerda.grid(row=1, column=0, sticky="nsew")
        direita = ttk.Frame(r, padding=(px(10), px(16), px(22), px(16)))
        direita.grid(row=1, column=1, sticky="nsew")

        self._montar_estado(esquerda)
        self._montar_ajustes(esquerda)
        self._montar_rodape(esquerda)
        self._montar_botoes(direita)
        self._montar_registro(direita)
        self._atualizar_status_botoes()

    def _montar_estado(self, pai):
        px = self._px
        ttk.Label(pai, text="FARM AUTOMÁTICO · FORTNITE", style="Rotulo.TLabel").pack(anchor="w")
        self.estado_lbl = ttk.Label(pai, style="Estado.TLabel")
        self.estado_lbl.pack(anchor="w")
        self.detalhe_lbl = ttk.Label(pai, style="Suave.TLabel", wraplength=px(320), justify="left")
        self.detalhe_lbl.pack(anchor="w", fill="x")

        numeros = ttk.Frame(pai)
        numeros.pack(fill="x", pady=(px(16), px(14)))
        self.numeros = {}
        for i, (chave, rotulo) in enumerate((("partidas", "PARTIDAS"), ("tempo", "TEMPO RODANDO"), ("cliques", "CLIQUES"))):
            numeros.columnconfigure(i, weight=1, uniform="numeros")
            ttk.Label(numeros, text=rotulo, style="Rotulo.TLabel").grid(row=0, column=i, sticky="w")
            self.numeros[chave] = ttk.Label(numeros, style="Numero.TLabel")
            self.numeros[chave].grid(row=1, column=i, sticky="w")

        self.botao_iniciar = ttk.Button(pai, style="Primario.TButton", command=self.alternar, cursor="hand2")
        self.botao_iniciar.pack(fill="x")

    def _montar_ajustes(self, pai):
        px = self._px
        g = self._cartao(pai, "AJUSTES", fill="x", pady=(px(16), 0))
        g = ttk.Frame(g, style="Cartao.TFrame")
        g.pack(fill="x")
        g.columnconfigure(1, weight=1)

        ttk.Label(g, text="Precisão mínima", style="Cartao.TLabel").grid(row=0, column=0, sticky="w")
        self.limiar_var = tk.DoubleVar(value=self.ajustes.limiar)
        ttk.Scale(
            g, from_=LIMITES["limiar"][0], to=0.95, variable=self.limiar_var, command=self._mudar_limiar,
            style="Ouro.Horizontal.TScale", cursor="hand2",
        ).grid(
            row=0, column=1, sticky="ew", padx=px(10)
        )
        self.limiar_txt = ttk.Label(g, text=_nota(self.ajustes.limiar), width=4, style="CartaoForte.TLabel")
        self.limiar_txt.grid(row=0, column=2, sticky="e")

        leitura = ttk.Frame(g, style="Cartao.TFrame")
        leitura.grid(row=1, column=0, columnspan=3, sticky="w", pady=(px(8), 0))
        ttk.Label(leitura, text="Ler a tela a cada", style="Cartao.TLabel").pack(side="left")
        self._numero(leitura, "intervalo", 0.5).pack(side="left", padx=px(6))
        ttk.Label(leitura, text="s", style="Cartao.TLabel").pack(side="left")

        self._opcao(g, 2, "Pausar quando o Fortnite sair do primeiro plano", "so_com_jogo_em_foco")
        self._opcao(g, 3, "Anti-AFK na partida (segura W/A/S/D aleatório)", "anti_afk")
        afk = ttk.Frame(g, style="Cartao.TFrame")
        afk.grid(row=4, column=0, columnspan=3, sticky="w", padx=(px(24), 0), pady=(px(4), 0))
        ttk.Label(afk, text="por", style="CartaoSuave.TLabel").pack(side="left")
        self._numero(afk, "afk_segurar", 0.5).pack(side="left", padx=px(6))
        ttk.Label(afk, text="s, a cada", style="CartaoSuave.TLabel").pack(side="left")
        self._numero(afk, "afk_a_cada", 1).pack(side="left", padx=px(6))
        ttk.Label(afk, text="s", style="CartaoSuave.TLabel").pack(side="left")
        self._opcao(g, 5, "Manter esta janela sempre no topo", "sempre_no_topo", self._mudar_topo)

    def _montar_rodape(self, pai):
        abrir = "o Farm.exe" if getattr(sys, "frozen", False) else "o iniciar.bat"
        admin = "Rodando como administrador." if entrada.eh_admin() else (
            f"Sem administrador: se os cliques não pegarem, abra {abrir} como administrador."
        )
        ttk.Label(
            pai, text=f"F8 inicia e para de qualquer lugar. {admin}", style="Rodape.TLabel",
            wraplength=self._px(320), justify="left",
        ).pack(side="bottom", anchor="w")

    def _montar_botoes(self, pai):
        px = self._px
        dentro = self._cartao(pai, "BOTÕES DO JOGO", fill="x")
        lista = ttk.Frame(dentro, style="Cartao.TFrame")
        lista.pack(fill="x")
        lista.columnconfigure(1, weight=1)
        self.status_botoes = {}
        self.miniatura_lbls = {}
        for i, b in enumerate(BOTOES):
            mini = tk.Label(lista, bg=COR["campo"], bd=0)
            mini.grid(row=i, column=0, padx=(0, px(12)), pady=px(3))
            self.miniatura_lbls[b.chave] = mini
            nomes = ttk.Frame(lista, style="Cartao.TFrame")
            nomes.grid(row=i, column=1, sticky="w")
            ttk.Label(nomes, text=b.nome, style="CartaoForte.TLabel").pack(anchor="w")
            ttk.Label(nomes, text=b.dica, style="CartaoSuave.TLabel").pack(anchor="w")
            status = ttk.Label(lista, width=5, anchor="e")
            status.grid(row=i, column=2, padx=px(10))
            self.status_botoes[b.chave] = status
            ttk.Button(lista, text="Capturar", command=lambda b=b: self.capturar(b), cursor="hand2").grid(row=i, column=3)
        ttk.Button(dentro, text="Testar na tela do jogo (3 s)", command=self.testar, cursor="hand2").pack(
            fill="x", pady=(px(10), 0)
        )

    def _montar_registro(self, pai):
        px = self._px
        dentro = self._cartao(pai, "REGISTRO", fill="both", expand=True, pady=(px(14), 0))
        caixa = ttk.Frame(dentro, style="Cartao.TFrame")
        caixa.pack(fill="both", expand=True)
        self.log_txt = tk.Text(
            caixa, height=6, state="disabled", wrap="word", font=(self.fontes["mono"], 9),
            bg=COR["campo"], fg=COR["texto"], relief="flat", bd=0, highlightthickness=0,
            padx=px(10), pady=px(8), selectbackground=COR["borda"], insertbackground=COR["texto"],
        )
        barra = ttk.Scrollbar(caixa, orient="vertical", command=self.log_txt.yview)
        self.log_txt.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        self.log_txt.pack(side="left", fill="both", expand=True)
        self.log_txt.tag_configure("hora", foreground=COR["suave"])
        for tipo, cor in CORES_REGISTRO.items():
            self.log_txt.tag_configure(tipo, foreground=cor)

    def _icone(self):
        self._icone_img = ImageTk.PhotoImage(desenhar_icone())
        self.root.iconphoto(True, self._icone_img)

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
        return ttk.Spinbox(
            pai, from_=menor, to=maior, increment=passo, width=5, textvariable=var, font=(self.fontes["corpo"], 10)
        )

    def _opcao(self, pai, linha, texto, campo, depois=None):
        var = tk.BooleanVar(value=getattr(self.ajustes, campo))
        self._vars.append(var)

        def mudou():
            setattr(self.ajustes, campo, var.get())
            if depois:
                depois()

        ttk.Checkbutton(pai, text=texto, variable=var, command=mudou, style="Cartao.TCheckbutton").grid(
            row=linha, column=0, columnspan=3, sticky="w", pady=(self._px(8), 0)
        )

    def _mudar_limiar(self, _valor):
        self.ajustes.limiar = round(self.limiar_var.get(), 2)
        self.limiar_txt.config(text=_nota(self.ajustes.limiar))
        self._atualizar_status_botoes()

    def _mudar_topo(self):
        self.root.attributes("-topmost", self.ajustes.sempre_no_topo)

    def _miniatura(self, chave):
        """Prévia da imagem capturada, ou um quadro vazio quando ainda não tem."""
        caminho = caminho_botao(chave)
        try:
            data = os.path.getmtime(caminho)
        except OSError:
            data = None
        guardada = self._miniaturas.get(chave)
        if guardada and guardada[0] == data:
            return guardada[1]
        larg, alt = self._px(MINIATURA[0]), self._px(MINIATURA[1])
        fundo = Image.new("RGB", (larg, alt), COR["campo"])
        if data is None:
            ImageDraw.Draw(fundo).rectangle((0, 0, larg - 1, alt - 1), outline=COR["borda"])
        else:
            try:
                with Image.open(caminho) as img:
                    img = img.convert("RGB")
                    img.thumbnail((larg - 4, alt - 4), Image.LANCZOS)
                    fundo.paste(img, ((larg - img.width) // 2, (alt - img.height) // 2))
            except OSError:
                pass
        foto = ImageTk.PhotoImage(fundo)
        self._miniaturas[chave] = (data, foto)
        return foto

    def _atualizar_status_botoes(self):
        for b in BOTOES:
            self.miniatura_lbls[b.chave].config(image=self._miniatura(b.chave))
            status = self.status_botoes[b.chave]
            nota = self.notas_teste.get(b.chave)
            if not os.path.isfile(caminho_botao(b.chave)):
                # só o Jogar é obrigatório; os outros sem imagem são ignorados
                status.config(text="falta", style="Falta.TLabel" if b.chave == "jogar" else "Nota.TLabel")
            elif nota is None:
                status.config(text="ok", style="Ok.TLabel")
            else:
                # depois do Testar mostra a nota: verde se achou na tela
                status.config(text=_nota(nota), style="Ok.TLabel" if nota >= self.ajustes.limiar else "Nota.TLabel")
        self.tem_jogar = os.path.isfile(caminho_botao("jogar"))

    def log(self, texto, tipo="info"):
        t = self.log_txt
        t.config(state="normal")
        t.insert("end", time.strftime("%H:%M:%S") + "  ", "hora")
        t.insert("end", texto + "\n", tipo)
        # registro não cresce sem fim em sessões longas
        if int(t.index("end-1c").split(".")[0]) > 400:
            t.delete("1.0", "101.0")
        t.see("end")
        t.config(state="disabled")
        try:
            with open(ARQUIVO_REGISTRO, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {texto}\n")
        except OSError:
            pass

    def _erro_interface(self, _tipo, valor, _tb):
        self.log(f"Erro: {valor}", "erro")

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
                self.log(f"Imagem de {b.nome} inválida ({e}). Capture de novo.", "erro")
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
        self.parar()  # se o farm anterior parou sozinho e a janela ainda não viu, fecha ele antes
        modelos = self._carregar_modelos()
        if "jogar" not in modelos:
            self.log("Capture pelo menos o botão Jogar antes de iniciar.", "aviso")
            self.root.bell()
            return
        faltam = [b.nome for b in BOTOES if b.chave not in modelos]
        if faltam:
            self.log("Sem imagem, serão ignorados: " + ", ".join(faltam))
        self._salvar_ajustes()
        self.automacao = Automacao(self.ajustes, modelos, lambda texto, tipo="info": self.fila.put(("log", (texto, tipo))))
        self.automacao.iniciar()
        self.log("Iniciado. Deixe o Fortnite aberto no saguão.")

    def parar(self):
        a = self.automacao
        if not a:
            return
        a.encerrar()
        self.partidas += a.partidas
        self.cliques += a.cliques
        self.tempo += time.monotonic() - a.inicio
        self.automacao = None
        self.log("Parado.")

    def _ocupado(self):
        if self.rodando:
            self.log("Pare o farm antes de capturar ou testar.", "aviso")
            return True
        return False

    def _contagem(self, texto, segundos, depois):
        """Esconde a janela e mostra uma contagem no topo da tela para dar tempo de abrir o jogo."""
        self.capturando = True
        self.root.withdraw()
        aviso = tk.Toplevel(self.root)
        aviso.overrideredirect(True)
        aviso.attributes("-topmost", True)
        caixa = tk.Frame(aviso, bg=COR["fundo"], highlightthickness=2, highlightbackground=COR["ouro"])
        caixa.pack()
        numero = tk.Label(caixa, font=(self.fontes["titulo"], 26), bg=COR["fundo"], fg=COR["ouro"], padx=self._px(16))
        numero.pack(side="left")
        tk.Label(caixa, text=texto, font=(self.fontes["corpo"], 12), bg=COR["fundo"], fg=COR["texto"]).pack(
            side="left", padx=(0, self._px(22)), pady=self._px(10)
        )

        def tique(n):
            if n == 0:
                aviso.destroy()
                # espera a contagem sumir da tela antes do print
                self.root.after(200, depois)
                return
            numero.config(text=str(n))
            aviso.update_idletasks()
            x = (self.root.winfo_screenwidth() - aviso.winfo_reqwidth()) // 2
            aviso.geometry(f"+{x}+{self._px(40)}")
            self.root.after(1000, tique, n - 1)

        tique(segundos)

    def capturar(self, botao):
        if self._ocupado():
            return
        self._contagem(f"Deixe o “{botao.nome}” visível no jogo", 3, lambda: self._abrir_recorte(botao))

    def _abrir_recorte(self, botao):
        try:
            Recorte(self.root, botao, self._fim_recorte(botao), self.fontes)
        except Exception as e:
            self._fim_recorte(botao)(False, f"Erro na captura: {e}")

    def _fim_recorte(self, botao):
        def fim(salvou, mensagem):
            self.capturando = False
            if salvou:
                self.notas_teste.pop(botao.chave, None)  # a nota era da imagem antiga
            self.root.deiconify()
            self.log(mensagem, "ok" if salvou else "info")
            self._atualizar_status_botoes()

        return fim

    def testar(self):
        if self._ocupado():
            return
        modelos = self._carregar_modelos()
        if not modelos:
            self.log("Nenhuma imagem capturada ainda.", "aviso")
            return
        self._contagem("Abra o jogo", 3, lambda: self._fazer_teste(modelos))

    def _fazer_teste(self, modelos):
        try:
            titulo, classe = entrada.janela_em_foco()
            img = visao.capturar_tela()
            self.log("Teste na tela atual:")
            if entrada.eh_janela_do_jogo(titulo, classe):
                self.log(f"  Janela em foco: “{titulo.strip()}”. É o Fortnite.", "ok")
            else:
                self.log(
                    f"  Janela em foco: “{titulo.strip() or 'sem título'}” ({classe}). Não parece o Fortnite: "
                    "com “Pausar quando o Fortnite sair do primeiro plano” ligado, o farm fica pausado.",
                    "aviso",
                )
            if visao.tela_preta(img):
                self.log("  O print saiu preto. No Fortnite, use “Tela cheia em janela”.", "erro")
                return
            quadro = visao.Quadro(img)
            self.notas_teste = {}
            for b in BOTOES:
                if b.chave not in modelos:
                    continue
                nota, x, y = visao.procurar(quadro, modelos[b.chave])
                self.notas_teste[b.chave] = nota
                if nota >= self.ajustes.limiar:
                    self.log(f"  {b.nome}: {_nota(nota)}, achou em ({x}, {y})", "ok")
                else:
                    self.log(f"  {b.nome}: {_nota(nota)}, não está na tela")
            self._atualizar_status_botoes()
        finally:
            self.capturando = False
            self.root.deiconify()

    # ---------- ciclo de vida ----------

    def _estado(self):
        """(chave em ESTADOS, frase de detalhe) do que o farm está fazendo agora."""
        a = self.automacao
        if not self.rodando:
            if self.tem_jogar:
                return "parado", "Deixe o Fortnite no saguão e aperte F8."
            return "parado", "Capture pelo menos o botão Jogar para começar."
        if a.situacao == "pausado":
            return "pausado", "O Fortnite saiu do primeiro plano. Volte para o jogo para continuar."
        if a.situacao == "preto":
            return "preto", "O jogo não aparece no print. No Fortnite, use “Tela cheia em janela”."
        if a.em_partida:
            return "partida", "Anti-AFK ligado." if self.ajustes.anti_afk else "Anti-AFK desligado."
        return "procurando", f"Lendo a tela a cada {_formatar(self.ajustes.intervalo)} s."

    def _desenhar_estado(self):
        a = self.automacao
        self.numeros["partidas"].config(text=str(self.partidas + (a.partidas if a else 0)))
        self.numeros["cliques"].config(text=str(self.cliques + (a.cliques if a else 0)))
        self.numeros["tempo"].config(text=_duracao(self.tempo + (time.monotonic() - a.inicio if a else 0)))

        chave, detalhe = self._estado()
        if (chave, detalhe) == self._mostrado:
            return
        self._mostrado = (chave, detalhe)
        texto, cor = ESTADOS[chave]
        self.estado_lbl.config(text=texto, foreground=cor)
        self.faixa.config(bg=cor)
        self.detalhe_lbl.config(text=detalhe)
        self.root.title(f"{TITULO} · {texto.capitalize()}")
        if self.rodando:
            self.botao_iniciar.config(text="■   PARAR   ·   F8", style="Parar.TButton")
        else:
            self.botao_iniciar.config(text="▶   INICIAR   ·   F8", style="Primario.TButton")

    def _tique(self):
        while True:
            try:
                tipo, valor = self.fila.get_nowait()
            except queue.Empty:
                break
            if tipo == "log":
                self.log(*valor)
            elif tipo == "alternar":
                self.alternar()
        if self.automacao and not self.automacao.rodando:
            self.parar()  # o farm parou sozinho, por exemplo quando os cliques não pegam
        self._desenhar_estado()
        self.root.after(200, self._tique)

    def _salvar_ajustes(self):
        try:
            self.ajustes.salvar()
        except OSError as e:
            self.log(f"Não consegui salvar os ajustes: {e}", "erro")

    def rodar(self):
        erro = self.atalho.iniciar()
        if erro:
            self.log(f"F8 indisponível ({erro}). Use o botão Iniciar/Parar.", "aviso")
        if self.tem_jogar:
            self.log("Pronto. Abra o Fortnite no saguão e aperte F8.")
        else:
            self.log("Primeiro passo: capture as imagens dos botões (pelo menos Jogar).")
        self._desenhar_estado()
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
