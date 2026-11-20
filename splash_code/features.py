"""
Splash Code Studio - Studio Features (SC-STUDIO-008)
Interaktif run/stdin, dosya watcher, .gitignore arama, AI streaming,
font yerellestirme, studio ayar kaliciligi.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", "venv", ".venv", "dist",
    "build", ".next", "target", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "site-packages", ".idea", ".vscode", ".cache",
    "bower_components", ".turbo", ".parcel-cache",
}
FONT_CSS = (
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
    "&family=JetBrains+Mono:wght@400;500;600&display=swap"
)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


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


def pkg_dir():
    return os.path.dirname(os.path.abspath(__file__))


def studio_file():
    from .constants import SETTINGS_DIR
    return os.path.join(SETTINGS_DIR, "studio.json")


def load_studio():
    try:
        with open(studio_file(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_studio(d):
    try:
        os.makedirs(os.path.dirname(studio_file()), exist_ok=True)
        tmp = studio_file() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d or {}, f, indent=2, ensure_ascii=False)
        os.replace(tmp, studio_file())
        return True
    except Exception:
        return False


# ── Calistirma + stdin ────────────────────────────────────────────────
def build_run_cmd(path, cwd):
    ext = os.path.splitext(path or "")[1].lower()
    q = os.path.abspath(path) if path else ""
    if ext in (".py", ".pyw"):
        return [sys.executable, "-u", q]
    if ext in (".js", ".mjs", ".cjs"):
        return ["node", q]
    if ext in (".ts", ".tsx"):
        return ["npx", "--yes", "tsx", q]
    if ext == ".sh":
        return ["bash", q]
    if ext == ".ps1":
        return ["powershell", "-ExecutionPolicy", "Bypass", "-File", q]
    if ext == ".rb":
        return ["ruby", q]
    if ext == ".php":
        return ["php", q]
    if ext == ".lua":
        return ["lua", q]
    if ext == ".pl":
        return ["perl", q]
    if ext == ".go":
        return ["go", "run", q]
    if ext == ".rs":
        man = os.path.join(cwd or os.path.dirname(q), "Cargo.toml")
        if os.path.isfile(man):
            return ["cargo", "run", "--manifest-path", man]
        return ["rustc", q, "-o", os.path.join(tempfile.gettempdir(), "sc_rs")]
    return None


class RunManager:
    """Tek calisan surec; stdin PIPE, stdout anlik akar."""

    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()

    def busy(self):
        with self.lock:
            return bool(self.proc and self.proc.poll() is None)

    def start(self, cmd, cwd):
        if self.busy():
            return {"ok": False, "hata": "Zaten calisan bir surec var"}
        env = dict(os.environ)
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env.setdefault("TERM", "xterm-256color")
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | NO_WINDOW)
        else:
            kw["start_new_session"] = True
        try:
            p = subprocess.Popen(
                cmd, cwd=cwd or None, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                bufsize=-1, env=env, **kw)
        except Exception as ex:
            return {"ok": False, "hata": str(ex)}
        with self.lock:
            self.proc = p
        threading.Thread(target=self._pump, args=(p,),
                         name="sc-run", daemon=True).start()
        return {"ok": True, "pid": p.pid}

    def _pump(self, p):
        try:
            while True:
                b = p.stdout.read1(65536)
                if not b:
                    break
                js_call("scRunOut", b.decode("utf-8", "replace"))
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
        js_call("scRunDone", rc)

    def send(self, data):
        with self.lock:
            p = self.proc
        if not p or p.poll() is not None:
            return {"ok": False, "hata": "Calisan surec yok"}
        try:
            s = data if isinstance(data, str) else str(data)
            p.stdin.write(s.encode("utf-8", "replace"))
            p.stdin.flush()
            return {"ok": True}
        except Exception as ex:
            return {"ok": False, "hata": str(ex)}

    def stop(self):
        with self.lock:
            p = self.proc
        if not p or p.poll() is not None:
            return {"ok": False, "hata": "Calisan surec yok"}
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
        return {"ok": True}


RUN = RunManager()


# ── Dosya Watcher ─────────────────────────────────────────────────────
class Watcher:
    def __init__(self):
        self._snap = None
        self._lock = threading.Lock()

    def poll(self, cwd, paths, dirs):
        files = {}
        listing = {}
        watched = []
        for p in (paths or []):
            if not p:
                continue
            ap = os.path.abspath(p)
            watched.append(ap)
            try:
                st = os.stat(ap)
                files[ap] = [round(st.st_mtime, 3), st.st_size]
            except Exception:
                files[ap] = None
        targets = ([cwd] if cwd else []) + list(dirs or [])
        seen = set()
        for d in targets:
            if not d:
                continue
            ad = os.path.abspath(d)
            if ad in seen or not os.path.isdir(ad):
                continue
            seen.add(ad)
            names = []
            try:
                for e in os.scandir(ad):
                    if e.name in SKIP_DIRS:
                        continue
                    names.append(e.name)
                names.sort()
            except Exception:
                pass
            listing[ad] = names
        cur = {"f": files, "d": listing}
        with self._lock:
            prev = self._snap
            self._snap = cur
        if prev is None:
            return {"ok": True, "init": True, "changed": [],
                    "deleted": [], "tree": []}
        pf = prev.get("f", {})
        changed, deleted = [], []
        for ap in watched:
            now = files.get(ap)
            before = pf.get(ap)
            if now is None and before is not None:
                deleted.append(ap)
            elif now is not None and before is not None and now != before:
                changed.append(ap)
        tree = []
        pd = prev.get("d", {})
        for d, names in listing.items():
            if d in pd and pd[d] != names:
                tree.append(d)
        return {"ok": True, "init": False, "changed": changed,
                "deleted": deleted, "tree": tree}

    def reset(self):
        with self._lock:
            self._snap = None


WATCH = Watcher()


# ── .gitignore ────────────────────────────────────────────────────────
class GitIgnore:
    def __init__(self, root):
        self.root = os.path.abspath(root or ".")
        self.rules = []
        self.add_dir(self.root, "")

    @staticmethod
    def _compile(pat):
        neg = pat.startswith("!")
        if neg:
            pat = pat[1:]
        dir_only = pat.endswith("/")
        pat = pat.strip().strip("/")
        anchored = "/" in pat
        out = []
        i, n = 0, len(pat)
        while i < n:
            c = pat[i]
            if c == "*":
                if pat[i:i + 3] == "**/":
                    out.append("(?:.*/)?")
                    i += 3
                    continue
                if pat[i:i + 2] == "**":
                    out.append(".*")
                    i += 2
                    continue
                out.append("[^/]*")
                i += 1
                continue
            if c == "?":
                out.append("[^/]")
                i += 1
                continue
            if c == "[":
                j = pat.find("]", i + 1)
                if j > i:
                    out.append(pat[i:j + 1])
                    i = j + 1
                    continue
            out.append(re.escape(c))
            i += 1
        body = "".join(out) or "(?!)"
        rx = ("^" if anchored else "^(?:.*/)?") + body
        return neg, dir_only, re.compile(rx)

    def add_dir(self, folder, rel):
        p = os.path.join(folder, ".gitignore")
        base = (rel or "").replace("\\", "/").strip("/")
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    s = line.rstrip("\r\n")
                    if not s.strip() or s.lstrip().startswith("#"):
                        continue
                    try:
                        self.rules.append((base, self._compile(s)))
                    except Exception:
                        continue
        except Exception:
            pass

    def ignored(self, rel, is_dir):
        rel = (rel or "").replace("\\", "/").strip("/")
        if not rel:
            return False
        res = False
        for base, (neg, dir_only, rx) in self.rules:
            if base:
                if not rel.startswith(base + "/") and rel != base:
                    continue
                r = rel[len(base):].lstrip("/")
            else:
                r = rel
            if not r:
                continue
            m = rx.match(r)
            if not m:
                continue
            tail = r[m.end():]
            if tail and not tail.startswith("/"):
                continue
            if dir_only and not tail and not is_dir:
                continue
            res = not neg
        return res


def _is_binary(path):
    try:
        if os.path.getsize(path) > 4 * 1024 * 1024:
            return True
        with open(path, "rb") as f:
            return b"\x00" in f.read(4096)
    except Exception:
        return True


def _match_glob(rel, patterns):
    if not patterns:
        return True
    for pat in patterns:
        pat = pat.strip()
        if not pat:
            continue
        if re.search(r"[*?\[]", pat):
            import fnmatch
            if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(
                    os.path.basename(rel), pat):
                return True
        elif pat in rel:
            return True
    return False


def search(root, query, opts=None):
    opts = opts or {}
    use_regex = bool(opts.get("regex"))
    case = bool(opts.get("case"))
    whole = bool(opts.get("whole"))
    use_gi = opts.get("gitignore", True)
    inc = [x for x in (opts.get("include") or "").split(",") if x.strip()]
    exc = [x for x in (opts.get("exclude") or "").split(",") if x.strip()]
    limit = int(opts.get("limit") or 800)
    if not query or not root or not os.path.isdir(root):
        return {"ok": False, "hits": [], "files": 0, "scanned": 0,
                "hata": "Eksik parametre"}
    q = query
    if use_regex:
        if whole:
            q = r"\b(?:" + q + r")\b"
    else:
        q = re.escape(query)
        if whole:
            q = r"\b" + q + r"\b"
    try:
        rx = re.compile(q, 0 if case else re.IGNORECASE)
    except re.error as ex:
        return {"ok": False, "hits": [], "files": 0, "scanned": 0,
                "hata": "Regex: %s" % ex}
    gi = GitIgnore(root) if use_gi else None
    plain = None if use_regex else (query if case else query.lower())
    hits, scanned, fcount = [], 0, 0
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""
        keep = []
        for d in dirnames:
            if d in SKIP_DIRS or (d.startswith(".") and d != ".github"):
                continue
            rel = (rel_dir + "/" + d).lstrip("/")
            if gi and gi.ignored(rel, True):
                continue
            keep.append(d)
        dirnames[:] = keep
        if gi:
            gi.add_dir(dirpath, rel_dir)
        for fn in filenames:
            rel = (rel_dir + "/" + fn).lstrip("/")
            if gi and gi.ignored(rel, False):
                continue
            if inc and not _match_glob(rel, inc):
                continue
            if exc and _match_glob(rel, exc):
                continue
            p = os.path.join(dirpath, fn)
            if _is_binary(p):
                continue
            scanned += 1
            got = 0
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    for i, ln in enumerate(f, 1):
                        if plain is not None:
                            hay = ln if case else ln.lower()
                            if plain not in hay:
                                continue
                        m = rx.search(ln)
                        if not m:
                            continue
                        hits.append({"path": p, "rel": rel, "line": i,
                                     "col": m.start(),
                                     "text": ln.rstrip()[:240]})
                        got += 1
                        if len(hits) >= limit:
                            truncated = True
                            break
            except Exception:
                continue
            if got:
                fcount += 1
            if truncated:
                break
        if truncated:
            break
    return {"ok": True, "hits": hits, "files": fcount,
            "scanned": scanned, "truncated": truncated}


def replace_all(root, query, repl, opts=None):
    res = search(root, query, opts)
    if not res.get("ok"):
        return res
    opts = opts or {}
    use_regex = bool(opts.get("regex"))
    case = bool(opts.get("case"))
    whole = bool(opts.get("whole"))
    q = query
    if use_regex:
        if whole:
            q = r"\b(?:" + q + r")\b"
    else:
        q = re.escape(query)
        if whole:
            q = r"\b" + q + r"\b"
    rx = re.compile(q, 0 if case else re.IGNORECASE)
    byfile = {}
    for h in res["hits"]:
        byfile.setdefault(h["path"], 0)
        byfile[h["path"]] += 1
    backup, total, changed = [], 0, 0
    for p in byfile:
        try:
            with open(p, "r", encoding="utf-8", errors="strict") as f:
                src = f.read()
        except Exception:
            continue
        new, k = rx.subn(repl or "", src)
        if not k:
            continue
        backup.append({"path": p, "content": src})
        try:
            d = os.path.dirname(p)
            fd, tmp = tempfile.mkstemp(dir=d, suffix=".sctmp")
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            os.replace(tmp, p)
            total += k
            changed += 1
        except Exception:
            backup.pop()
    return {"ok": True, "replacements": total, "changed_files": changed,
            "backup": backup}


def restore_backup(backup):
    n = 0
    for item in (backup or []):
        try:
            with open(item["path"], "w", encoding="utf-8", newline="") as f:
                f.write(item["content"])
            n += 1
        except Exception:
            continue
    return {"ok": True, "restored": n}


# ── AI Streaming ──────────────────────────────────────────────────────
class AiStreams:
    def __init__(self):
        self.lock = threading.Lock()
        self.cancels = {}
        self.n = 0

    def start(self, provider, key, model, messages):
        if not key:
            return {"ok": False, "hata": "API key yok"}
        with self.lock:
            self.n += 1
            sid = "s%d" % self.n
            ev = threading.Event()
            self.cancels[sid] = ev
        threading.Thread(
            target=self._run,
            args=(sid, provider, key, model, messages or [], ev),
            name="sc-ai-" + sid, daemon=True).start()
        return {"ok": True, "id": sid}

    def cancel(self, sid):
        with self.lock:
            ev = self.cancels.get(sid)
        if ev:
            ev.set()
            return {"ok": True}
        return {"ok": False}

    def _emit_lines(self, resp, ev, on_data):
        for raw in resp:
            if ev.is_set():
                break
            line = raw.decode("utf-8", "replace").strip()
            if not line or not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                on_data(json.loads(payload))
            except Exception:
                continue

    def _run(self, sid, provider, key, model, messages, ev):
        parts = []
        err = None
        try:
            if provider == "gemini":
                model = (model or "gemini-2.5-flash").strip()
                sysp, contents = [], []
                for m in messages:
                    r = m.get("role")
                    t = m.get("content") or ""
                    if r == "system":
                        sysp.append(t)
                    else:
                        contents.append({
                            "role": "user" if r == "user" else "model",
                            "parts": [{"text": t}]})
                if not contents:
                    raise RuntimeError("Bos mesaj")
                if contents[0]["role"] != "user":
                    contents.insert(0, {"role": "user",
                                        "parts": [{"text": "(baglam)"}]})
                body = {"contents": contents}
                if sysp:
                    body["systemInstruction"] = {
                        "parts": [{"text": "\n\n".join(sysp)}]}
                url = ("https://generativelanguage.googleapis.com/v1beta/"
                       "models/" + model + ":streamGenerateContent?alt=sse")
                req = urllib.request.Request(
                    url, data=json.dumps(body).encode("utf-8"),
                    headers={"Content-Type": "application/json",
                             "x-goog-api-key": key}, method="POST")

                def on(d):
                    for c in (d.get("candidates") or []):
                        for p in ((c.get("content") or {}).get("parts") or []):
                            t = p.get("text") or ""
                            if t:
                                parts.append(t)
                                js_call("scAiChunk", sid, t)
                with urllib.request.urlopen(req, timeout=180) as resp:
                    self._emit_lines(resp, ev, on)

            elif provider == "claude":
                model = (model or "claude-sonnet-4-5").strip()
                sysp, msgs = [], []
                for m in messages:
                    if m.get("role") == "system":
                        sysp.append(m.get("content") or "")
                    else:
                        msgs.append({
                            "role": "assistant" if m.get("role") == "assistant"
                            else "user",
                            "content": m.get("content") or ""})
                if not msgs:
                    raise RuntimeError("Bos mesaj")
                body = {"model": model, "max_tokens": 8192,
                        "messages": msgs, "stream": True}
                if sysp:
                    body["system"] = "\n\n".join(sysp)
                req = urllib.request.Request(
                    "https://api.anthropic.com/v1/messages",
                    data=json.dumps(body).encode("utf-8"),
                    headers={"Content-Type": "application/json",
                             "x-api-key": key,
                             "anthropic-version": "2023-06-01"},
                    method="POST")

                def on(d):
                    if d.get("type") == "content_block_delta":
                        t = (d.get("delta") or {}).get("text") or ""
                        if t:
                            parts.append(t)
                            js_call("scAiChunk", sid, t)
                    elif d.get("type") == "error":
                        raise RuntimeError(
                            (d.get("error") or {}).get("message", "AI hatasi"))
                with urllib.request.urlopen(req, timeout=180) as resp:
                    self._emit_lines(resp, ev, on)
            else:
                err = "Bilinmeyen saglayici"
        except urllib.error.HTTPError as ex:
            try:
                err = "HTTP %s: %s" % (
                    ex.code, ex.read().decode("utf-8", "ignore")[:300])
            except Exception:
                err = "HTTP %s" % ex.code
        except Exception as ex:
            err = str(ex)
        js_call("scAiDone", sid, "".join(parts), err, ev.is_set())
        with self.lock:
            self.cancels.pop(sid, None)


AI = AiStreams()


# ── Font yerellestirme ────────────────────────────────────────────────
def localize_fonts():
    out_dir = os.path.join(pkg_dir(), "static", "fonts")
    os.makedirs(out_dir, exist_ok=True)
    try:
        req = urllib.request.Request(FONT_CSS, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=90) as r:
            css = r.read().decode("utf-8", "replace")
    except Exception as ex:
        return {"ok": False, "hata": "CSS indirilemedi: %s" % ex}
    urls = sorted(set(re.findall(r"url\((https://[^)]+)\)", css)))
    if not urls:
        return {"ok": False, "hata": "Font URL bulunamadi"}
    n = 0
    for u in urls:
        name = u.split("/")[-1].split("?")[0]
        if not name:
            name = "f%d.woff2" % n
        dest = os.path.join(out_dir, name)
        try:
            if not os.path.isfile(dest):
                rq = urllib.request.Request(u, headers={"User-Agent": UA})
                with urllib.request.urlopen(rq, timeout=90) as r:
                    data = r.read()
                with open(dest, "wb") as f:
                    f.write(data)
            css = css.replace(u, name)
            n += 1
        except Exception:
            continue
    try:
        with open(os.path.join(out_dir, "sc-fonts.css"), "w",
                  encoding="utf-8") as f:
            f.write(css)
    except Exception as ex:
        return {"ok": False, "hata": str(ex)}
    return {"ok": True, "files": n, "dir": out_dir}
