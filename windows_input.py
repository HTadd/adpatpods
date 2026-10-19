"""Windows user32 bindings. Imported on non-Windows for tests; not instantiated."""
import ctypes as C
import sys

LONG = C.c_int32
DWORD = C.c_uint32
WORD = C.c_uint16
ULONG_PTR = C.c_size_t

class MOUSEINPUT(C.Structure):
    _fields_ = [('dx', LONG), ('dy', LONG), ('mouseData', DWORD),
                ('dwFlags', DWORD), ('time', DWORD), ('dwExtraInfo', ULONG_PTR)]
class KEYBDINPUT(C.Structure):
    _fields_ = [('wVk', WORD), ('wScan', WORD), ('dwFlags', DWORD),
                ('time', DWORD), ('dwExtraInfo', ULONG_PTR)]
class HARDWAREINPUT(C.Structure):
    _fields_ = [('uMsg', DWORD), ('wParamL', WORD), ('wParamH', WORD)]
class INPUTUNION(C.Union):
    _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT), ('hi', HARDWAREINPUT)]
class INPUT(C.Structure):
    _anonymous_ = ('u',)
    _fields_ = [('type', DWORD), ('u', INPUTUNION)]

class WindowsMouse:
    def __init__(self):
        if sys.platform != 'win32':
            raise RuntimeError('Desktop control requires Windows')
        self.api = C.WinDLL('user32', use_last_error=True)
        self.api.SetCursorPos.argtypes = [C.c_int, C.c_int]
        self.api.SetCursorPos.restype = C.c_int
        self.api.GetAsyncKeyState.argtypes = [C.c_int]
        self.api.GetAsyncKeyState.restype = C.c_int16
        self.api.SendInput.argtypes = [C.c_uint, C.POINTER(INPUT), C.c_int]
        self.api.SendInput.restype = C.c_uint
        try:
            self.api.SetProcessDpiAwarenessContext(C.c_void_p(-4))
        except AttributeError:
            self.api.SetProcessDPIAware()

    def bounds(self):
        # Virtual desktop, including monitors left of primary.
        return tuple(self.api.GetSystemMetrics(i) for i in (76, 77, 78, 79))

    def move(self, x, y):
        if not self.api.SetCursorPos(x, y):
            raise C.WinError(C.get_last_error())

    def click(self):
        events = (INPUT * 2)()
        events[0].mi.dwFlags = 0x0002  # LEFTDOWN
        events[1].mi.dwFlags = 0x0004  # LEFTUP
        if self.api.SendInput(2, events, C.sizeof(INPUT)) != 2:
            # Best-effort release if a partial send occurred.
            release = INPUT()
            release.mi.dwFlags = 0x0004
            self.api.SendInput(1, C.byref(release), C.sizeof(INPUT))
            raise RuntimeError('Windows rejected mouse input; check desktop/integrity level')

    def key_down(self, vk):
        return bool(self.api.GetAsyncKeyState(vk) & 0x8000)
