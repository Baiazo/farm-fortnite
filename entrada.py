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
MOUSEEVENTF_ABSOLUTE = 0x8000
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
SM_CXSCREEN = 0
SM_CYSCREEN = 1

WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_NOREPEAT = 0x4000
VK_F8 = 0x77
BELOW_NORMAL_PRIORITY_CLASS = 0x4000

# Scan codes físicos: o jogo lê a posição da tecla, não a letra
SCAN = {"w": 0x11, "a": 0x1E, "s": 0x1F, "d": 0x20}


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


def _enviar(*eventos):
    lista = (INPUT * len(eventos))(*eventos)
    if user32.SendInput(len(eventos), lista, ctypes.sizeof(INPUT)) != len(eventos):
        raise ctypes.WinError(ctypes.get_last_error())


def _mouse(flags, dx=0, dy=0):
    return INPUT(type=INPUT_MOUSE, u=_Uniao(mi=MOUSEINPUT(dx=dx, dy=dy, dwFlags=flags)))


def _tecla(tecla, solta):
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if solta else 0)
    return INPUT(type=INPUT_KEYBOARD, u=_Uniao(ki=KEYBDINPUT(wScan=SCAN[tecla], dwFlags=flags)))


def mover(x, y):
    """Põe o cursor em (x, y), em pixels do monitor principal."""
    larg = user32.GetSystemMetrics(SM_CXSCREEN)
    alt = user32.GetSystemMetrics(SM_CYSCREEN)
    # no modo absoluto o SendInput usa 0..65535 para cobrir o monitor principal
    nx = round(x * 65535 / max(larg - 1, 1))
    ny = round(y * 65535 / max(alt - 1, 1))
    _enviar(_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, nx, ny))


def clicar(x, y):
    """Leva o mouse até o botão e clica. O Fortnite só aceita o clique depois do hover."""
    mover(x - 12, y - 6)
    time.sleep(0.06)
    mover(x, y)
    time.sleep(0.15)
    _enviar(_mouse(MOUSEEVENTF_LEFTDOWN))
    time.sleep(0.08)
    _enviar(_mouse(MOUSEEVENTF_LEFTUP))


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
        if not user32.RegisterHotKey(None, 1, MOD_NOREPEAT, self.vk):
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
            user32.UnregisterHotKey(None, 1)

    def iniciar(self):
        """Começa a escutar. Devolve o erro se a tecla já estiver em uso por outro programa."""
        self.start()
        self._pronto.wait(2)
        return self.erro

    def encerrar(self):
        if self._id_thread and self.is_alive():
            user32.PostThreadMessageW(self._id_thread, WM_QUIT, 0, 0)
