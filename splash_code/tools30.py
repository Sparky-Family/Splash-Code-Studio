"""
Splash Code Studio - Tools30 (SC-TOOLS-030)
Pasif split test dosyasi, pdb debug oturumu, saglam sorun taramasi.
"""
import json
import os
import re
import subprocess
import sys
import threading

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
TEMP_PREFIX = "_temp_"


def js_call(fn, *args):
    try:
        import webview
        if not webview.windows:
            return
        payload = ",".join(json.dumps(a, ensure_ascii=False) for a in args)
        webview.windows[0].evaluate_js(
            "if(window.%s)window.%s(%s);" % (fn, fn, payload))
    except Exception:
        pass


def is_temp_name(name):
    return str(name or "").startswith(TEMP_PREFIX)


def temp_path_for(path):
    p = os.path.abspath(str(path))
    return os.path.join(os.path.dirname(p), TEMP_PREFIX + os.path.basename(p))


def temp_write(path, content):
    try:
        if not path:
            return {"ok": False, "hata": "Dosya yok"}
        tp = temp_path_for(path)
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


def temp_delete(path):
    try:
        if path and os.path.isfile(path):
            os.remove(path)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "hata": str(e)}


def temp_cleanup(folder):
    n = 0
    try:
        if folder and os.path.isdir(folder):
            for name in os.listdir(folder):
                if is_temp_name(name):
                    try:
                        os.remove(os.path.join(folder, name))
                        n += 1
                    except Exception:
                        pass
    except Exception:
        pass
    return {"ok": True, "removed": n}


# ── Sorun taramasi ───────────────────────────────────────────
def _scan_brackets(text):
    pairs = {")": "(", "]": "[", "}": "{"}
    opens = set("([{")
    stack = []
    errs = []
    line, col = 0, 0
    i, n = 0, len(text)
    quote = None
    while i < n:
        ch = text[i]
        if ch == "\n":
            line += 1
            col = 0
            quote = None
            i += 1
            continue
        if quote:
            if ch == "\\":
                i += 2
                col += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            col += 1
            continue
        if ch in ("'", '"', "`"):
            quote = ch
            i += 1
            col += 1
            continue
        if ch == "#" or text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            col += j - i
            i = j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            seg = text[i:j]
            line += seg.count("\n")
            i = j
            continue
        if ch in opens:
            stack.append((ch, line, col))
        elif ch in pairs:
            if stack and stack[-1][0] == pairs[ch]:
                stack.pop()
            else:
                errs.append({"severity": 1, "line": line, "col": col,
                             "message": "Beklenmeyen '%s'" % ch,
                             "source": "bracket"})
        i += 1
        col += 1
    for ch, ln, cl in stack:
        errs.append({"severity": 1, "line": ln, "col": cl,
                     "message": "Kapatilmamis '%s'" % ch,
                     "source": "bracket"})
    return errs


def local_problems(path, lang, text):
    out = []
    if not text:
        return out
    p = (path or "").lower()
    if lang == "python" or p.endswith(".py"):
        try:
            compile(text, path or "<editor>", "exec")
        except SyntaxError as e:
            out.append({"severity": 1, "line": (e.lineno or 1) - 1,
                        "col": (e.offset or 1) - 1,
                        "message": e.msg or "Sozdizimi hatasi",
                        "source": "python"})
        except Exception as e:
            out.append({"severity": 1, "line": 0, "col": 0,
                        "message": str(e), "source": "python"})
    elif lang == "json" or p.endswith(".json"):
        try:
            json.loads(text)
        except Exception as e:
            ln = getattr(e, "lineno", 1) - 1
            cl = getattr(e, "colno", 1) - 1
            out.append({"severity": 1, "line": max(0, ln),
                        "col": max(0, cl), "message": str(e),
                        "source": "json"})
    if lang not in ("plaintext", "markdown"):
        out.extend(_scan_brackets(text)[:20])
    return out


def merge_problems(lsp_items, lint_issues, local_items):
    out, seen = [], set()

    def push(sev, line, col, msg, src):
        msg = str(msg or "").strip()
        if not msg:
            return
        key = (int(sev), int(line), msg[:120])
        if key in seen:
            return
        seen.add(key)
        out.append({"severity": int(sev), "line": max(0, int(line)),
                    "col": max(0, int(col)), "message": msg[:400],
                    "source": src})

    for d in (lsp_items or []):
        rg = (d.get("range") or {}).get("start") or {}
        push(d.get("severity", 1), rg.get("line", 0),
             rg.get("character", 0), d.get("message", ""), "lsp")
    for i in (lint_issues or []):
        sev = {"error": 1, "warning": 2, "info": 3}.get(i.get("severity"), 2)
        push(sev, int(i.get("line", 1)) - 1, 0, i.get("msg", ""), "lint")
    for i in (local_items or []):
        push(i.get("severity", 1), i.get("line", 0), i.get("col", 0),
             i.get("message", ""), i.get("source", "local"))
    out.sort(key=lambda x: (x["severity"], x["line"], x["col"]))
    return out[:300]


# ── Debug (pdb) ──────────────────────────────────────────────
class DebugRunner:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()
        self.file = None

    def busy(self):
        with self.lock:
            return bool(self.proc and self.proc.poll() is None)

    def start(self, path, cwd=None):
        if not path or not os.path.isfile(path):
            return {"ok": False, "hata": "Dosya bulunamadi"}
        if os.path.splitext(path)[1].lower() not in (".py", ".pyw"):
            return {"ok": False, "hata": "Simdilik sadece Python"}
        if self.busy():
            self.stop()
        cwd = cwd or os.path.dirname(path) or os.getcwd()
        cmd = [sys.executable, "-u", "-m", "pdb", os.path.abspath(path)]
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | NO_WINDOW
        else:
            kw["start_new_session"] = True
        try:
            p = subprocess.Popen(
                cmd, cwd=cwd, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                bufsize=-1, env=env, **kw)
        except Exception as e:
            return {"ok": False, "hata": str(e)}
        with self.lock:
            self.proc = p
            self.file = path
        threading.Thread(target=self._pump, args=(p,), daemon=True).start()
        return {"ok": True, "pid": p.pid, "file": path,
                "cmd": " ".join(cmd)}

    def _pump(self, p):
        try:
            while True:
                b = p.stdout.read1(65536)
                if not b:
                    break
                js_call("scDebugOut", b.decode("utf-8", "replace"))
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
        js_call("scDebugDone", rc)

    def send(self, text):
        with self.lock:
            p = self.proc
        if not p or p.poll() is not None:
            return {"ok": False, "hata": "Debug oturumu yok"}
        try:
            s = "" if text is None else str(text)
            if not s.endswith("\n"):
                s += "\n"
            p.stdin.write(s.encode("utf-8", "replace"))
            p.stdin.flush()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def stop(self):
        with self.lock:
            p = self.proc
        if not p or p.poll() is not None:
            with self.lock:
                self.proc = None
            return {"ok": True}
        try:
            try:
                p.stdin.write(b"q\n")
                p.stdin.flush()
            except Exception:
                pass
            if os.name == "nt":
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
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
        return {"ok": True}


DEBUG = DebugRunner()
