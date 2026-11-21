"""
Splash Code Studio - Split032 (SC-SPLIT-032)
Pasif test alani: _temp_ dosya, ayri calistirma, otomatik temizlik.
Ana dosyaya asla dokunmaz.
"""
import os
import subprocess
import sys
import tempfile
import threading

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
PREFIX = "_temp_"


def js_call(fn, *args):
    try:
        import webview
        if not webview.windows:
            return
        import json as _j
        payload = ",".join(_j.dumps(a, ensure_ascii=False) for a in args)
        webview.windows[0].evaluate_js(
            "if(window.%s)window.%s(%s);" % (fn, fn, payload))
    except Exception:
        pass


def is_temp(name):
    return str(name or "").startswith(PREFIX)


def temp_path(src):
    p = os.path.abspath(str(src))
    return os.path.join(os.path.dirname(p), PREFIX + os.path.basename(p))


def write_temp(src, content):
    try:
        if not src:
            return {"ok": False, "hata": "Kaynak dosya yok"}
        tp = temp_path(src)
        with open(tp, "w", encoding="utf-8", newline="") as f:
            f.write("" if content is None else str(content))
        try:
            from .constants import get_lang
            lang = get_lang(tp)
        except Exception:
            lang = "plaintext"
        return {"ok": True, "path": tp, "name": os.path.basename(tp),
                "dir": os.path.dirname(tp), "lang": lang}
    except Exception as e:
        return {"ok": False, "hata": str(e)}


def delete_temp(path):
    try:
        if path and os.path.isfile(path) and is_temp(os.path.basename(path)):
            os.remove(path)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "hata": str(e)}


def build_cmd(path, cwd):
    ext = os.path.splitext(path)[1].lower()
    q = os.path.abspath(path)
    base = cwd or os.path.dirname(q)
    if ext in (".py", ".pyw"):
        return [sys.executable, "-u", q], []
    if ext in (".js", ".mjs", ".cjs"):
        return ["node", q], []
    if ext in (".ts", ".tsx"):
        return ["npx", "--yes", "tsx", q], []
    if ext == ".sh":
        return ["bash", q], []
    if ext == ".ps1":
        return ["powershell", "-ExecutionPolicy", "Bypass", "-File", q], []
    if ext == ".rb":
        return ["ruby", q], []
    if ext == ".php":
        return ["php", q], []
    if ext == ".lua":
        return ["lua", q], []
    if ext == ".pl":
        return ["perl", q], []
    if ext == ".go":
        return ["go", "run", q], []
    if ext == ".rs":
        man = os.path.join(base, "Cargo.toml")
        if os.path.isfile(man):
            return ["cargo", "run", "--manifest-path", man], []
        exe = os.path.join(tempfile.gettempdir(), "_temp_sc32_rs")
        if os.name == "nt":
            exe += ".exe"
        return ["rustc", q, "-o", exe], [exe]
    return None, []


class Runner:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.temp = None
        self.extras = []

    def busy(self):
        with self.lock:
            return bool(self.proc and self.proc.poll() is None)

    def _clean(self):
        with self.lock:
            tp, ex = self.temp, list(self.extras)
            self.temp, self.extras = None, []
        delete_temp(tp)
        for p in ex:
            try:
                if p and os.path.isfile(p):
                    os.remove(p)
            except Exception:
                pass

    def start(self, src, content, cwd=None):
        if self.busy():
            return {"ok": False, "hata": "Zaten calisan bir test var"}
        w = write_temp(src, content)
        if not w.get("ok"):
            return w
        tp = w["path"]
        base = cwd or w["dir"]
        cmd, extras = build_cmd(tp, base)
        if not cmd:
            delete_temp(tp)
            return {"ok": False,
                    "hata": "Desteklenmeyen uzanti: %s"
                            % os.path.splitext(tp)[1]}
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | NO_WINDOW)
        else:
            kw["start_new_session"] = True
        try:
            p = subprocess.Popen(
                cmd, cwd=base, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                bufsize=-1, env=env, **kw)
        except Exception as e:
            delete_temp(tp)
            return {"ok": False, "hata": str(e)}
        with self.lock:
            self.proc = p
            self.temp = tp
            self.extras = extras
        threading.Thread(target=self._pump, args=(p,),
                         name="sc32-run", daemon=True).start()
        return {"ok": True, "cmd": " ".join(str(c) for c in cmd),
                "temp": tp, "name": w["name"]}

    def _pump(self, p):
        try:
            while True:
                b = p.stdout.read1(65536)
                if not b:
                    break
                js_call("scSplitOut32", b.decode("utf-8", "replace"))
        except Exception:
            pass
        rc = None
        try:
            rc = p.wait(timeout=5)
        except Exception:
            pass
        with self.lock:
            if self.proc is p:
                self.proc = None
        self._clean()
        js_call("scSplitDone32", rc)

    def stop(self):
        with self.lock:
            p = self.proc
        if not p or p.poll() is not None:
            with self.lock:
                self.proc = None
            self._clean()
            return {"ok": True}
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                    capture_output=True, timeout=8,
                    creationflags=NO_WINDOW)
            else:
                import signal
                try:
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                except Exception:
                    p.terminate()
            try:
                p.wait(timeout=3)
            except Exception:
                p.kill()
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
        with self.lock:
            self.proc = None
        self._clean()
        js_call("scSplitDone32", -1)
        return {"ok": True}


RUN = Runner()
