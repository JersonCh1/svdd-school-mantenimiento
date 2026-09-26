"""Conductor de GUI para verificar la app real de S.V.D.D. School (solo Windows).

Ejecuta la app DENTRO de este mismo proceso con un 'escenario' que corre en el
event loop: encuentra widgets por texto, invoca botones, escribe en los campos,
opera los diálogos nativos (messagebox, abrir archivo) y toma capturas.

Reglas aprendidas:
  - Las capturas se hacen por ventana con PrintWindow, nunca copiando la
    pantalla: así no aparece nada más del escritorio.
  - Nunca se simula el teclado del sistema (SendInput/keybd_event): si la
    ventana no queda en primer plano, las teclas van a otra aplicación.
"""
import ctypes
import os
import sys
import time
import tkinter as tk
from tkinter import messagebox


ctypes.windll.shcore.SetProcessDpiAwareness(2)
user32 = ctypes.windll.user32

LOG = []


def log(*a):
    msg = " ".join(str(x) for x in a)
    LOG.append(msg)
    print(msg, flush=True)


def walk(w):
    yield w
    for c in w.winfo_children():
        yield from walk(c)


def toplevels(root):
    return [w for w in walk(root) if isinstance(w, (tk.Tk, tk.Toplevel)) and w.winfo_exists()]


def visibles(root):
    return [w for w in toplevels(root) if w.winfo_viewable()]


def find(container, cls=None, text=None, contains=None):
    out = []
    for w in walk(container):
        if cls and not isinstance(w, cls):
            continue
        try:
            t = w.cget("text")
        except tk.TclError:
            t = None
        if text is not None and t != text:
            continue
        if contains is not None and (t is None or contains not in str(t)):
            continue
        out.append(w)
    return out


def pump(root, secs=0.3):
    end = time.time() + secs
    while time.time() < end:
        root.update()
        time.sleep(0.02)


def rect_of(hwnd):
    r = (ctypes.c_long * 4)()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return tuple(r)


def _print_window(hwnd):
    """Imagen de UNA ventana (aunque esté tapada por otras), vía PrintWindow."""
    from PIL import Image
    gdi32 = ctypes.windll.gdi32
    x0, y0, x1, y1 = rect_of(hwnd)
    w, h = x1 - x0, y1 - y0
    hdc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)  # PW_RENDERFULLCONTENT
    class BIH(ctypes.Structure):
        _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                    ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                    ("biSizeImage", ctypes.c_uint32), ("a", ctypes.c_int32), ("b", ctypes.c_int32),
                    ("c", ctypes.c_uint32), ("d", ctypes.c_uint32)]
    bih = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bih), 0)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(hwnd, hdc)
    return Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB"), (x0, y0)


def shot(path, windows=(), hwnds=()):
    """Compone SOLO las ventanas de la app (y sus diálogos) sobre fondo neutro.
    Nunca copia la pantalla: así no aparece nada más del escritorio."""
    from PIL import Image
    hs = []
    for w in windows:
        w.update()
        hs.append(user32.GetParent(w.winfo_id()) or w.winfo_id())
    hs += list(hwnds)
    time.sleep(0.25)
    capas = [_print_window(h) for h in hs]
    x0 = min(p[0] for _, p in capas); y0 = min(p[1] for _, p in capas)
    x1 = max(p[0] + im.width for im, p in capas); y1 = max(p[1] + im.height for im, p in capas)
    lienzo = Image.new("RGB", (x1 - x0, y1 - y0), (34, 44, 58))
    for im, (x, y) in capas:
        lienzo.paste(im, (x - x0, y - y0))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lienzo.save(path)
    log("captura:", path, lienzo.size)


def while_dialog(root, action, on_dialog, timeout=5):
    """Ejecuta action() (que abre un messagebox modal); cuando el diálogo aparece,
    llama on_dialog(hwnd, titulo, texto) y luego lo cierra con Enter."""
    state = {}

    def poll():
        h = user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(h, buf, 256)
        if buf.value == "#32770":  # clase Win32 de los cuadros de diálogo
            t = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, t, 256)
            texto = dialog_text(h)
            state["seen"] = (t.value, texto)
            try:
                on_dialog(h, t.value, texto)
            finally:
                user32.PostMessageW(h, 0x0010, 0, 0)  # WM_CLOSE
            return
        if time.time() - state["t0"] < timeout:
            root.after(100, poll)

    state["t0"] = time.time()
    root.after(300, poll)
    action()
    return state.get("seen")


def dialog_text(hwnd):
    textos = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, _):
        cls = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(h, cls, 64)
        if cls.value == "Static":
            b = ctypes.create_unicode_buffer(1024)
            user32.GetWindowTextW(h, b, 1024)
            if b.value:
                textos.append(b.value)
        return True

    user32.EnumChildWindows(hwnd, cb, 0)
    return " | ".join(textos)


def run(script, scenario, nested_mainloop_noop=True):
    """Ejecuta el script de la app; el escenario corre al entrar al mainloop raíz."""
    real = tk.Misc.mainloop
    st = {"depth": 0}

    def fake(self, n=0):
        st["depth"] += 1
        if st["depth"] == 1:
            root = self._root()

            def go():
                try:
                    scenario(root, g)
                except Exception:
                    import traceback
                    traceback.print_exc()
                finally:
                    root.after(50, root.destroy)

            root.after(200, go)
            real(self, n)
        else:
            log(f"(mainloop anidado nº {st['depth'] - 1})")
            if not nested_mainloop_noop:
                real(self, n)

    tk.Misc.mainloop = fake
    sys.argv = [script]
    g = {"__name__": "__main__", "__file__": script}
    os.chdir(os.path.dirname(os.path.abspath(script)))
    sys.path.insert(0, os.getcwd())
    exec(compile(open(script, encoding="utf-8").read(), script, "exec"), g)
    return g, st


def descendants(hwnd, cls):
    out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, _):
        b = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(h, b, 64)
        if b.value == cls and user32.IsWindowVisible(h):
            out.append(h)
        return True

    user32.EnumChildWindows(hwnd, cb, 0)
    return out


def pick_file(path):
    """Handler para el diálogo nativo de abrir archivo: escribe la ruta y pulsa Abrir."""
    def h(hwnd, titulo, texto):
        edits = descendants(hwnd, "Edit")
        user32.SendMessageW(edits[0], 0x000C, 0, ctypes.c_wchar_p(path))  # WM_SETTEXT
        time.sleep(0.2)
        user32.SendMessageW(hwnd, 0x0111, 1, 0)  # WM_COMMAND IDOK
        return "handled"
    return h


def our_dialogs():
    pid = os.getpid(); out = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, _):
        p = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        b = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(h, b, 64)
        if p.value == pid and b.value == "#32770" and user32.IsWindowVisible(h):
            out.append(h)
        return True

    user32.EnumWindows(cb, 0)
    return out


def with_dialogs(root, action, handlers, timeout=8):
    """Como while_dialog, pero atiende varios diálogos sucesivos (p. ej. selector
    de archivo y luego un messagebox). Cada handler(hwnd, titulo, texto) puede
    devolver 'handled' si ya cerró el diálogo."""
    vistos = []
    st = {"t0": time.time(), "i": 0, "last": None}

    def poll():
        nuevos = [d for d in our_dialogs() if d != st["last"]]
        h = nuevos[0] if nuevos else None
        if h and st["i"] < len(handlers):
            st["last"] = h
            t = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(h, t, 256)
            texto = dialog_text(h)
            vistos.append((t.value, texto))
            try:
                r = handlers[st["i"]](h, t.value, texto)
            except Exception as e:
                log("handler falló:", repr(e)); r = None
            st["i"] += 1
            if r != "handled":
                user32.PostMessageW(h, 0x0010, 0, 0)
        if st["i"] < len(handlers) and time.time() - st["t0"] < timeout:
            root.after(150, poll)

    root.after(300, poll)
    action()
    pump(root, 0.5)
    return vistos
