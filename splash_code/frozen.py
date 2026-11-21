"""
Splash Code Studio - Frozen runtime (SC-037)
PyInstaller ile paketlenince sys.executable UYGULAMANIN KENDISI olur.
Bu modul gercek Python yorumlayicisini ve kaynak yollarini cozer.
"""
import glob
import os
import shutil
import sys

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_PY = None
_PY_SEARCHED = False


def is_frozen():
    return bool(getattr(sys, "frozen", False))


def base_dir():
    if is_frozen():
        return getattr(sys, "_MEIPASS",
                       os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def res(*parts):
    return os.path.join(base_dir(), *parts)


def app_dir():
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return base_dir()


def _self_names():
    n = set()
    try:
        n.add(os.path.basename(sys.executable).lower())
    except Exception:
        pass
    n.add("splashcodestudio.exe")
    n.add("splash.exe")
    return n


def python_exe():
    """Gercek Python yorumlayicisi. Frozen'da ASLA kendi exe'mizi dondurmez."""
    global _PY, _PY_SEARCHED
    if _PY_SEARCHED:
        return _PY or ""
    _PY_SEARCHED = True
    me = _self_names()

    if not is_frozen():
        _PY = sys.executable
        return _PY

    base = getattr(sys, "_base_executable", None)
    if base and os.path.isfile(base):
        if os.path.basename(base).lower() not in me:
            _PY = base
            return _PY

    names = ("python.exe", "python3.exe") if os.name == "nt" else ("python3", "python")
    for nm in names:
        p = shutil.which(nm)
        if p and os.path.basename(p).lower() not in me:
            _PY = os.path.abspath(p)
            return _PY

    if os.name == "nt":
        cands = []
        roots = [os.environ.get("LOCALAPPDATA", ""),
                 os.environ.get("ProgramFiles", ""),
                 os.environ.get("ProgramFiles(x86)", ""), "C:\\"]
        for r in roots:
            if not r:
                continue
            cands += glob.glob(os.path.join(r, "Programs", "Python", "Python3*", "python.exe"))
            cands += glob.glob(os.path.join(r, "Python3*", "python.exe"))
        cands += glob.glob("C:\\Python3*\\python.exe")
        for c in sorted(set(cands), reverse=True):
            if os.path.isfile(c) and os.path.basename(c).lower() not in me:
                _PY = c
                return _PY
    else:
        for c in ("/usr/bin/python3", "/usr/local/bin/python3", "/opt/homebrew/bin/python3"):
            if os.path.isfile(c):
                _PY = c
                return _PY

    _PY = ""
    return ""


def has_python():
    return bool(python_exe())


def py_args(args):
    p = python_exe()
    return ([p] + list(args)) if p else None


def fix_cmd(cmd):
    """Komut listesindeki sys.executable'i gercek python ile degistir."""
    if not cmd:
        return cmd
    out = list(cmd)
    try:
        if out and os.path.basename(str(out[0])).lower() in _self_names():
            p = python_exe()
            if p:
                out[0] = p
            else:
                return None
    except Exception:
        pass
    return out


def subproc_kw(hide=True):
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = NO_WINDOW if hide else 0
    return kw


def env_for_child():
    e = dict(os.environ)
    e["PYTHONUNBUFFERED"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    e.pop("PYTHONHOME", None)
    e.pop("PYTHONPATH", None)
    if is_frozen():
        e.pop("_MEIPASS2", None)
    return e


def report():
    return {
        "frozen": is_frozen(),
        "base": base_dir(),
        "app": app_dir(),
        "python": python_exe(),
        "has_python": has_python(),
        "executable": sys.executable,
    }
