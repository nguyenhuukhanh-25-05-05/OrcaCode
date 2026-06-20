"""Utility functions for clipboard and formatting."""


def _format_duration(seconds: float) -> str:
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    else:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m{secs}s"


def get_clipboard_text() -> str:
    import sys
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        import time
        
        OpenClipboard = ctypes.windll.user32.OpenClipboard
        OpenClipboard.argtypes = [wintypes.HWND]
        OpenClipboard.restype = wintypes.BOOL
        
        CloseClipboard = ctypes.windll.user32.CloseClipboard
        CloseClipboard.argtypes = []
        CloseClipboard.restype = wintypes.BOOL
        
        GetClipboardData = ctypes.windll.user32.GetClipboardData
        GetClipboardData.argtypes = [wintypes.UINT]
        GetClipboardData.restype = wintypes.HANDLE
        
        IsClipboardFormatAvailable = ctypes.windll.user32.IsClipboardFormatAvailable
        IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        IsClipboardFormatAvailable.restype = wintypes.BOOL
        
        GlobalLock = ctypes.windll.kernel32.GlobalLock
        GlobalLock.argtypes = [wintypes.HANDLE]
        GlobalLock.restype = ctypes.c_void_p
        
        GlobalUnlock = ctypes.windll.kernel32.GlobalUnlock
        GlobalUnlock.argtypes = [wintypes.HANDLE]
        GlobalUnlock.restype = wintypes.BOOL
        
        CF_UNICODETEXT = 13
        
        opened = False
        for _ in range(10):
            if OpenClipboard(None):
                opened = True
                break
            time.sleep(0.01)
            
        if not opened:
            return ""
        try:
            if not IsClipboardFormatAvailable(CF_UNICODETEXT):
                return ""
            h_clip_mem = GetClipboardData(CF_UNICODETEXT)
            if not h_clip_mem:
                return ""
            p_clip_mem = GlobalLock(h_clip_mem)
            if not p_clip_mem:
                return ""
            try:
                text = ctypes.wstring_at(p_clip_mem)
                return text
            finally:
                GlobalUnlock(h_clip_mem)
        except Exception:
            pass
        finally:
            CloseClipboard()
            
    try:
        import pyperclip
        return pyperclip.paste()
    except Exception:
        if sys.platform == "darwin":
            try:
                import subprocess
                return subprocess.check_output(["pbpaste"], text=True)
            except Exception:
                pass
        elif sys.platform.startswith("linux"):
            try:
                import subprocess
                return subprocess.check_output(["xclip", "-selection", "clipboard", "-o"], text=True)
            except Exception:
                try:
                    return subprocess.check_output(["xsel", "-clipboard", "-o"], text=True)
                except Exception:
                    pass
    return ""


def set_clipboard_text(text: str) -> bool:
    import sys
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        import time
        
        OpenClipboard = ctypes.windll.user32.OpenClipboard
        OpenClipboard.argtypes = [wintypes.HWND]
        OpenClipboard.restype = wintypes.BOOL
        
        EmptyClipboard = ctypes.windll.user32.EmptyClipboard
        EmptyClipboard.argtypes = []
        EmptyClipboard.restype = wintypes.BOOL
        
        CloseClipboard = ctypes.windll.user32.CloseClipboard
        CloseClipboard.argtypes = []
        CloseClipboard.restype = wintypes.BOOL
        
        SetClipboardData = ctypes.windll.user32.SetClipboardData
        SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        SetClipboardData.restype = wintypes.HANDLE
        
        GlobalAlloc = ctypes.windll.kernel32.GlobalAlloc
        GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        GlobalAlloc.restype = wintypes.HANDLE
        
        GlobalLock = ctypes.windll.kernel32.GlobalLock
        GlobalLock.argtypes = [wintypes.HANDLE]
        GlobalLock.restype = ctypes.c_void_p
        
        GlobalUnlock = ctypes.windll.kernel32.GlobalUnlock
        GlobalUnlock.argtypes = [wintypes.HANDLE]
        GlobalUnlock.restype = wintypes.BOOL
        
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        
        opened = False
        for _ in range(10):
            if OpenClipboard(None):
                opened = True
                break
            time.sleep(0.01)
            
        if not opened:
            return False
        try:
            EmptyClipboard()
            data = text.encode("utf-16-le") + b"\x00\x00"
            h_clip_mem = GlobalAlloc(GMEM_MOVEABLE, len(data))
            if not h_clip_mem:
                return False
            p_clip_mem = GlobalLock(h_clip_mem)
            if not p_clip_mem:
                GlobalFree = ctypes.windll.kernel32.GlobalFree
                GlobalFree.argtypes = [wintypes.HANDLE]
                GlobalFree.restype = wintypes.HANDLE
                GlobalFree(h_clip_mem)
                return False
            try:
                ctypes.memmove(p_clip_mem, data, len(data))
            finally:
                GlobalUnlock(h_clip_mem)
            result = SetClipboardData(CF_UNICODETEXT, h_clip_mem)
            if not result:
                GlobalFree = ctypes.windll.kernel32.GlobalFree
                GlobalFree.argtypes = [wintypes.HANDLE]
                GlobalFree.restype = wintypes.HANDLE
                GlobalFree(h_clip_mem)
                return False
            return True
        except Exception:
            pass
        finally:
            CloseClipboard()
        
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        if sys.platform == "darwin":
            try:
                import subprocess
                p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, text=True)
                p.communicate(text)
                return True
            except Exception:
                pass
        elif sys.platform.startswith("linux"):
            try:
                import subprocess
                p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE, text=True)
                p.communicate(text)
                return True
            except Exception:
                try:
                    p = subprocess.Popen(["xsel", "-clipboard", "-i"], stdin=subprocess.PIPE, text=True)
                    p.communicate(text)
                    return True
                except Exception:
                    pass
    return False
