"""
Splash Code Studio - Araçlar (SC-TOOLS-029)
TODO deposu, sorun tarama, referans fallback, test çalıştırıcı.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid

from .constants import SETTINGS_DIR

SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", "venv", ".venv", "dist",
    "build", ".next", "target", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "site-packages", ".idea", ".vscode", ".cache",
}
TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK|NOTE)\b[:\s]*(.*)")
NO_WINDOW = 0x08000000 if os.name == "nt" else 0


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


def _todos_file():
    return os.path.join(SETTINGS_DIR, "todos.json")


def load_todos():
    try:
        with open(_todos_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_todos(items):
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        tmp = _todos_file() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(items or [], f, indent=2, ensure_ascii=False)
        os.replace(tmp, _todos_file())
        return True
    except Exception:
        return False


def add_todo(text, cwd=None):
    text = (text or "").strip()
    if not text:
        return {"ok": False, "hata": "Boş görev"}
    items = load_todos()
    item = {
        "id": uuid.uuid4().hex[:12],
        "text": text[:500],
        "done": False,
        "cwd": cwd or "",
        "ts": time.time(),
    }
    items.insert(0, item)
    save_todos(items[:500])
    return {"ok": True, "item": item}


def toggle_todo(tid):
    items = load_todos()
    for it in items:
        if it.get("id") == tid:
            it["done"] = not it.get("done")
            save_todos(items)
            return {"ok": True, "item": it}
    return {"ok": False, "hata": "Bulunamadı"}


def delete_todo(tid):
    items = load_todos()
    n = len(items)
    items = [x for x in items if x.get("id") != tid]
    save_todos(items)
    return {"ok": len(items) != n}


def _iter_files(root, max_size=2 * 1024 * 1024):
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in fns:
            p = os.path.join(dp, fn)
            try:
                if os.path.getsize(p) > max_size:
                    continue
                with open(p, "rb") as f:
                    if b"\x00" in f.read(2048):
                        continue
            except Exception:
                continue
            yield p


def scan_project_todos(cwd, limit=300):
    out = []
    if not cwd or not os.path.isdir(cwd):
        return out
    for p in _iter_files(cwd):
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                for i, ln in enumerate(f, 1):
                    m = TODO_RE.search(ln)
                    if m:
                        out.append({
                            "tag": m.group(1), "path": p, "line": i,
                            "text": (m.group(2) or ln.strip())[:200],
                        })
                        if len(out) >= limit:
                            return out
        except Exception:
            continue
    return out


def list_todos(cwd=None, include_project=True):
    items = load_todos()
    if cwd:
        items = [x for x in items if not x.get("cwd") or x.get("cwd") == cwd]
    proj = scan_project_todos(cwd) if include_project else []
    return {"ok": True, "items": items, "project": proj}


def local_problems(path, lang, text):
    issues = []
    if not text:
        return issues
    if lang == "python" or (path or "").endswith(".py"):
        try:
            compile(text, path or "<editor>", "exec")
        except SyntaxError as e:
            issues.append({
                "severity": 1, "line": (e.lineno or 1) - 1,
                "col": (e.offset or 1) - 1,
                "message": e.msg or "Sözdizimi hatası",
                "source": "python",
            })
    elif lang == "json" or (path or "").endswith(".json"):
        try:
            json.loads(text)
        except Exception as e:
            line = getattr(e, "lineno", 1) - 1
            col = getattr(e, "colno", 1) - 1
            issues.append({
                "severity": 1, "line": max(0, line), "col": max(0, col),
                "message": str(e), "source": "json",
            })
    return issues


def normalize_problems(lsp_items, lint_issues, local_issues):
    out = []
    seen = set()

    def push(sev, line, col, msg, source):
        msg = str(msg or "").strip()
        if not msg:
            return
        key = (int(sev), int(line), msg[:120])
        if key in seen:
            return
        seen.add(key)
        out.append({
            "severity": int(sev), "line": int(line), "col": int(col),
            "message": msg[:400], "source": source,
        })

    for d in (lsp_items or []):
        r = (d.get("range") or {}).get("start") or {}
        push(d.get("severity", 1), r.get("line", 0),
             r.get("character", 0), d.get("message", ""), "lsp")
    for i in (lint_issues or []):
        sev = {"error": 1, "warning": 2, "info": 3}.get(
            i.get("severity"), 2)
        push(sev, max(0, int(i.get("line", 1)) - 1), 0,
             i.get("msg", ""), "lint")
    for i in (local_issues or []):
        push(i.get("severity", 1), i.get("line", 0),
             i.get("col", 0), i.get("message", ""), i.get("source", "local"))
    out.sort(key=lambda x: (x["severity"], x["line"], x["col"]))
    return out[:300]


def word_at(text, line, col):
    lines = (text or "").split("\n")
    if line < 0 or line >= len(lines):
        return ""
    ln = lines[line]
    if col < 0:
        col = 0
    if col > len(ln):
        col = len(ln)
    left = col
    right = col
    while left > 0 and re.match(r"[A-Za-z0-9_]", ln[left - 1]):
        left -= 1
    while right < len(ln) and re.match(r"[A-Za-z0-9_]", ln[right]):
        right += 1
    return ln[left:right]


def find_word_refs(cwd, word, limit=200):
    out = []
    if not cwd or not word:
        return out
    pat = re.compile(r"\b" + re.escape(word) + r"\b")
    for p in _iter_files(cwd):
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                for i, ln in enumerate(f, 1):
                    m = pat.search(ln)
                    if m:
                        out.append({
                            "path": p, "line": i, "col": m.start(),
                            "text": ln.rstrip()[:240],
                        })
                        if len(out) >= limit:
                            return out
        except Exception:
            continue
    return out


class TestRunner:
    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()

    def busy(self):
        with self.lock:
            return bool(self.proc and self.proc.poll() is None)

    def detect(self, cwd):
        cwd = cwd or os.getcwd()
        pj = os.path.join(cwd, "package.json")
        if os.path.isfile(pj):
            try:
                with open(pj, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if (data.get("scripts") or {}).get("test"):
                    return ["npm", "test", "--silent"]
            except Exception:
                pass
        if os.path.isfile(os.path.join(cwd, "go.mod")):
            return ["go", "test", "./..."]
        if os.path.isfile(os.path.join(cwd, "Cargo.toml")):
            return ["cargo", "test"]
        has_pytest = any(
            os.path.exists(os.path.join(cwd, x))
            for x in ("pytest.ini", "pyproject.toml", "setup.cfg", "tests", "test"))
        if has_pytest:
            try:
                import pytest  # noqa
                return [sys.executable, "-m", "pytest", "-q"]
            except Exception:
                pass
        return [sys.executable, "-m", "unittest", "discover", "-v"]

    def start(self, cwd):
        if self.busy():
            return {"ok": False, "hata": "Zaten çalışan test var"}
        cwd = cwd or os.getcwd()
        cmd = self.detect(cwd)
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
                cmd, cwd=cwd, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                bufsize=-1, env=env, **kw)
        except Exception as e:
            return {"ok": False, "hata": str(e)}
        with self.lock:
            self.proc = p
        threading.Thread(target=self._pump, args=(p,), daemon=True).start()
        return {"ok": True, "cmd": " ".join(cmd), "pid": p.pid}

    def _pump(self, p):
        try:
            while True:
                b = p.stdout.read1(65536)
                if not b:
                    break
                js_call("scTestOut", b.decode("utf-8", "replace"))
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
        js_call("scTestDone", rc)

    def stop(self):
        with self.lock:
            p = self.proc
        if not p or p.poll() is not None:
            return {"ok": False, "hata": "Çalışan test yok"}
        try:
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


TESTS = TestRunner()
