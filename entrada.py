"""Mouse, teclado e atalho global pela API do Windows (SendInput e RegisterHotKey).

Sem bibliotecas externas e sem hook de teclado: o atalho F8 é registrado no sistema,
então o programa não lê nenhuma outra tecla que você digita.
"""
import ctypes
import threading
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_NOREPEAT = 0x4000
VK_F8 = 0x77
VK_F9 = 0x78
VK_F10 = 0x79
BELOW_NORMAL_PRIORITY_CLASS = 0x4000

# Scan codes físicos: o jogo lê a posição da tecla, não a letra
SCAN = {"w": 0x11, "a": 0x1E, "s": 0x1F, "d": 0x20, "espaco": 0x39, "e": 0x12, "x": 0x2D, "f": 0x21}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _Uniao(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _Uniao)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.GetMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT)
user32.GetMessageW.restype = wintypes.BOOL
user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
user32.PostThreadMessageW.argtypes = (wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)


def preparar_processo():
    """Chamar antes de abrir a janela: coordenadas em pixels reais e prioridade baixa."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        user32.SetProcessDPIAware()
    # abaixo do normal: o jogo sempre tem preferência na CPU
    kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS)


def eh_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def janela_em_foco():
    """Título e classe da janela em primeiro plano. Só pergunta ao Windows: não abre o processo do jogo."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", ""
    titulo = ctypes.create_unicode_buffer(256)
    classe = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, titulo, 256)
    user32.GetClassNameW(hwnd, classe, 256)
    return titulo.value, classe.value


def eh_janela_do_jogo(titulo, classe):
    # o Fortnite usa a janela padrão do Unreal Engine; a classe evita confundir com uma aba
    # "Fortnite" no navegador ou um vídeo do jogo
    return classe == "UnrealWindow" and titulo.strip().lower().startswith("fortnite")


def jogo_em_foco():
    return eh_janela_do_jogo(*janela_em_foco())


def _enviar(*eventos):
    lista = (INPUT * len(eventos))(*eventos)
    if user32.SendInput(len(eventos), lista, ctypes.sizeof(INPUT)) != len(eventos):
        raise ctypes.WinError(ctypes.get_last_error())


def _mouse(flags, dx=0, dy=0):
    return INPUT(type=INPUT_MOUSE, u=_Uniao(mi=MOUSEINPUT(dx=dx, dy=dy, dwFlags=flags)))


def _tecla(tecla, solta):
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if solta else 0)
    return INPUT(type=INPUT_KEYBOARD, u=_Uniao(ki=KEYBDINPUT(wScan=SCAN[tecla], dwFlags=flags)))


def posicao_cursor():
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def mover(x, y):
    """Põe o cursor em (x, y), em pixels da área de trabalho (o monitor principal começa em 0, 0)."""
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    larg = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    alt = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    # no modo absoluto o SendInput usa 0..65535 para cobrir todos os monitores juntos
    nx = round((x - vx) * 65535 / max(larg - 1, 1))
    ny = round((y - vy) * 65535 / max(alt - 1, 1))
    _enviar(_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, nx, ny))


def clicar(x, y):
    """Leva o mouse até o botão, clica e devolve o cursor para onde estava.

    O Fortnite só aceita o clique depois do hover. Tirar o cursor de cima também desfaz o
    destaque do hover, então o próximo print mostra se o botão sumiu mesmo.
    """
    antes = posicao_cursor()
    mover(x - 12, y - 6)
    time.sleep(0.06)
    mover(x, y)
    time.sleep(0.15)
    _enviar(_mouse(MOUSEEVENTF_LEFTDOWN))
    time.sleep(0.08)
    _enviar(_mouse(MOUSEEVENTF_LEFTUP))
    time.sleep(0.1)
    mover(*antes)


def virar(dx, dy=0):
    """Move o mouse a partir de onde ele está. Na partida o cursor fica preso e isso vira a câmera."""
    _enviar(_mouse(MOUSEEVENTF_MOVE, dx, dy))


def apertar(tecla):
    _enviar(_tecla(tecla, solta=False))


def soltar(tecla):
    _enviar(_tecla(tecla, solta=True))


def soltar_tudo():
    """Garante que nenhuma tecla do anti-AFK fique presa ao parar."""
    for tecla in SCAN:
        try:
            soltar(tecla)
        except OSError:
            pass


class AtalhoGlobal(threading.Thread):
    """Chama `ao_apertar` (nesta thread) sempre que a tecla é apertada, mesmo com o jogo em foco."""

    def __init__(self, ao_apertar, vk=VK_F8):
        super().__init__(daemon=True)
        self.ao_apertar = ao_apertar
        self.vk = vk
        self.erro = None
        self._id_thread = None
        self._pronto = threading.Event()

    def run(self):
        self._id_thread = kernel32.GetCurrentThreadId()
        # id = tecla: dois atalhos (F8 e F9) não se confundem
        if not user32.RegisterHotKey(None, self.vk, MOD_NOREPEAT, self.vk):
            self.erro = ctypes.WinError(ctypes.get_last_error())
            self._pronto.set()
            return
        msg = wintypes.MSG()
        # PeekMessage cria a fila de mensagens antes de avisar que está pronto
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        self._pronto.set()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    self.ao_apertar()
        finally:
            user32.UnregisterHotKey(None, self.vk)

    def iniciar(self):
        """Começa a escutar. Devolve o erro se a tecla já estiver em uso por outro programa."""
        self.start()
        self._pronto.wait(2)
        return self.erro

    def encerrar(self):
        if self._id_thread and self.is_alive():
            user32.PostThreadMessageW(self._id_thread, WM_QUIT, 0, 0)
