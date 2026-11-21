"""
Splash Code Studio - WebView API
Frontend (JS) <-> backend (Python) koprusu

Patch 002:
  * durdur() gercek: process-tree kill
  * 16 eksik metod eklendi (format/lint/rename/refs/symbols/todo/
    debug/git_diff/test/treesitter/harici terminal/calistir_icerik)
  * URI normalizasyonu (frontend encodeURI vs Path.as_uri uyumsuzlugu)
  * git: UTF-8 + porcelain -z (Turkce yol/commit bozulmasi yok)
  * _cwd dosya acilinca da set ediliyor (LSP root dogru)
  * kaydet: atomik + EOL + hash/size
  * lsp_diagnostics artik sunucu SPAWN ETMIYOR
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import sys
import threading
import time

from .constants import (
    APP_NAME, APP_VERSION, LSP_SERVERS, LSP_INSTALL_CMDS,
    LSP_INSTALL_NOTES, LSP_MONACO_IDS, BUILTINS,
    ICON_PACKS, DEFAULT_ICON_MAP, ICON_MAP_FILE, SETTINGS_DIR,
    get_lang,
)
from .settings import (
    load_settings, save_settings, load_session, save_session,
    load_icon_map, save_icon_map, normalize_settings,
)
from .lsp_client import get_lsp, shutdown_all_lsp
from .terminal import (
    term_spawn, term_write, term_resize, term_close,
    close_all_terminals,
)
from .ai import ai_gemini, ai_claude
from .themes import all_themes, save_user_theme, delete_user_theme
from .html_builder import clear_build_cache
from .utils import atomic_write, is_binary_path, path_to_uri

try:
    from .utils import uri_to_path
except Exception:
    def uri_to_path(u):
        return u

try:
    from .log import exc as _log_exc, info as _log_info, warn as _log_warn
except Exception:
    def _log_exc(*a, **k):
        pass

    def _log_info(*a, **k):
        pass

    def _log_warn(*a, **k):
        pass

try:
    from .lsp_client import peek_lsp as _peek_lsp
except Exception:
    _peek_lsp = None

_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_SKIP_DIRS = {
    "node_modules", "__pycache__", ".git", "venv", ".venv",
    "dist", "build", ".next", "target", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "site-packages",
}
_TODO_RE = re.compile(r"\b(TODO|FIXME|XXX|HACK|NOTE)\b[:\s]*(.*)")
_WHICH_CACHE = {}
_WHICH_LOCK = threading.Lock()


def _which(exe):
    """shutil.which cache'li (bilgi() 19 kez PATH taramasin)."""
    with _WHICH_LOCK:
        hit = _WHICH_CACHE.get(exe)
        if hit is not None and time.time() - hit[0] < 60:
            return hit[1]
    if os.path.isabs(exe):
        found = exe if os.path.isfile(exe) else None
    else:
        found = shutil.which(exe)
    with _WHICH_LOCK:
        _WHICH_CACHE[exe] = (time.time(), found)
    return found


def _norm_uri(uri):
    """Frontend'den gelen URI'yi backend'in canonical formuna cevirir."""
    try:
        s = str(uri or "")
        if not s.startswith("file:"):
            return s
        p = uri_to_path(s)
        if p and os.path.isabs(p):
            return path_to_uri(p)
        return s
    except Exception:
        return str(uri or "")


def _iter_files(cwd, max_size=2 * 1024 * 1024):
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs
                   if d not in _SKIP_DIRS and not d.startswith(".")]
        for fn in files:
            p = os.path.join(root, fn)
            try:
                if os.path.getsize(p) > max_size:
                    continue
                if is_binary_path(p):
                    continue
            except Exception:
                continue
            yield p


def _run_hidden(cmd, cwd=None, timeout=30):
    kw = {}
    if _NO_WINDOW:
        kw["creationflags"] = _NO_WINDOW
    return subprocess.run(
        cmd, cwd=cwd, capture_output=True, timeout=timeout,
        encoding="utf-8", errors="replace", **kw)


def _basic_format(text, tab_size=4):
    """Guvenli minimal normalize: trailing WS + final newline."""
    lines = [ln.rstrip() for ln in
             text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while len(lines) > 1 and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def _scan_brackets(code):
    """String/comment farkindalikli parantez tarayici."""
    pairs = {")": "(", "]": "[", "}": "{"}
    opens = set("([{")
    stack = []
    out = []
    i, n = 0, len(code)
    line, col = 0, 0
    in_s = None
    triple = False
    while i < n:
        c = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if c == "\n":
            line += 1
            col = 0
            if in_s and not triple:
                in_s = None
            i += 1
            continue
        if in_s:
            if triple:
                if code.startswith(in_s * 3, i):
                    in_s = None
                    triple = False
                    col += 3
                    i += 3
                    continue
            elif c == "\\":
                col += 2
                i += 2
                continue
            elif c == in_s:
                in_s = None
            col += 1
            i += 1
            continue
        if code.startswith(chr(34)*3, i) or code.startswith(chr(39)*3, i):
            in_s = code[i]
            triple = True
            col += 3
            i += 3
            continue
        if c == "#" or code.startswith("//", i):
            j = code.find("\n", i)
            j = n if j < 0 else j
            col += j - i
            i = j
            continue
        if code.startswith("/*", i):
            j = code.find("*/", i + 2)
            j = n if j < 0 else j + 2
            seg = code[i:j]
            line += seg.count("\n")
            col = len(seg) if "\n" not in seg else len(seg.split("\n")[-1])
            i = j
            continue
        if c in ("'", '"', "`"):
            in_s = c
            col += 1
            i += 1
            continue
        if c in opens:
            stack.append((c, line, col))
        elif c in pairs:
            if stack and stack[-1][0] == pairs[c]:
                o = stack.pop()
                out.append((o[1], o[2], line, col))
        col += 1
        i += 1
    return out


class Api:
    """pywebview js_api olarak kullanilan ana API sinifi."""

    def __init__(self):
        self.settings = load_settings()
        self.session = load_session()
        c = self.settings.get("lastProject")
        self._cwd = c if (c and os.path.isdir(c)) else None
        self._cur_path = None
        self._cur_tab_id = None
        self._run_proc = None
        self._run_lock = threading.Lock()
        self._ext_term = None

    # ── Yardimci ─────────────────────────────────────
    def _js(self, code):
        try:
            import webview
            if webview.windows:
                webview.windows[0].evaluate_js(code)
        except Exception as e:
            _log_warn("evaluate_js: %s", e)

    def _js_call(self, fn, *args):
        self._js("if(window.%s) window.%s(%s);" % (
            fn, fn, ",".join(json.dumps(a, ensure_ascii=False)
                             for a in args)))

    def _set_cwd_for(self, path):
        try:
            d = os.path.dirname(os.path.abspath(path))
            if os.path.isdir(d):
                self._cwd = d
        except Exception:
            pass

    def _lsp_req(self, lang, uri, text, method, extra=None, timeout=8):
        """LSP istegi: dokumani senkronlar, sonra request atar."""
        try:
            c = get_lsp(lang, self._cwd)
            if not c or not c.proc:
                return None
            if not c.initialize():
                return None
            sync = getattr(c, "_sync", None) or c.did_change
            sync(uri, text)
            params = {"textDocument": {"uri": uri}}
            params.update(extra or {})
            r = c._request(method, params, timeout=timeout)
            return (r or {}).get("result")
        except Exception as e:
            _log_exc("lsp_req %s" % method, e)
            return None

    # ── Ayarlar ──────────────────────────────────────
    def ayarlari_yukle(self):
        return self.settings

    def ayarlari_kaydet(self, s):
        try:
            _s = dict(s or {})
            if "saveBeforeRun" in _s and "autoSaveBeforeRun" not in _s:
                _s["autoSaveBeforeRun"] = _s["saveBeforeRun"]
            merged = dict(self.settings)
            merged.update(_s)
            self.settings = normalize_settings(merged)
            save_settings(self.settings)
            clear_build_cache()
            return {"ok": True, "settings": self.settings}
        except Exception as e:
            _log_exc("ayarlari_kaydet", e)
            return {"ok": False, "hata": str(e)}

    # ── Oturum ───────────────────────────────────────
    def oturum_yukle(self):
        return self.session

    def oturum_kaydet(self, s):
        try:
            self.session.update(s or {})
            save_session(self.session)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    # ── Dosya ────────────────────────────────────────
    def dosya_ac(self):
        try:
            import webview
            r = webview.windows[0].create_file_dialog(
                webview.OPEN_DIALOG, allow_multiple=False)
            if not r:
                return None
            p = r[0] if isinstance(r, (list, tuple)) else r
            return self._read_file(p)
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def dosya_oku(self, path):
        return self._read_file(path)

    def _read_file(self, path):
        try:
            path = os.path.abspath(path)
            if not os.path.isfile(path):
                return {"ok": False, "hata": "Dosya bulunamadi"}
            size = os.path.getsize(path)
            with open(path, "rb") as f:
                raw = f.read()
            try:
                content = raw.decode("utf-8")
                enc = "utf-8"
            except UnicodeDecodeError:
                content = raw.decode("latin-1")
                enc = "latin-1"
            self._cur_path = path
            self._set_cwd_for(path)
            return {
                "ok": True, "path": path,
                "name": os.path.basename(path),
                "lang": get_lang(path), "content": content,
                "encoding": enc,
                "hash": hashlib.sha1(raw).hexdigest(),
                "size": size,
            }
        except Exception as e:
            _log_exc("_read_file", e)
            return {"ok": False, "hata": str(e)}

    def kaydet(self, path, content):
        try:
            if not path:
                return self.farkli_kaydet(content)
            path = os.path.abspath(path)
            d = os.path.dirname(path)
            if d:
                os.makedirs(d, exist_ok=True)
            text = "" if content is None else str(content)
            eol = self.settings.get("endOfLine", "\n")
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            if eol == "\r\n":
                text = text.replace("\n", "\r\n")
            enc = self.settings.get("encoding", "utf-8") or "utf-8"
            raw = text.encode(enc, "replace")
            fd, tmp = tempfile.mkstemp(dir=d or ".", suffix=".sctmp")
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(raw)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        pass
                os.replace(tmp, path)
            except Exception:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                raise
            self._cur_path = path
            self._set_cwd_for(path)
            return {
                "ok": True, "path": path,
                "name": os.path.basename(path),
                "lang": get_lang(path),
                "hash": hashlib.sha1(raw).hexdigest(),
                "size": len(raw),
            }
        except Exception as e:
            _log_exc("kaydet", e)
            return {"ok": False, "hata": str(e)}

    def farkli_kaydet(self, content):
        try:
            import webview
            r = webview.windows[0].create_file_dialog(
                webview.SAVE_DIALOG, save_filename="untitled.py")
            if not r:
                return {"ok": False, "hata": "Iptal"}
            path = r if isinstance(r, str) else (r[0] if r else None)
            if not path:
                return {"ok": False, "hata": "Iptal"}
            return self.kaydet(path, content)
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def klasor_sec(self):
        try:
            import webview
            r = webview.windows[0].create_file_dialog(
                webview.FOLDER_DIALOG)
            if not r:
                return {"ok": False, "hata": "Iptal"}
            cwd = r[0] if isinstance(r, (list, tuple)) else r
            if not cwd or not os.path.isdir(cwd):
                return {"ok": False, "hata": "Gecersiz klasor"}
            self._cwd = cwd
            self.settings["lastProject"] = cwd
            save_settings(self.settings)
            clear_build_cache()
            return {"ok": True, "cwd": cwd,
                    "files": self._list_dir(cwd, top=True)}
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def _list_dir(self, cwd, top=False, max_items=5000):
        out = []
        try:
            for e in sorted(os.scandir(cwd),
                            key=lambda x: (not x.is_dir(),
                                           x.name.lower())):
                if e.name.startswith(".") and e.name not in (
                        ".env", ".gitignore"):
                    continue
                if e.name in _SKIP_DIRS:
                    continue
                out.append({"name": e.name, "path": e.path,
                            "is_dir": e.is_dir()})
                if len(out) >= max_items:
                    break
        except Exception as e:
            _log_warn("_list_dir: %s", e)
        return out

    def klasor_icerik(self, path):
        try:
            if not path or not os.path.isdir(path):
                return []
            return self._list_dir(path)
        except Exception:
            return []

    def _safe_child(self, parent, name):
        name = str(name or "").strip().replace("\\", "/")
        if not name or name.startswith("/") or ".." in name.split("/"):
            raise ValueError("Gecersiz isim")
        if os.path.isabs(name) or (len(name) > 1 and name[1] == ":"):
            raise ValueError("Mutlak yol kabul edilmez")
        base = os.path.abspath(parent or self._cwd or os.getcwd())
        p = os.path.abspath(os.path.join(base, name))
        if os.path.commonpath([base, p]) != base:
            raise ValueError("Klasor disina cikilamaz")
        return p

    def yeni_dosya(self, parent, name):
        try:
            path = self._safe_child(parent, name)
            if os.path.exists(path):
                return {"ok": False, "hata": "Zaten var"}
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
            return {"ok": True, "path": path,
                    "name": os.path.basename(path)}
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def yeni_klasor(self, parent, name):
        try:
            path = self._safe_child(parent, name)
            os.makedirs(path, exist_ok=True)
            return {"ok": True, "path": path}
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def dosya_sil(self, path):
        try:
            path = os.path.abspath(path)
            try:
                from send2trash import send2trash
                send2trash(path)
                return {"ok": True, "trash": True}
            except ImportError:
                pass
            except Exception as e:
                _log_warn("send2trash: %s", e)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            return {"ok": True, "trash": False}
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def dosya_yeniden_adlandir(self, old, new):
        try:
            if os.path.exists(new):
                return {"ok": False, "hata": "Hedef var"}
            os.rename(old, new)
            return {"ok": True, "path": os.path.abspath(new)}
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    # ── LSP ──────────────────────────────────────────
    def lsp_check(self, lang):
        try:
            cmd = LSP_SERVERS.get(lang)
            if not cmd:
                return {"active": False, "reason": "desteklenmiyor"}
            if not _which(cmd[0]):
                return {"active": False, "reason": "sunucu yok"}
            return {"active": True}
        except Exception:
            return {"active": False}

    def lsp_kur(self, lang):
        try:
            cmd = LSP_INSTALL_CMDS.get(lang)
            if cmd is None:
                return {"ok": False, "manuel": True,
                        "hata": LSP_INSTALL_NOTES.get(
                            lang, "Elle kurulum gerekli")}
            r = _run_hidden(cmd, timeout=300)
            ok = r.returncode == 0
            with _WHICH_LOCK:
                _WHICH_CACHE.clear()
            return {"ok": ok, "out": (r.stdout or "")[-2000:],
                    "err": (r.stderr or "")[-2000:] if not ok else ""}
        except Exception as e:
            _log_exc("lsp_kur", e)
            return {"ok": False, "hata": str(e)}

    def lsp_complete(self, lang, uri, text, line, col):
        try:
            c = get_lsp(lang, self._cwd)
            if not c.proc:
                return {"items": []}
            return {"items": c.completion(
                _norm_uri(uri), line, col, text) or []}
        except Exception:
            return {"items": []}

    def lsp_hover(self, lang, uri, text, line, col):
        try:
            c = get_lsp(lang, self._cwd)
            if not c.proc:
                return None
            h = c.hover(_norm_uri(uri), line, col, text)
            if not h:
                return None
            ct = h.get("contents")
            if isinstance(ct, dict):
                return {"content": ct.get("value", "")}
            if isinstance(ct, list):
                parts = [(x.get("value", "") if isinstance(x, dict)
                          else str(x)) for x in ct]
                return {"content": "\n".join(parts)}
            return {"content": str(ct)}
        except Exception:
            return None

    def lsp_definition(self, lang, uri, text, line, col):
        try:
            c = get_lsp(lang, self._cwd)
            if not c.proc:
                return None
            d = c.definition(_norm_uri(uri), line, col, text)
            if isinstance(d, list):
                d = d[0] if d else None
            if not d:
                return None
            return {"location": {"uri": d.get("uri"),
                                 "range": d.get("range")}}
        except Exception:
            return None

    def lsp_diagnostics(self, lang, uri):
        """Sunucu SPAWN ETMEZ - sadece var olan client'tan okur."""
        try:
            u = _norm_uri(uri)
            c = None
            if _peek_lsp is not None:
                c = _peek_lsp(lang, self._cwd) or _peek_lsp(lang)
            else:
                c = get_lsp(lang, self._cwd)
            if not c or not c.proc:
                return {"items": []}
            items = c.diagnostics_for(u)
            if not items and u != str(uri):
                items = c.diagnostics_for(str(uri))
            return {"items": items}
        except Exception:
            return {"items": []}

    def lsp_durum(self, lang):
        try:
            c = (_peek_lsp(lang, self._cwd) if _peek_lsp
                 else get_lsp(lang, self._cwd))
            running = bool(c and c.proc and c.proc.poll() is None
                           and getattr(c, "_ready", False))
            nd = 0
            if c:
                with c._diag_lock:
                    nd = sum(len(v) for v in c._diagnostics.values())
            return {"running": running, "clients": 1 if c else 0,
                    "diagnostics": nd,
                    "installed": bool(_which(
                        (LSP_SERVERS.get(lang) or [""])[0])),
                    "stderr": list(getattr(c, "stderr_tail", []))[-15:]}
        except Exception as e:
            return {"running": False, "clients": 0,
                    "diagnostics": 0, "hata": str(e)}

    def lsp_symbols(self, lang, uri, text):
        r = self._lsp_req(lang, _norm_uri(uri), text,
                          "textDocument/documentSymbol")
        return {"items": r or []}

    def lsp_references(self, lang, uri, text, line, col):
        r = self._lsp_req(lang, _norm_uri(uri), text,
                          "textDocument/references", {
                              "position": {"line": line,
                                           "character": col},
                              "context": {"includeDeclaration": True},
                          })
        return {"items": r or []}

    def lsp_rename(self, lang, uri, text, line, col, new_name):
        if not (new_name or "").strip():
            return {"ok": False, "hata": "Isim bos"}
        r = self._lsp_req(lang, _norm_uri(uri), text,
                          "textDocument/rename", {
                              "position": {"line": line,
                                           "character": col},
                              "newName": new_name,
                          }, timeout=12)
        if not r:
            return {"ok": False, "hata": "Rename desteklenmiyor"}
        changes = r.get("changes")
        if not changes and r.get("documentChanges"):
            changes = {}
            for dc in r["documentChanges"]:
                tu = (dc.get("textDocument") or {}).get("uri")
                if tu:
                    changes.setdefault(tu, []).extend(
                        dc.get("edits") or [])
        if not changes:
            return {"ok": False, "hata": "Degisiklik yok"}
        return {"ok": True, "edits": {"changes": changes}}

    def fake_complete(self, lang, text, line, col):
        try:
            lines = text.split("\n") if text else []
            prefix = lines[line][:col] if 0 <= line < len(lines) else ""
            m = re.search(r"([A-Za-z_][A-Za-z0-9_]*)$", prefix)
            word = m.group(1) if m else ""
            if not word:
                return []
            wl = word.lower()
            base = BUILTINS.get(lang, [])
            out = [{"label": b, "insertText": b, "sortText": "0_" + b}
                   for b in base
                   if b.lower().startswith(wl) and b != word]
            words = set(re.findall(
                r"[A-Za-z_][A-Za-z0-9_]{2,}", text or ""))
            for w in sorted(words):
                if (w.lower().startswith(wl) and w != word
                        and w not in base):
                    out.append({"label": w, "insertText": w,
                                "sortText": "1_" + w})
            return out[:80]
        except Exception:
            return []

    # ── Format / Lint ────────────────────────────────
    def format_dosya(self, path, code):
        """LSP -> harici formatter -> guvenli normalize."""
        try:
            code = "" if code is None else str(code)
            lang = get_lang(path or "untitled.py")
            tab = int(self.settings.get("tabSize", 4) or 4)
            if self.settings.get("lspEnabled", True):
                c = (_peek_lsp(lang, self._cwd) if _peek_lsp else None)
                fn = getattr(c, "formatting", None) if c else None
                if fn and c.proc:
                    uri = _norm_uri(path_to_uri(path)) if path else None
                    if uri:
                        edits = fn(uri, code, tab, True)
                        if edits:
                            txt = self._apply_edits(code, edits)
                            if txt is not None:
                                return {"ok": True, "text": txt,
                                        "engine": "lsp"}
            ext = os.path.splitext(path or "")[1].lower()
            cmd = None
            if ext == ".py":
                if _which("black"):
                    cmd = ["black", "-q", "--line-length", "88", "-"]
                elif _which("autopep8"):
                    cmd = ["autopep8", "-"]
            elif ext in (".js", ".jsx", ".ts", ".tsx", ".json",
                         ".css", ".scss", ".html", ".md", ".yaml",
                         ".yml"):
                if _which("prettier"):
                    cmd = ["prettier", "--stdin-filepath",
                           os.path.abspath(path or ("f" + ext))]
            elif ext == ".rs" and _which("rustfmt"):
                cmd = ["rustfmt", "--emit", "stdout"]
            elif ext == ".go" and _which("gofmt"):
                cmd = ["gofmt"]
            elif ext in (".c", ".h", ".cpp", ".hpp", ".cc", ".cs") \
                    and _which("clang-format"):
                cmd = ["clang-format"]
            if cmd:
                kw = {}
                if _NO_WINDOW:
                    kw["creationflags"] = _NO_WINDOW
                p = subprocess.run(
                    cmd, input=code.encode("utf-8"),
                    capture_output=True, timeout=25, **kw)
                if p.returncode == 0 and p.stdout:
                    return {"ok": True,
                            "text": p.stdout.decode("utf-8", "replace"),
                            "engine": cmd[0]}
                _log_warn("format %s rc=%s", cmd[0], p.returncode)
            return {"ok": True, "text": _basic_format(code, tab),
                    "engine": "basic"}
        except Exception as e:
            _log_exc("format_dosya", e)
            return {"ok": False, "hata": str(e)}

    @staticmethod
    def _apply_edits(text, edits):
        try:
            lines = text.replace("\r\n", "\n").split("\n")
            se = sorted(edits, key=lambda e: (
                e["range"]["start"]["line"],
                e["range"]["start"]["character"]), reverse=True)
            for e in se:
                s, en = e["range"]["start"], e["range"]["end"]
                if s["line"] == en["line"]:
                    ln = lines[s["line"]]
                    lines[s["line"]] = (ln[:s["character"]]
                                        + e.get("newText", "")
                                        + ln[en["character"]:])
                else:
                    head = lines[s["line"]][:s["character"]]
                    tail = lines[en["line"]][en["character"]:]
                    new = (head + e.get("newText", "") + tail)
                    lines[s["line"]:en["line"] + 1] = new.split("\n")
            return "\n".join(lines)
        except Exception as e:
            _log_exc("_apply_edits", e)
            return None

    def lint_dosya(self, path):
        issues = []
        try:
            if not path or not os.path.isfile(path):
                return {"issues": []}
            ext = os.path.splitext(path)[1].lower()
            if ext == ".py":
                with open(path, "r", encoding="utf-8",
                          errors="replace") as f:
                    src = f.read()
                try:
                    compile(src, path, "exec")
                except SyntaxError as se:
                    issues.append({
                        "severity": "error",
                        "line": se.lineno or 1,
                        "msg": se.msg or "Syntax error"})
                tool = None
                if _which("ruff"):
                    tool = ["ruff", "check", "--output-format",
                            "json", "--no-cache", path]
                elif _which("pyflakes"):
                    tool = ["pyflakes", path]
                if tool:
                    r = _run_hidden(tool, timeout=25)
                    txt = (r.stdout or "") + (r.stderr or "")
                    if tool[0] == "ruff":
                        try:
                            for it in json.loads(r.stdout or "[]"):
                                issues.append({
                                    "severity": "warning",
                                    "line": (it.get("location") or {})
                                    .get("row", 1),
                                    "msg": "%s %s" % (
                                        it.get("code", ""),
                                        it.get("message", ""))})
                        except Exception:
                            pass
                    else:
                        for ln in txt.splitlines():
                            m = re.search(r":(\d+):(?:(\d+):)?\s*(.*)",
                                          ln)
                            if m:
                                issues.append({
                                    "severity": "warning",
                                    "line": int(m.group(1)),
                                    "msg": m.group(3)[:200]})
            else:
                lang = get_lang(path)
                d = self.lsp_diagnostics(lang, path_to_uri(path))
                for it in (d.get("items") or []):
                    sev = it.get("severity", 1)
                    issues.append({
                        "severity": ("error" if sev == 1 else
                                     "warning" if sev == 2 else "info"),
                        "line": ((it.get("range") or {})
                                 .get("start") or {}).get("line", 0) + 1,
                        "msg": it.get("message", "")})
            return {"issues": issues[:200]}
        except Exception as e:
            _log_exc("lint_dosya", e)
            return {"issues": issues, "hata": str(e)}

    # ── Tree-Sitter / Outline / Bracket ──────────────
    def treesitter_parse(self, lang, code):
        code = code or ""
        try:
            import tree_sitter_languages as tsl
            parser = tsl.get_parser(lang)
            tree = parser.parse(code.encode("utf-8"))
            nodes = []

            def walk(n):
                if n.type in ("function_definition",
                              "class_definition",
                              "function_declaration",
                              "method_definition",
                              "struct_item", "impl_item"):
                    nm = ""
                    for ch in n.children:
                        if ch.type in ("identifier",
                                       "name", "type_identifier"):
                            nm = code.encode("utf-8")[
                                ch.start_byte:ch.end_byte].decode(
                                    "utf-8", "replace")
                            break
                    nodes.append({"type": n.type, "name": nm,
                                  "start_line": n.start_point[0],
                                  "end_line": n.end_point[0]})
                for ch in n.children:
                    walk(ch)
            walk(tree.root_node)
            return {"ok": True, "engine": "tree-sitter",
                    "count": len(nodes), "nodes": nodes[:300]}
        except Exception:
            pass
        if lang == "python":
            try:
                import ast
                t = ast.parse(code)
                nodes = []
                for n in ast.walk(t):
                    if isinstance(n, (ast.FunctionDef,
                                      ast.AsyncFunctionDef,
                                      ast.ClassDef)):
                        nodes.append({
                            "type": ("class" if isinstance(
                                n, ast.ClassDef) else "function"),
                            "name": n.name,
                            "start_line": (n.lineno or 1) - 1,
                            "end_line": (getattr(n, "end_lineno",
                                                 n.lineno) or 1) - 1})
                nodes.sort(key=lambda x: x["start_line"])
                return {"ok": True, "engine": "ast",
                        "count": len(nodes), "nodes": nodes[:300]}
            except SyntaxError:
                pass
        pat = re.compile(
            r"^\s*(?:def|class|function|func|fn|sub|package)\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)", re.M)
        nodes = [{"type": "decl", "name": m.group(1),
                  "start_line": code[:m.start()].count("\n"),
                  "end_line": code[:m.start()].count("\n")}
                 for m in pat.finditer(code)]
        return {"ok": True, "engine": "regex",
                "count": len(nodes), "nodes": nodes[:300]}

    def treesitter_bracket(self, code, line, col):
        try:
            pairs = _scan_brackets(code or "")
            if not pairs:
                return {"ok": False}
            best = None
            for (ol, oc, cl, cc) in pairs:
                if (ol, oc) <= (line, col) <= (cl, cc):
                    if best is None or (ol, oc) > (best[0], best[1]):
                        best = (ol, oc, cl, cc)
            if best is None:
                for p in pairs:
                    if p[0] == line and abs(p[1] - col) <= 1:
                        best = p
                        break
                    if p[2] == line and abs(p[3] - col) <= 1:
                        best = p
                        break
            if not best:
                return {"ok": False}
            return {"ok": True,
                    "open": {"line": best[0], "col": best[1]},
                    "close": {"line": best[2], "col": best[3]}}
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    # ── Terminal ─────────────────────────────────────
    def terminal_baslat(self, cwd, shell_cmd=None):
        return term_spawn("t1", cwd or self._cwd or os.getcwd(),
                          shell_cmd)

    def terminal_yaz(self, term_id, data):
        return term_write(term_id or "t1", data)

    def terminal_yeniden_boyutlandir(self, term_id, rows, cols):
        return term_resize(term_id or "t1", rows, cols)

    def terminal_kapat(self, term_id):
        return term_close(term_id or "t1")

    def _term_cmdline(self, cmd_text):
        """Aktif shell'e uygun komut satiri (PowerShell needs &)."""
        if os.name == "nt":
            return "& " + cmd_text + "\r"
        return cmd_text + "\n"

    def _send_to_term(self, cwd, cmd_text):
        r = term_spawn("t1", cwd or self._cwd or os.getcwd(), None)
        if not r.get("ok"):
            return r
        time.sleep(0.6)
        return term_write("t1", self._term_cmdline(cmd_text))

    def harici_terminal_ac(self, cwd, shell=None):
        cwd = cwd or self._cwd or os.getcwd()
        try:
            if os.name == "nt":
                wt = _which("wt")
                ps = (_which("pwsh") or _which("powershell")
                      or "powershell.exe")
                if wt:
                    cmd = [wt, "-d", cwd, ps, "-NoExit"]
                    name = "Windows Terminal"
                else:
                    cmd = ["cmd", "/c", "start", "", ps,
                           "-NoExit", "-Command",
                           "Set-Location -LiteralPath '%s'"
                           % cwd.replace("'", "''")]
                    name = "PowerShell"
                subprocess.Popen(cmd, cwd=cwd,
                                 creationflags=_NO_WINDOW)
                return {"ok": True, "terminal": name,
                        "deelevated": False}
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "Terminal", cwd])
                return {"ok": True, "terminal": "Terminal.app"}
            for t, args in (
                ("x-terminal-emulator", []),
                ("gnome-terminal", ["--working-directory", cwd]),
                ("konsole", ["--workdir", cwd]),
                ("xfce4-terminal", ["--working-directory", cwd]),
                ("xterm", []),
            ):
                if _which(t):
                    subprocess.Popen([t] + args, cwd=cwd)
                    return {"ok": True, "terminal": t}
            return {"ok": False, "hata": "Terminal emulator bulunamadi"}
        except Exception as e:
            _log_exc("harici_terminal_ac", e)
            return {"ok": False, "hata": str(e)}

    # ── Calistirma ───────────────────────────────────
    def _build_cmd(self, path, cwd):
        ext = os.path.splitext(path)[1].lower()
        q = os.path.abspath(path)
        if ext in (".py", ".pyw"):
            return [sys.executable, "-u", q]
        if ext in (".js", ".mjs", ".cjs"):
            return ["node", q]
        if ext in (".ts", ".tsx"):
            if _which("tsx"):
                return ["tsx", q]
            return ["npx", "--yes", "tsx", q]
        if ext == ".sh":
            return ["bash", q]
        if ext == ".ps1":
            return [_which("pwsh") or "powershell",
                    "-ExecutionPolicy", "Bypass", "-File", q]
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
            man = os.path.join(cwd or os.path.dirname(q),
                               "Cargo.toml")
            if os.path.isfile(man):
                return ["cargo", "run", "--manifest-path", man]
            out = os.path.join(tempfile.gettempdir(),
                               "sc_rs_out")
            return ["rustc", q, "-o", out]
        return None

    def calistir(self, path, cwd):
        if not path:
            return {"ok": False, "hata": "Dosya yok"}
        cwd = cwd or os.path.dirname(path) or os.getcwd()
        cmd = self._build_cmd(path, cwd)
        if not cmd:
            return {"ok": False,
                    "hata": "Desteklenmeyen: %s"
                            % os.path.splitext(path)[1]}
        if not _which(cmd[0]) and not os.path.isfile(cmd[0]):
            return {"ok": False,
                    "hata": "'%s' bulunamadi (PATH)" % cmd[0]}
        return self._run_cmd("run1", cwd, cmd)

    def calistir_icerik(self, path, content, cwd):
        """Kaydedilmemis icerigi temp dosyaya yazip calistirir."""
        try:
            ext = os.path.splitext(path or "")[1].lower() or ".py"
            d = tempfile.mkdtemp(prefix="sc_run_")
            tmp = os.path.join(d, "unsaved" + ext)
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(content or "")
            cwd = cwd or self._cwd or os.getcwd()
            cmd = self._build_cmd(tmp, cwd)
            if not cmd:
                return {"ok": False,
                        "hata": "Desteklenmeyen: %s" % ext}
            r = self._run_cmd("run1", cwd, cmd)
            if r.get("ok"):
                self._js_call("runOutput",
                              "[kaydedilmemis kopya: %s]\n" % tmp)
            return r
        except Exception as e:
            return {"ok": False, "hata": str(e)}

    def calistir_harici(self, path, cwd):
        if not path or not os.path.isfile(path):
            return {"ok": False, "hata": "Once dosyayi kaydet"}
        cwd = cwd or os.path.dirname(path) or os.getcwd()
        cmd = self._build_cmd(path, cwd)
        if not cmd:
            return {"ok": False, "hata": "Desteklenmeyen uzanti"}
        quoted = " ".join('"%s"' % c if " " in str(c) else str(c)
                          for c in cmd)
        try:
            if os.name == "nt":
                ps = (_which("pwsh") or _which("powershell")
                      or "powershell.exe")
                inner = ("Set-Location -LiteralPath '%s'; & %s; "
                         "Write-Host ''; Read-Host 'Kapatmak icin Enter'"
                         % (cwd.replace("'", "''"), quoted))
                wt = _which("wt")
                if wt:
                    c = [wt, "-d", cwd, ps, "-NoExit",
                         "-Command", inner]
                else:
                    c = ["cmd", "/c", "start", "", ps,
                         "-NoExit", "-Command", inner]
                subprocess.Popen(c, cwd=cwd,
                                 creationflags=_NO_WINDOW)
            else:
                inner = "%s; echo; read -p 'Enter...'" % quoted
                for t in ("x-terminal-emulator", "gnome-terminal",
                          "konsole", "xfce4-terminal", "xterm"):
                    if _which(t):
                        subprocess.Popen(
                            [t, "-e", "bash", "-lc", inner], cwd=cwd)
                        break
                else:
                    return {"ok": False,
                            "hata": "Terminal bulunamadi"}
            return {"ok": True}
        except Exception as e:
            _log_exc("calistir_harici", e)
            return {"ok": False, "hata": str(e)}

    def _run_cmd(self, term_id, cwd, cmd):
        with self._run_lock:
            if self._run_proc and self._run_proc.poll() is None:
                return {"ok": False,
                        "hata": "Zaten calisan bir surec var (Durdur)"}
        try:
            kw = {}
            if os.name == "nt":
                kw["creationflags"] = (
                    subprocess.CREATE_NEW_PROCESS_GROUP | _NO_WINDOW)
            else:
                kw["start_new_session"] = True
            proc = subprocess.Popen(
                cmd, cwd=cwd, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                bufsize=-1, shell=isinstance(cmd, str), **kw)
        except Exception as e:
            _log_exc("_run_cmd", e)
            return {"ok": False, "hata": str(e)}
        with self._run_lock:
            self._run_proc = proc

        def reader():
            buf, last = [], time.time()

            def flush():
                if not buf:
                    return
                txt = "".join(buf)
                buf.clear()
                self._js_call("runOutput", txt)
            try:
                while True:
                    chunk = proc.stdout.read1(65536)
                    if not chunk:
                        break
                    buf.append(chunk.decode("utf-8", "replace"))
                    if (sum(len(x) for x in buf) > 8000
                            or time.time() - last > 0.05):
                        flush()
                        last = time.time()
            except Exception as e:
                _log_warn("run reader: %s", e)
            flush()
            rc = None
            try:
                rc = proc.wait(timeout=5)
            except Exception:
                pass
            self._js_call("runOutput",
                          "\n[exit %s]\n" % ("?" if rc is None else rc))
            self._js("if(window.runDone) window.runDone();")
            with self._run_lock:
                if self._run_proc is proc:
                    self._run_proc = None
        threading.Thread(target=reader, name="sc-run",
                         daemon=True).start()
        return {"ok": True, "pid": proc.pid}

    def durdur(self):
        """Calisan sureci (ve alt sureclerini) oldurur."""
        with self._run_lock:
            p = self._run_proc
        if not p or p.poll() is not None:
            return {"ok": False, "hata": "Calisan surec yok"}
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(p.pid)],
                    capture_output=True, timeout=8,
                    creationflags=_NO_WINDOW)
            else:
                import signal
                try:
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                except Exception:
                    p.terminate()
            try:
                p.wait(timeout=3)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
            self._js_call("runOutput", "\n[durduruldu]\n")
            self._js("if(window.runDone) window.runDone();")
            return {"ok": True}
        except Exception as e:
            _log_exc("durdur", e)
            try:
                p.kill()
            except Exception:
                pass
            return {"ok": False, "hata": str(e)}
        finally:
            with self._run_lock:
                self._run_proc = None

    def debug_baslat(self, path, cwd):
        if not path or not os.path.isfile(path):
            return {"ok": False, "hata": "Dosya yok"}
        if os.path.splitext(path)[1].lower() not in (".py", ".pyw"):
            return {"ok": False, "hata": "Simdilik sadece Python"}
        cmd = '"%s" -m pdb "%s"' % (sys.executable,
                                    os.path.abspath(path))
        r = self._send_to_term(cwd, cmd)
        return {"ok": bool(r.get("ok")),
                "hata": r.get("hata", "")}

    def test_calistir(self, cwd):
        cwd = cwd or self._cwd or os.getcwd()
        if not os.path.isdir(cwd):
            return {"ok": False, "hata": "Proje yok"}
        has_pytest = any(
            os.path.exists(os.path.join(cwd, x))
            for x in ("pytest.ini", "pyproject.toml", "setup.cfg",
                      "tox.ini", "tests", "test"))
        if has_pytest:
            cmd = '"%s" -m pytest -q' % sys.executable
        else:
            cmd = '"%s" -m unittest discover -v' % sys.executable
        r = self._send_to_term(cwd, cmd)
        return {"ok": bool(r.get("ok")), "hata": r.get("hata", "")}

    # ── AI ───────────────────────────────────────────
    def ai_gonder(self, messages, context):
        s = self.settings
        provider = s.get("ai_provider", "")
        if not provider:
            return {"ok": False, "hata": "AI saglayici secilmemis"}
        msgs = []
        if context:
            msgs.append({"role": "system",
                         "content": "Asagidaki kod baglaminda "
                                    "yardimci ol:\n" + str(context)})
        msgs.extend(messages or [])
        model = s.get("ai_model", "")
        if provider == "gemini":
            return ai_gemini(s.get("ai_gemini_key", ""), model, msgs)
        if provider == "claude":
            return ai_claude(s.get("ai_claude_key", ""), model, msgs)
        return {"ok": False, "hata": "Bilinmeyen saglayici"}

    # ── Arama / TODO / Degistir ──────────────────────
    def projede_ara(self, query, cwd, use_regex=False,
                    case_sensitive=False, max_results=500):
        out = []
        if not query or not cwd:
            return out
        try:
            pattern = re.compile(
                query if use_regex else re.escape(query),
                0 if case_sensitive else re.IGNORECASE)
        except re.error:
            pattern = re.compile(re.escape(query), re.IGNORECASE)
        plain = None if use_regex else query.lower()
        try:
            for p in _iter_files(cwd):
                try:
                    with open(p, "r", encoding="utf-8",
                              errors="ignore") as f:
                        for i, ln in enumerate(f, 1):
                            if plain and plain not in ln.lower():
                                continue
                            if pattern.search(ln):
                                out.append({"path": p, "line": i,
                                            "text": ln.rstrip()[:200]})
                                if len(out) >= max_results:
                                    return out
                except Exception:
                    continue
        except Exception as e:
            _log_warn("projede_ara: %s", e)
        return out

    def projede_degistir(self, query, repl, cwd, use_regex=False,
                         case_sensitive=False, max_files=500):
        if not query or not cwd:
            return {"ok": False, "hata": "Eksik parametre"}
        try:
            pattern = re.compile(
                query if use_regex else re.escape(query),
                0 if case_sensitive else re.IGNORECASE)
        except re.error as e:
            return {"ok": False, "hata": "Regex: %s" % e}
        nrep, nfiles, errs = 0, 0, []
        try:
            for p in _iter_files(cwd):
                try:
                    with open(p, "r", encoding="utf-8",
                              errors="strict") as f:
                        src = f.read()
                except Exception:
                    continue
                new, k = pattern.subn(repl or "", src)
                if not k:
                    continue
                try:
                    fd, tmp = tempfile.mkstemp(
                        dir=os.path.dirname(p), suffix=".sctmp")
                    with os.fdopen(fd, "w", encoding="utf-8",
                                   newline="") as f:
                        f.write(new)
                    os.replace(tmp, p)
                    nrep += k
                    nfiles += 1
                except Exception as e:
                    errs.append("%s: %s" % (p, e))
                if nfiles >= max_files:
                    break
            return {"ok": True, "replacements": nrep,
                    "changed_files": nfiles, "errors": errs[:10]}
        except Exception as e:
            _log_exc("projede_degistir", e)
            return {"ok": False, "hata": str(e),
                    "replacements": nrep, "changed_files": nfiles}

    def todo_bul(self, cwd, max_results=500):
        out = []
        if not cwd:
            return out
        try:
            for p in _iter_files(cwd):
                try:
                    with open(p, "r", encoding="utf-8",
                              errors="ignore") as f:
                        for i, ln in enumerate(f, 1):
                            m = _TODO_RE.search(ln)
                            if m:
                                out.append({
                                    "tag": m.group(1), "path": p,
                                    "line": i,
                                    "text": (m.group(2) or
                                             ln.strip())[:200]})
                                if len(out) >= max_results:
                                    return out
                except Exception:
                    continue
        except Exception as e:
            _log_warn("todo_bul: %s", e)
        return out

    # ── Git ──────────────────────────────────────────
    def _git(self, cwd, args, timeout=25):
        try:
            r = _run_hidden(
                ["git", "-c", "core.quotepath=false"] + args,
                cwd=cwd, timeout=timeout)
            return {"ok": r.returncode == 0,
                    "out": r.stdout or "", "err": r.stderr or "",
                    "code": r.returncode}
        except Exception as e:
            return {"ok": False, "err": str(e), "out": "", "code": -1}

    def git_durum(self):
        if not self._cwd:
            return {"ok": False, "branch": None, "changes": []}
        b = self._git(self._cwd, ["branch", "--show-current"])
        branch = (b.get("out") or "").strip()
        if not branch:
            h = self._git(self._cwd, ["rev-parse", "--short", "HEAD"])
            branch = ("(detached %s)" % (h.get("out") or "").strip()
                      if h.get("ok") else "(repo yok)")
        st = self._git(self._cwd,
                       ["status", "--porcelain=v1", "-z",
                        "--untracked-files=all"])
        changes = []
        if st.get("ok"):
            parts = (st.get("out") or "").split("\0")
            i = 0
            while i < len(parts):
                rec = parts[i]
                i += 1
                if len(rec) < 4:
                    continue
                xy = rec[:2]
                path = rec[3:]
                orig = None
                if xy[0] in ("R", "C") or xy[1] in ("R", "C"):
                    if i < len(parts):
                        orig = parts[i]
                        i += 1
                if xy == "??":
                    label = "??"
                elif xy[0] != " ":
                    label = xy[0]
                else:
                    label = xy[1]
                changes.append({
                    "status": label, "xy": xy, "path": path,
                    "orig": orig,
                    "staged": xy[0] not in (" ", "?"),
                    "unstaged": xy[1] not in (" ", "?"),
                })
        return {"ok": st.get("ok", False), "branch": branch,
                "changes": changes}

    def git_diff(self, path=""):
        if not self._cwd:
            return {"ok": False, "diff": ""}
        args = ["diff", "--no-color"]
        if path:
            args += ["--", path]
        r = self._git(self._cwd, args)
        d = r.get("out") or ""
        if not d.strip():
            r2 = self._git(self._cwd, args[:1] + ["--cached"]
                           + args[2:])
            d = r2.get("out") or ""
        return {"ok": r.get("ok", False),
                "diff": d or "Degisiklik yok"}

    def git_commit(self, msg):
        if not self._cwd:
            return {"ok": False, "hata": "cwd yok", "err": "cwd yok"}
        if not (msg or "").strip():
            return {"ok": False, "err": "Commit mesaji bos olamaz"}
        a = self._git(self._cwd, ["add", "-A"])
        if not a["ok"]:
            return a
        return self._git(self._cwd, ["commit", "-m", msg])

    def git_push(self):
        if not self._cwd:
            return {"ok": False, "err": "cwd yok"}
        return self._git(self._cwd, ["push"], timeout=90)

    def git_pull(self):
        if not self._cwd:
            return {"ok": False, "err": "cwd yok"}
        return self._git(self._cwd, ["pull"], timeout=90)

    # ── Ikonlar / Temalar ────────────────────────────
    def ikon_haritasi_yukle(self):
        return load_icon_map()

    def ikon_haritasi_kaydet(self, m):
        ok = save_icon_map(m or {})
        clear_build_cache()
        return {"ok": ok}

    def ikon_haritasi_sifirla(self):
        try:
            if os.path.exists(ICON_MAP_FILE):
                os.remove(ICON_MAP_FILE)
        except Exception:
            pass
        clear_build_cache()
        return {"ok": True, "map": dict(DEFAULT_ICON_MAP)}

    def ikon_paketleri(self):
        return {"packs": [{"id": k, "name": v["name"],
                           "desc": v["desc"], "colors": v["colors"]}
                          for k, v in ICON_PACKS.items()],
                "current": self.settings.get("iconPack", "splash")}

    def ikon_paket_sec(self, name):
        if name not in ICON_PACKS:
            return {"ok": False, "hata": "paket yok"}
        self.settings["iconPack"] = name
        save_settings(self.settings)
        clear_build_cache()
        return {"ok": True, "pack": name,
                "colors": ICON_PACKS[name]["colors"]}

    def tema_ekle(self, name, theme):
        ok = save_user_theme(name, theme)
        clear_build_cache()
        return {"ok": ok}

    def tema_sil(self, name):
        ok = delete_user_theme(name)
        clear_build_cache()
        return {"ok": ok}

    # ── Bilgi / Temizlik ─────────────────────────────
    def bilgi(self):
        return {
            "app": APP_NAME, "version": APP_VERSION,
            "platform": sys.platform, "python": sys.version,
            "cwd": self._cwd,
            "lsp_servers": {k: bool(_which(v[0]))
                            for k, v in LSP_SERVERS.items()},
        }

    def cleanup(self):
        try:
            self.durdur()
        except Exception:
            pass
        try:
            save_session(self.session)
        except Exception:
            pass
        try:
            save_settings(self.settings)
        except Exception:
            pass
        threads = [
            threading.Thread(target=shutdown_all_lsp, daemon=True),
            threading.Thread(target=close_all_terminals, daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=6)

# ===== SC-STUDIO-008 =====
import time as _sc008_time
import tempfile as _sc008_tmp
from . import features as _sc008_f
from . import terminal as _sc008_term


def _sc008_run_baslat(self, path, content, cwd):
    try:
        cwd = cwd or self._cwd or os.getcwd()
        target = path
        if content is not None:
            ext = os.path.splitext(path or "")[1] or ".py"
            d = _sc008_tmp.mkdtemp(prefix="sc_run_")
            target = os.path.join(d, "unsaved" + ext)
            with open(target, "w", encoding="utf-8", newline="") as f:
                f.write(content)
        if not target:
            return {"ok": False, "hata": "Dosya yok"}
        cmd = _sc008_f.build_run_cmd(target, cwd)
        if not cmd:
            return {"ok": False,
                    "hata": "Desteklenmeyen uzanti: %s"
                            % os.path.splitext(target)[1]}
        r = _sc008_f.RUN.start(cmd, cwd)
        if r.get("ok"):
            r["cmd"] = " ".join(str(c) for c in cmd)
            r["file"] = target
        return r
    except Exception as e:
        return {"ok": False, "hata": str(e)}


def _sc008_run_stdin(self, data):
    return _sc008_f.RUN.send(data)


def _sc008_run_durdur(self):
    return _sc008_f.RUN.stop()


def _sc008_run_durum(self):
    return {"ok": True, "busy": _sc008_f.RUN.busy()}


def _sc008_terminal_ac(self, cwd, shell=None, name=None):
    tid = "s%d" % int(_sc008_time.time() * 1000)
    r = _sc008_term.term_spawn(tid, cwd or self._cwd or os.getcwd(), shell)
    if r.get("ok"):
        r["term_id"] = tid
        r["name"] = name or "Terminal"
        r["cwd"] = cwd or self._cwd or os.getcwd()
    return r


def _sc008_terminal_listele(self):
    try:
        return {"ok": True, "ids": list(_sc008_term._TERM_PROCS.keys())}
    except Exception:
        return {"ok": True, "ids": []}


def _sc008_izleme_poll(self, cwd, paths, dirs):
    return _sc008_f.WATCH.poll(cwd or self._cwd, paths, dirs)


def _sc008_izleme_sifirla(self):
    _sc008_f.WATCH.reset()
    return {"ok": True}


def _sc008_arama(self, query, cwd, opts):
    return _sc008_f.search(cwd or self._cwd, query, opts or {})


def _sc008_degistir(self, query, repl, cwd, opts):
    return _sc008_f.replace_all(cwd or self._cwd, query, repl, opts or {})


def _sc008_geri_al(self, backup):
    return _sc008_f.restore_backup(backup)


def _sc008_ai_stream(self, messages, context):
    s = self.settings
    provider = s.get("ai_provider", "")
    if not provider:
        return {"ok": False, "hata": "AI saglayici secilmemis"}
    msgs = []
    if context:
        msgs.append({"role": "system",
                     "content": "Asagidaki kod baglaminda yardimci ol. "
                                "Kod onerirken tam fenced blok ver:\n"
                                + str(context)})
    msgs.extend(messages or [])
    key = (s.get("ai_gemini_key", "") if provider == "gemini"
           else s.get("ai_claude_key", ""))
    return _sc008_f.AI.start(provider, key, s.get("ai_model", ""), msgs)


def _sc008_ai_durdur(self, sid):
    return _sc008_f.AI.cancel(sid)


def _sc008_font(self):
    r = _sc008_f.localize_fonts()
    try:
        clear_build_cache()
    except Exception:
        pass
    return r


def _sc008_studio_yukle(self):
    return _sc008_f.load_studio()


def _sc008_studio_kaydet(self, d):
    return {"ok": _sc008_f.save_studio(d or {})}


Api.run_baslat = _sc008_run_baslat
Api.run_stdin = _sc008_run_stdin
Api.run_durdur = _sc008_run_durdur
Api.run_durum = _sc008_run_durum
Api.terminal_ac = _sc008_terminal_ac
Api.terminal_listele = _sc008_terminal_listele
Api.izleme_poll = _sc008_izleme_poll
Api.izleme_sifirla = _sc008_izleme_sifirla
Api.arama_v2 = _sc008_arama
Api.degistir_v2 = _sc008_degistir
Api.geri_al = _sc008_geri_al
Api.ai_stream_baslat = _sc008_ai_stream
Api.ai_stream_durdur = _sc008_ai_durdur
Api.font_yerellestir = _sc008_font
Api.studio_ayar_yukle = _sc008_studio_yukle
Api.studio_ayar_kaydet = _sc008_studio_kaydet
# ===== /SC-STUDIO-008 =====

# ===== SC-STUDIO-009 =====
import re as _sc009_re
import time as _sc009_time
from . import terminal as _sc009_term


def _sc009_terminal_ac(self, cwd, shell=None, name=None, term_id=None):
    # Frontend'in istedigi id'yi KABUL ET. Onceki surum backend'de yeni id
    # uretiyordu; frontend kendi id'sine yazdigi icin her tus bos geliyordu.
    tid = str(term_id or '').strip()
    if not tid or not _sc009_re.fullmatch(r'[A-Za-z0-9_-]{1,64}', tid):
        tid = 's%d' % int(_sc009_time.time() * 1000)
    base = cwd or self._cwd or os.getcwd()
    r = _sc009_term.term_spawn(tid, base, shell)
    if r.get('ok'):
        r['term_id'] = tid
        r['name'] = name or 'Terminal'
        r['cwd'] = base
    return r


def _sc009_entry(tid):
    try:
        return _sc009_term._TERM_PROCS.get(tid)
    except Exception:
        return None


def _sc009_proc(entry):
    if entry is None:
        return None
    if isinstance(entry, dict):
        return entry.get('proc')
    return entry


def _sc009_terminal_canli(self, term_id):
    p = _sc009_proc(_sc009_entry(term_id))
    if p is None:
        return {'ok': True, 'alive': False}
    try:
        alive = bool(p.isalive())
    except Exception:
        alive = True
    return {'ok': True, 'alive': alive}


def _sc009_terminal_aktif(self, term_id):
    self._sc009_active = str(term_id or '')
    return {'ok': True}


def _sc009_send_to_term(self, cwd, cmd_text):
    # Debug / Test ciktisi GORUNEN sekmeye ve onun PTY'sine yazilir.
    tid = getattr(self, '_sc009_active', '') or 't1'
    if _sc009_entry(tid) is None:
        r = _sc009_term.term_spawn(tid, cwd or self._cwd or os.getcwd(), None)
        if not r.get('ok'):
            return r
        _sc009_time.sleep(0.7)
    line = ('& ' + cmd_text + '\r') if os.name == 'nt' else (cmd_text + '\n')
    return _sc009_term.term_write(tid, line)


def _sc009_studio_sifirla(self):
    try:
        from .features import studio_file
        p = studio_file()
        if os.path.exists(p):
            os.remove(p)
    except Exception:
        pass
    return {'ok': True}


Api.terminal_ac = _sc009_terminal_ac
Api.terminal_canli = _sc009_terminal_canli
Api.terminal_aktif_belirle = _sc009_terminal_aktif
Api._send_to_term = _sc009_send_to_term
Api.studio_ayar_sifirla = _sc009_studio_sifirla
# ===== /SC-STUDIO-009 =====

# ===== SC-STUDIO-010 =====
import os as _sc010_os
import shutil as _sc010_shutil
import subprocess as _sc010_sp
import tempfile as _sc010_tf
import threading as _sc010_th
import time as _sc010_time
import uuid as _sc010_uuid


def _sc010_harici_terminal(self, path=None, *_rest):
    # Hedef klasor: secili agac yolu -> aktif sekme -> proje kokü
    try:
        target = None
        if path:
            p = _sc010_os.path.abspath(str(path))
            if _sc010_os.path.isdir(p):
                target = p
            elif _sc010_os.path.isfile(p):
                target = _sc010_os.path.dirname(p)
        if not target:
            cp = getattr(self, "_cur_path", None)
            if cp and _sc010_os.path.exists(cp):
                target = cp if _sc010_os.path.isdir(cp) else _sc010_os.path.dirname(cp)
        if not target:
            cw = getattr(self, "_cwd", None)
            if cw and _sc010_os.path.isdir(cw):
                target = cw
        if target and not _sc010_os.path.isdir(target):
            target = None
        if _sc010_os.name == "nt":
            return _sc010_open_win(target)
        return _sc010_open_unix(target)
    except Exception as e:
        return {"ok": False, "hata": str(e)}


def _sc010_open_win(target):
    CREATE_NO_WINDOW = 0x08000000
    wt = _sc010_shutil.which("wt")
    pwsh = _sc010_shutil.which("pwsh") or _sc010_shutil.which("powershell")
    if wt:
        name = "Windows Terminal"
        term_cmd = ('"%s" -d "%s"' % (wt, target)) if target else ('"%s"' % wt)
    elif pwsh:
        name = "PowerShell"
        if target:
            term_cmd = ('"%s" -NoExit -Command "Set-Location -LiteralPath \'%s\'; Clear-Host"'
                        % (pwsh, target))
        else:
            term_cmd = '"%s" -NoExit -Command "Clear-Host"' % pwsh
    else:
        name = "CMD"
        term_cmd = ('cmd /k cd /d "%s"' % target) if target else "cmd"

    # Gecici .cmd + zamanlanmis gorev -> yetki DUSURULUR (admin -> kullanici)
    tmp = _sc010_os.path.join(_sc010_tf.gettempdir(),
                              "sc_term_%s.cmd" % _sc010_uuid.uuid4().hex)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("@echo off\n")
            f.write('start "" %s\n' % term_cmd)
        task = "SC_Term_%s" % _sc010_uuid.uuid4().hex[:10]
        deelevated = False
        try:
            _sc010_sp.run(["schtasks", "/create", "/tn", task,
                           "/tr", '"%s"' % tmp, "/sc", "once",
                           "/st", "00:00", "/f"],
                          capture_output=True, timeout=10,
                          creationflags=CREATE_NO_WINDOW)
            _sc010_sp.run(["schtasks", "/run", "/tn", task],
                          capture_output=True, timeout=10,
                          creationflags=CREATE_NO_WINDOW)
            _sc010_sp.run(["schtasks", "/delete", "/tn", task, "/f"],
                          capture_output=True, timeout=10,
                          creationflags=CREATE_NO_WINDOW)
            deelevated = True
        except Exception:
            _sc010_sp.Popen(term_cmd, shell=True)

        def _clean():
            _sc010_time.sleep(3)
            try:
                _sc010_os.remove(tmp)
            except Exception:
                pass
        _sc010_th.Thread(target=_clean, daemon=True).start()
        return {"ok": True, "terminal": name,
                "deelevated": deelevated, "dir": target}
    except Exception as e:
        return {"ok": False, "hata": str(e)}


def _sc010_open_unix(target):
    term = None
    for cand in (["x-terminal-emulator"], ["gnome-terminal"], ["konsole"],
                 ["xfce4-terminal"], ["xterm"]):
        if _sc010_shutil.which(cand[0]):
            term = cand
            break
    if not term:
        return {"ok": False, "hata": "Terminal bulunamadi"}
    args = list(term)
    if target:
        if term[0] in ("gnome-terminal", "xfce4-terminal"):
            args += ["--working-directory", target]
        elif term[0] == "konsole":
            args += ["--workdir", target]
        else:
            args += [target]
    try:
        _sc010_sp.Popen(args, cwd=target or None)
        return {"ok": True, "terminal": term[0],
                "deelevated": False, "dir": target}
    except Exception as e:
        return {"ok": False, "hata": str(e)}


Api.harici_terminal_ac = _sc010_harici_terminal
# ===== /SC-STUDIO-010 =====

# ===== SC-SESSION-014 =====
# rememberProject / rememberSession gercekten calisir

_sc014_orig_init = Api.__init__
_sc014_orig_klasor_sec = Api.klasor_sec
_sc014_orig_oturum_yukle = Api.oturum_yukle
_sc014_orig_oturum_kaydet = Api.oturum_kaydet


def _sc014_init(self):
    _sc014_orig_init(self)
    # rememberProject kapaliysa _cwd yukleme
    if not self.settings.get("rememberProject", True):
        self._cwd = None


def _sc014_klasor_sec(self):
    r = _sc014_orig_klasor_sec(self)
    # rememberProject kapaliysa lastProject'i kaldir
    if isinstance(r, dict) and r.get("ok"):
        if not self.settings.get("rememberProject", True):
            self.settings["lastProject"] = None
            try:
                save_settings(self.settings)
            except Exception:
                pass
    return r


def _sc014_oturum_yukle(self):
    if not self.settings.get("rememberSession", True):
        return {"cwd": None, "tabs": [], "activeTab": None,
                "recentFiles": []}
    sess = _sc014_orig_oturum_yukle(self)
    # rememberProject kapaliysa cwd'i de kaldir
    if not self.settings.get("rememberProject", True):
        sess = dict(sess)
        sess["cwd"] = None
    return sess


def _sc014_oturum_kaydet(self, s):
    if not self.settings.get("rememberSession", True):
        self.session = {"cwd": None, "tabs": [], "activeTab": None,
                        "recentFiles": []}
        try:
            save_session(self.session)
        except Exception:
            pass
        return {"ok": True, "skipped": True}
    return _sc014_orig_oturum_kaydet(self, s)


Api.__init__ = _sc014_init
Api.klasor_sec = _sc014_klasor_sec
Api.oturum_yukle = _sc014_oturum_yukle
Api.oturum_kaydet = _sc014_oturum_kaydet
# ===== /SC-SESSION-014 =====
# ===== SC-015 =====
# rememberProject / rememberSession GERCEKTEN uygulanir.
# Oncesi: bu iki ayar sadece kaydediliyordu, hicbir yerde
#         kontrol edilmiyordu. Simdi her nokta denetleniyor.

_sc015_orig_ayarlari_kaydet = Api.ayarlari_kaydet
_sc015_orig_klasor_sec      = Api.klasor_sec
_sc015_orig_oturum_yukle    = Api.oturum_yukle
_sc015_orig_oturum_kaydet   = Api.oturum_kaydet
_sc015_orig_bilgi           = Api.bilgi

_SC015_EMPTY_SESSION = {
    "cwd": None, "tabs": [], "activeTab": None,
    "recentFiles": [],
}


def _sc015_ayarlari_kaydet(self, s):
    data = dict(s or {})
    # rememberProject kapatildi -> lastProject silinir
    rp = data.get("rememberProject",
                  self.settings.get("rememberProject", True))
    if not rp:
        data["lastProject"] = None
    result = _sc015_orig_ayarlari_kaydet(self, data)
    # rememberSession kapatildi -> oturum dosyasi temizlenir
    rs = self.settings.get("rememberSession", True)
    if not rs:
        self.session = dict(_SC015_EMPTY_SESSION)
        try:
            save_session(self.session)
        except Exception:
            pass
    return result


def _sc015_klasor_sec(self):
    result = _sc015_orig_klasor_sec(self)
    # rememberProject kapaliysa lastProject kalici olmaz
    if isinstance(result, dict) and result.get("ok"):
        if not self.settings.get("rememberProject", True):
            self.settings["lastProject"] = None
            try:
                save_settings(self.settings)
            except Exception:
                pass
    return result


def _sc015_oturum_yukle(self):
    if not self.settings.get("rememberSession", True):
        return dict(_SC015_EMPTY_SESSION)
    return _sc015_orig_oturum_yukle(self)


def _sc015_oturum_kaydet(self, s):
    if not self.settings.get("rememberSession", True):
        return {"ok": True, "skipped": True}
    return _sc015_orig_oturum_kaydet(self, s)


def _sc015_bilgi(self):
    result = _sc015_orig_bilgi(self)
    # rememberProject kapaliysa frontend tree yuklemesin
    if isinstance(result, dict):
        if not self.settings.get("rememberProject", True):
            result["cwd"] = None
    return result


Api.ayarlari_kaydet = _sc015_ayarlari_kaydet
Api.klasor_sec      = _sc015_klasor_sec
Api.oturum_yukle    = _sc015_oturum_yukle
Api.oturum_kaydet   = _sc015_oturum_kaydet
Api.bilgi           = _sc015_bilgi
# ===== /SC-015 =====
# ===== SC-SPLIT-021 =====
import os as _sc021_os


def _sc021_split_temp_olustur(self, path, content):
    try:
        dirname = _sc021_os.path.dirname(path)
        basename = _sc021_os.path.basename(path)
        name, ext = _sc021_os.path.splitext(basename)
        temp_name = name + "_temp" + ext
        temp_path = _sc021_os.path.join(dirname, temp_name)
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"ok": True, "path": temp_path, "name": temp_name,
                "lang": get_lang(temp_path)}
    except Exception as e:
        return {"ok": False, "hata": str(e)}


def _sc021_split_temp_sil(self, path):
    try:
        if path and _sc021_os.path.exists(path):
            _sc021_os.remove(path)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "hata": str(e)}


Api.split_temp_olustur = _sc021_split_temp_olustur
Api.split_temp_sil = _sc021_split_temp_sil
# ===== /SC-SPLIT-021 =====
# ===== SC-LSP-022 =====
# LSP tamamlama kind fix + tree-sitter + resolve + debounce

import re as _sc022_re
import time as _sc022_time
import json as _sc022_json

# --- Completion kind categorization for fake_complete ---
_SC022_KEYWORDS = {
    "python": {"def", "class", "import", "from", "as", "return", "yield",
               "if", "elif", "else", "for", "while", "break", "continue",
               "pass", "try", "except", "finally", "with", "async", "await",
               "lambda", "global", "nonlocal", "assert", "del", "raise",
               "in", "is", "not", "and", "or", "True", "False", "None"},
    "javascript": {"function", "const", "let", "var", "if", "else", "for",
                   "while", "do", "switch", "case", "break", "continue",
                   "return", "true", "false", "null", "undefined", "new",
                   "this", "class", "extends", "super", "async", "await",
                   "try", "catch", "finally", "throw", "typeof", "instanceof"},
    "typescript": {"function", "const", "let", "var", "if", "else", "for",
                   "while", "return", "true", "false", "null", "undefined",
                   "new", "this", "class", "extends", "interface", "type",
                   "enum", "namespace", "async", "await", "readonly",
                   "private", "public", "protected", "abstract", "implements"},
}
_SC022_FUNCTIONS = {
    "python": {"print", "input", "len", "range", "str", "int", "float",
               "list", "dict", "set", "tuple", "bool", "type", "isinstance",
               "getattr", "setattr", "hasattr", "open", "enumerate", "zip",
               "map", "filter", "sorted", "reversed", "sum", "min", "max",
               "abs", "round", "pow", "hex", "oct", "bin", "chr", "ord",
               "repr", "hash", "id", "iter", "next", "all", "any", "callable",
               "vars", "dir", "super", "object", "format"},
    "javascript": {"console", "document", "window", "navigator", "setTimeout",
                   "setInterval", "clearTimeout", "clearInterval", "parseInt",
                   "parseFloat", "isNaN", "isFinite", "fetch", "alert",
                   "confirm", "prompt", "atob", "btoa"},
}
_SC022_CONSTANTS = {
    "python": {"True", "False", "None", "__name__", "__main__", "__init__"},
    "javascript": {"true", "false", "null", "undefined", "NaN", "Infinity"},
}

def _sc022_categorize(word, lang):
    """Return LSP completion kind (1-25) for a word."""
    kw = _SC022_KEYWORDS.get(lang, set())
    fn = _SC022_FUNCTIONS.get(lang, set())
    cn = _SC022_CONSTANTS.get(lang, set())
    if word in kw:
        return 14  # Keyword
    if word in cn:
        return 21  # Constant
    if word in fn:
        return 3   # Function
    if word.startswith('_') and word.endswith('_'):
        return 14  # dunder -> Keyword
    if word[0:1].isupper():
        return 7   # Class
    return 6       # Variable

# Override fake_complete to include kind
_sc022_orig_fake_complete = Api.fake_complete

def _sc022_fake_complete(self, lang, text, line, col):
    try:
        lines = text.split("\n") if text else []
        prefix = ""
        if 0 <= line < len(lines):
            prefix = lines[line][:col]
        m = _sc022_re.search(r"([A-Za-z_][A-Za-z0-9_]*)$", prefix)
        word = m.group(1) if m else ""
        if not word:
            return []
        wl = word.lower()
        candidates = []
        for b in BUILTINS.get(lang, []):
            if b.lower().startswith(wl) and b != word:
                kind = _sc022_categorize(b, lang)
                candidates.append({
                    "label": b, "insertText": b,
                    "sortText": "0_" + b, "kind": kind,
                    "detail": "builtin",
                })
        words = set(_sc022_re.findall(
            r"[A-Za-z_][A-Za-z0-9_]{2,}", text or ""))
        for w in sorted(words):
            if (w.lower().startswith(wl) and w != word
                    and w not in BUILTINS.get(lang, [])):
                kind = _sc022_categorize(w, lang)
                candidates.append({
                    "label": w, "insertText": w,
                    "sortText": "1_" + w, "kind": kind,
                    "detail": "local",
                })
        return candidates[:80]
    except Exception:
        return []

Api.fake_complete = _sc022_fake_complete

# --- LSP completion resolve + debounce ---
_sc022_lsp_cache = {}
_SC022_DEBOUNCE = 0.25  # seconds

def _sc022_lsp_complete(self, lang, uri, text, line, col):
    """Optimized LSP completion with resolve."""
    try:
        c = get_lsp(lang, self._cwd)
        if not c.proc:
            return {"items": []}
        items = c.completion(uri, line, col, text)
        if not items:
            return {"items": []}
        # Resolve top items to get kind/detail if missing
        resolved = []
        for item in items[:60]:
            if item.get("kind") is None or item.get("kind") == 0:
                # Try resolve
                try:
                    resp = c._request("completionItem/resolve", item, timeout=2)
                    if resp and resp.get("result"):
                        item = resp["result"]
                except Exception:
                    pass
            if item.get("kind") is None:
                item["kind"] = _sc022_categorize(
                    item.get("label", ""), lang)
            resolved.append(item)
        return {"items": resolved}
    except Exception:
        return {"items": []}

Api.lsp_complete = _sc022_lsp_complete

# --- Tree-sitter API (Python ast + regex fallback) ---
def _sc022_treesitter_parse(self, lang, code):
    """Parse code and return symbols (functions, classes, variables)."""
    try:
        if lang == "python":
            import ast
            tree = ast.parse(code)
            symbols = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    symbols.append({"name": node.name, "kind": 12,
                                    "line": node.lineno, "type": "function"})
                elif isinstance(node, ast.AsyncFunctionDef):
                    symbols.append({"name": node.name, "kind": 12,
                                    "line": node.lineno, "type": "function"})
                elif isinstance(node, ast.ClassDef):
                    symbols.append({"name": node.name, "kind": 5,
                                    "line": node.lineno, "type": "class"})
                elif isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            symbols.append({"name": t.id, "kind": 13,
                                            "line": node.lineno, "type": "variable"})
            return {"ok": True, "symbols": symbols}
        else:
            # Regex fallback for other languages
            symbols = []
            for m in _sc022_re.finditer(
                r'^\s*(?:function|def|fn|func)\s+(\w+)', code, _sc022_re.M):
                symbols.append({"name": m.group(1), "kind": 12,
                                "line": code[:m.start()].count('\n') + 1,
                                "type": "function"})
            for m in _sc022_re.finditer(
                r'^\s*(?:class|struct|interface)\s+(\w+)', code, _sc022_re.M):
                symbols.append({"name": m.group(1), "kind": 5,
                                "line": code[:m.start()].count('\n') + 1,
                                "type": "class"})
            for m in _sc022_re.finditer(
                r'^\s*(?:const|let|var|val)\s+(\w+)', code, _sc022_re.M):
                symbols.append({"name": m.group(1), "kind": 13,
                                "line": code[:m.start()].count('\n') + 1,
                                "type": "variable"})
            return {"ok": True, "symbols": symbols}
    except SyntaxError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

Api.treesitter_parse = _sc022_treesitter_parse

def _sc022_treesitter_bracket(self, code, line, col):
    """Find matching bracket for position."""
    try:
        lines = code.split("\n")
        if line >= len(lines):
            return {"ok": False}
        text = lines[line]
        if col >= len(text):
            return {"ok": False}
        char = text[col]
        open_brackets = "([{<"
        close_brackets = ")]}>"
        if char not in open_brackets + close_brackets:
            # Check adjacent
            if col + 1 < len(text) and text[col + 1] in open_brackets + close_brackets:
                col += 1
                char = text[col]
            else:
                return {"ok": False}
        is_open = char in open_brackets
        match_char = close_brackets[open_brackets.index(char)] if is_open else open_brackets[close_brackets.index(char)]
        # Search forward/backward
        depth = 0
        if is_open:
            for l in range(line, len(lines)):
                start_col = col if l == line else 0
                for c in range(start_col, len(lines[l])):
                    if lines[l][c] == char:
                        depth += 1
                    elif lines[l][c] == match_char:
                        depth -= 1
                        if depth == 0:
                            return {"ok": True, "line": l, "col": c}
        else:
            for l in range(line, -1, -1):
                start_col = col if l == line else len(lines[l]) - 1
                for c in range(start_col, -1, -1):
                    if lines[l][c] == char:
                        depth += 1
                    elif lines[l][c] == match_char:
                        depth -= 1
                        if depth == 0:
                            return {"ok": True, "line": l, "col": c}
        return {"ok": False}
    except Exception:
        return {"ok": False}

Api.treesitter_bracket = _sc022_treesitter_bracket
# ===== /SC-LSP-022 =====
# ===== SC-TS-023 =====
# Tree-Sitter gercek entegrasyon + fallback

_SC023_TS = None
_SC023_TS_MODE = "yok"

# 1) tree_sitter_languages dene (40+ dil, tek paket)
try:
    import tree_sitter_languages as _sc023_tsl
    _SC023_TS = _sc023_tsl
    _SC023_TS_MODE = "tree_sitter_languages"
except ImportError:
    _sc023_tsl = None

# 2) Yoksa bireysel tree-sitter + dil paketleri dene
if _SC023_TS is None:
    try:
        import tree_sitter as _sc023_ts_core
        _SC023_TS = _sc023_ts_core
        _SC023_TS_MODE = "tree_sitter_core"
    except ImportError:
        _sc023_ts_core = None

# Monaco dil ID -> tree-sitter dil adi
_SC023_LANG_MAP = {
    "python": "python", "javascript": "javascript",
    "typescript": "typescript", "tsx": "tsx", "jsx": "javascript",
    "html": "html", "css": "css", "json": "json",
    "rust": "rust", "go": "go", "java": "java",
    "c": "c", "cpp": "cpp", "csharp": "c_sharp",
    "php": "php", "ruby": "ruby", "lua": "lua",
    "shell": "bash", "bash": "bash", "powershell": "powershell",
    "yaml": "yaml", "markdown": "markdown", "sql": "sql",
    "kotlin": "kotlin", "swift": "swift", "dart": "dart",
    "scala": "scala", "haskell": "haskell", "elixir": "elixir",
    "erlang": "erlang", "clojure": "clojure", "perl": "perl",
    "r": "r", "toml": "toml", "ini": "ini", "xml": "xml",
    "proto": "proto", "graphql": "graphql", "dockerfile": "dockerfile",
    "makefile": "makefile", "cmake": "cmake", "zig": "zig",
    "nim": "nim", "fortran": "fortran", "verilog": "verilog",
    "vhdl": "vhdl", "bat": "batch", "scss": "css", "less": "css",
    "plaintext": None,
}

# Dil -> sembol node tipleri
_SC023_SYMBOL_NODES = {
    "python": {
        "function": ["function_definition"],
        "class": ["class_definition"],
        "variable": ["assignment"],
        "import": ["import_statement", "import_from_statement"],
    },
    "javascript": {
        "function": ["function_declaration", "arrow_function",
                      "function_expression", "method_definition"],
        "class": ["class_declaration"],
        "variable": ["variable_declaration", "lexical_declaration"],
        "import": ["import_statement"],
    },
    "typescript": {
        "function": ["function_declaration", "arrow_function",
                      "function_expression", "method_definition"],
        "class": ["class_declaration"],
        "variable": ["variable_declaration", "lexical_declaration"],
        "import": ["import_statement"],
        "interface": ["interface_declaration"],
        "type": ["type_alias_declaration"],
        "enum": ["enum_declaration"],
    },
    "go": {
        "function": ["function_declaration", "method_declaration"],
        "class": ["type_declaration"],
        "variable": ["var_declaration", "const_declaration"],
        "import": ["import_declaration"],
    },
    "rust": {
        "function": ["function_item"],
        "class": ["struct_item", "enum_item", "trait_item", "impl_item"],
        "variable": ["let_declaration"],
        "import": ["use_declaration"],
    },
    "java": {
        "function": ["method_declaration", "constructor_declaration"],
        "class": ["class_declaration", "interface_declaration",
                   "enum_declaration"],
        "variable": ["field_declaration", "local_variable_declaration"],
        "import": ["import_declaration"],
    },
    "c": {
        "function": ["function_definition"],
        "class": ["struct_specifier", "enum_specifier"],
        "variable": ["declaration", "init_declarator"],
    },
    "cpp": {
        "function": ["function_definition"],
        "class": ["class_specifier", "struct_specifier"],
        "variable": ["declaration", "init_declarator"],
    },
    "csharp": {
        "function": ["method_declaration"],
        "class": ["class_declaration", "interface_declaration"],
        "variable": ["field_declaration", "local_declaration_statement"],
    },
    "ruby": {
        "function": ["method"],
        "class": ["class", "module"],
        "variable": ["assignment"],
    },
    "php": {
        "function": ["function_definition", "method_declaration"],
        "class": ["class_declaration", "interface_declaration"],
        "variable": ["expression_statement"],
    },
    "lua": {
        "function": ["function_declaration", "function_definition"],
        "variable": ["variable_declaration", "assignment_statement"],
    },
    "shell": {
        "function": ["function_definition"],
        "variable": ["variable_assignment"],
    },
    "bash": {
        "function": ["function_definition"],
        "variable": ["variable_assignment"],
    },
}

_SC023_parser_cache = {}


def _sc023_get_parser(lang):
    ts_lang = _SC023_LANG_MAP.get(lang)
    if not ts_lang:
        return None
    if ts_lang in _SC023_parser_cache:
        return _SC023_parser_cache[ts_lang]
    try:
        if _SC023_TS_MODE == "tree_sitter_languages":
            p = _SC023_TS.get_parser(ts_lang)
            _SC023_parser_cache[ts_lang] = p
            return p
        elif _SC023_TS_MODE == "tree_sitter_core":
            # Bireysel dil paketleri: tree_sitter_python vs.
            mod_name = "tree_sitter_" + ts_lang.replace("-", "_")
            try:
                import importlib
                mod = importlib.import_module(mod_name)
                lang_obj = _sc023_ts_core.Language(mod.language())
                p = _sc023_ts_core.Parser(lang_obj)
                _SC023_parser_cache[ts_lang] = p
                return p
            except (ImportError, Exception):
                return None
    except Exception:
        return None
    return None


def _sc023_extract_name(node, code_bytes):
    for child in node.children:
        if child.type in ("identifier", "name", "type_identifier",
                          "property_identifier", "field_identifier"):
            return code_bytes[child.start_byte:child.end_byte].decode(
                "utf-8", "replace")
    # İlk identifier'i bul
    text = code_bytes[node.start_byte:node.end_byte].decode(
        "utf-8", "replace")
    import re as _re023
    m = _re023.search(r"[A-Za-z_][A-Za-z0-9_]*", text)
    return m.group(0) if m else None


def _sc023_ts_parse(lang, code):
    parser = _sc023_get_parser(lang)
    if not parser:
        return None
    try:
        code_bytes = code.encode("utf-8") if isinstance(code, str) else code
        tree = parser.parse(code_bytes)
        root = tree.root_node
        ts_lang = _SC023_LANG_MAP.get(lang, lang)
        node_map = _SC023_SYMBOL_NODES.get(ts_lang, {})
        symbols = []
        seen = set()

        def walk(node, depth=0):
            if depth > 20:
                return
            for sym_type, node_types in node_map.items():
                if node.type in node_types:
                    name = _sc023_extract_name(node, code_bytes)
                    if name and name not in seen:
                        seen.add(name)
                        symbols.append({
                            "name": name,
                            "type": sym_type,
                            "line": node.start_point[0] + 1,
                            "col": node.start_point[1],
                            "end_line": node.end_point[0] + 1,
                            "kind": {"function": 12, "class": 5,
                                     "variable": 13, "import": 2,
                                     "interface": 11, "type": 22,
                                     "enum": 13}.get(sym_type, 13),
                        })
            for child in node.children:
                walk(child, depth + 1)

        walk(root)
        return {"ok": True, "engine": "tree-sitter",
                "symbols": symbols, "error_count": root.error_count}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _sc023_ast_parse(lang, code):
    import re as _re023
    symbols = []
    if lang == "python":
        try:
            import ast as _ast023
            tree = _ast023.parse(code)
            for node in _ast023.walk(tree):
                if isinstance(node, (_ast023.FunctionDef,
                                     _ast023.AsyncFunctionDef)):
                    symbols.append({"name": node.name, "type": "function",
                                    "line": node.lineno, "col": node.col_offset,
                                    "end_line": getattr(node, "end_lineno", node.lineno),
                                    "kind": 12})
                elif isinstance(node, _ast023.ClassDef):
                    symbols.append({"name": node.name, "type": "class",
                                    "line": node.lineno, "col": node.col_offset,
                                    "end_line": getattr(node, "end_lineno", node.lineno),
                                    "kind": 5})
                elif isinstance(node, _ast023.Assign):
                    for t in node.targets:
                        if isinstance(t, _ast023.Name):
                            symbols.append({"name": t.id, "type": "variable",
                                            "line": node.lineno, "col": node.col_offset,
                                            "end_line": node.lineno, "kind": 13})
            return {"ok": True, "engine": "python-ast",
                    "symbols": symbols, "error_count": 0}
        except SyntaxError as e:
            return {"ok": False, "error": str(e), "symbols": []}
    else:
        # Regex fallback
        patterns = [
            (r"^\s*(?:def|function|fn|func|sub)\s+([A-Za-z_]\w*)", "function", 12),
            (r"^\s*(?:class|struct|interface|enum|type)\s+([A-Za-z_]\w*)", "class", 5),
            (r"^\s*(?:const|let|var|val)\s+([A-Za-z_]\w*)", "variable", 13),
        ]
        for pat, stype, kind in patterns:
            for m in _re023.finditer(pat, code, _re023.M):
                line = code[:m.start()].count("\n") + 1
                symbols.append({"name": m.group(1), "type": stype,
                                "line": line, "col": m.start(),
                                "end_line": line, "kind": kind})
        return {"ok": True, "engine": "regex",
                "symbols": symbols, "error_count": 0}


def _sc023_treesitter_parse(self, lang, code):
    result = _sc023_ts_parse(lang, code)
    if result and result.get("ok"):
        return result
    return _sc023_ast_parse(lang, code)


def _sc023_treesitter_bracket(self, code, line, col):
    parser = _sc023_get_parser("python")  # dil farketmez, genel
    if parser:
        try:
            code_bytes = code.encode("utf-8") if isinstance(code, str) else code
            tree = parser.parse(code_bytes)
            # Brute force: node'u bul, parent'ta eslesen bracket'i ara
        except Exception:
            pass
    # Manuel bracket matching (tum dillerde calisir)
    try:
        lines = code.split("\n")
        if line >= len(lines):
            return {"ok": False}
        text = lines[line]
        if col >= len(text):
            return {"ok": False}
        char = text[col]
        opens = "([{"
        closes = ")]}"
        if char not in opens + closes:
            if col + 1 < len(text) and text[col + 1] in opens + closes:
                col += 1
                char = text[col]
            elif col > 0 and text[col - 1] in opens + closes:
                col -= 1
                char = text[col]
            else:
                return {"ok": False}
        is_open = char in opens
        match_char = closes[opens.index(char)] if is_open else opens[closes.index(char)]
        depth = 0
        if is_open:
            for l in range(line, len(lines)):
                sc = col if l == line else 0
                for c in range(sc, len(lines[l])):
                    if lines[l][c] == char:
                        depth += 1
                    elif lines[l][c] == match_char:
                        depth -= 1
                        if depth == 0:
                            return {"ok": True, "line": l, "col": c}
        else:
            for l in range(line, -1, -1):
                sc = col if l == line else len(lines[l]) - 1
                for c in range(sc, -1, -1):
                    if lines[l][c] == char:
                        depth += 1
                    elif lines[l][c] == match_char:
                        depth -= 1
                        if depth == 0:
                            return {"ok": True, "line": l, "col": c}
        return {"ok": False}
    except Exception:
        return {"ok": False}


def _sc023_treesitter_durum(self):
    return {
        "ok": True,
        "mode": _SC023_TS_MODE,
        "available": _SC023_TS_MODE != "yok",
        "langs": list(_SC023_LANG_MAP.keys()),
    }


Api.treesitter_parse = _sc023_treesitter_parse
Api.treesitter_bracket = _sc023_treesitter_bracket
Api.treesitter_durum = _sc023_treesitter_durum
# ===== /SC-TS-023 =====
# ===== SC-I18N-026 =====
from .i18n import LANGS as _SC026_LANGS, get_translations as _sc026_get_tr

def _sc026_dil_listesi(self):
    return {"ok": True, "langs": _SC026_LANGS}

def _sc026_dil_yukle(self, lang):
    tr = _sc026_get_tr(lang)
    return {"ok": True, "lang": lang, "t": tr}

def _sc026_dil_degistir(self, lang):
    self.settings["language"] = lang
    try:
        save_settings(self.settings)
    except Exception:
        pass
    return {"ok": True, "lang": lang}

Api.dil_listesi = _sc026_dil_listesi
Api.dil_yukle = _sc026_dil_yukle
Api.dil_degistir = _sc026_dil_degistir
# ===== /SC-I18N-026 =====
# ===== SC-TERM-028 =====
# Harici terminal: schtasks/.cmd YOK, dogrudan Popen (liste) -> tirnak/path ezilmez.
# target yoksa cd atmadan direkt terminal acar.
import os as _sc028_os
import shutil as _sc028_shutil
import subprocess as _sc028_sp


def _sc028_open_win(target):
    wt = _sc028_shutil.which("wt")
    pwsh = _sc028_shutil.which("pwsh") or _sc028_shutil.which("powershell")

    # 1) Windows Terminal (en temiz)
    if wt:
        args = [wt]
        if target:
            args += ["-d", target]
        try:
            _sc028_sp.Popen(args)
            return {"ok": True, "terminal": "Windows Terminal",
                    "deelevated": False, "dir": target}
        except Exception:
            pass

    # 2) PowerShell
    if pwsh:
        args = [pwsh, "-NoExit", "-NoLogo"]
        if target:
            safe = target.replace("'", "''")
            args += ["-Command", "Set-Location -LiteralPath '" + safe + "'"]
        try:
            _sc028_sp.Popen(args)
            return {"ok": True, "terminal": "PowerShell",
                    "deelevated": False, "dir": target}
        except Exception:
            pass

    # 3) CMD fallback
    if target:
        args = ["cmd", "/k", 'cd /d "' + target + '"']
    else:
        args = ["cmd"]
    try:
        _sc028_sp.Popen(args)
        return {"ok": True, "terminal": "CMD",
                "deelevated": False, "dir": target}
    except Exception as e:
        return {"ok": False, "hata": str(e)}


def _sc028_open_unix(target):
    term = None
    for cand in (["x-terminal-emulator"], ["gnome-terminal"], ["konsole"],
                 ["xfce4-terminal"], ["xterm"]):
        if _sc028_shutil.which(cand[0]):
            term = cand
            break
    if not term:
        return {"ok": False, "hata": "Terminal bulunamadi"}
    args = list(term)
    if target:
        if term[0] in ("gnome-terminal", "xfce4-terminal"):
            args += ["--working-directory", target]
        elif term[0] == "konsole":
            args += ["--workdir", target]
        else:
            args += [target]
    try:
        _sc028_sp.Popen(args)
        return {"ok": True, "terminal": term[0],
                "deelevated": False, "dir": target}
    except Exception as e:
        return {"ok": False, "hata": str(e)}


def _sc028_harici_terminal(self, path=None, *_rest):
    try:
        target = None
        if path:
            p = _sc028_os.path.abspath(str(path))
            if _sc028_os.path.isdir(p):
                target = p
            elif _sc028_os.path.isfile(p):
                target = _sc028_os.path.dirname(p)
        if not target:
            cp = getattr(self, "_cur_path", None)
            if cp and _sc028_os.path.exists(cp):
                target = cp if _sc028_os.path.isdir(cp) else _sc028_os.path.dirname(cp)
        if not target:
            cw = getattr(self, "_cwd", None)
            if cw and _sc028_os.path.isdir(cw):
                target = cw
        if target and not _sc028_os.path.isdir(target):
            target = None
        if _sc028_os.name == "nt":
            return _sc028_open_win(target)
        return _sc028_open_unix(target)
    except Exception as e:
        return {"ok": False, "hata": str(e)}


Api.harici_terminal_ac = _sc028_harici_terminal
# ===== /SC-TERM-028 =====
# ===== SC-TOOLS-029 =====
from . import tools as _sc029_tools
from .lsp_client import get_lsp as _sc029_get_lsp


def _sc029_todo_listele(self, cwd=None, include_project=True):
    return _sc029_tools.list_todos(cwd or self._cwd, include_project)


def _sc029_todo_ekle(self, text, cwd=None):
    return _sc029_tools.add_todo(text, cwd or self._cwd)


def _sc029_todo_toggle(self, tid):
    return _sc029_tools.toggle_todo(tid)


def _sc029_todo_sil(self, tid):
    return _sc029_tools.delete_todo(tid)


def _sc029_sorunlar(self, path, lang, text, uri):
    lsp_items = []
    lint_issues = []
    try:
        if self.settings.get("diagnosticsEnabled", True):
            r = self.lsp_diagnostics(lang, uri)
            lsp_items = (r or {}).get("items") or []
    except Exception:
        pass
    try:
        fn = getattr(self, "lint_dosya", None)
        if fn and path:
            r = fn(path)
            lint_issues = (r or {}).get("issues") or []
    except Exception:
        pass
    local = _sc029_tools.local_problems(path, lang, text)
    items = _sc029_tools.normalize_problems(lsp_items, lint_issues, local)
    return {"ok": True, "items": items}


def _sc029_referanslar(self, lang, uri, text, line, col, cwd=None):
    items = []
    try:
        c = _sc029_get_lsp(lang, self._cwd)
        if c and c.proc and c.initialize():
            sync = getattr(c, "_sync", None) or c.did_change
            sync(uri, text)
            r = c._request("textDocument/references", {
                "textDocument": {"uri": uri},
                "position": {"line": line, "character": col},
                "context": {"includeDeclaration": True},
            }, timeout=8)
            res = (r or {}).get("result") or []
            for it in res:
                rg = (it.get("range") or {}).get("start") or {}
                items.append({
                    "uri": it.get("uri"), "path": it.get("uri"),
                    "line": rg.get("line", 0) + 1,
                    "col": rg.get("character", 0), "text": "",
                })
    except Exception:
        pass
    if not items:
        word = _sc029_tools.word_at(text, line, col)
        items = _sc029_tools.find_word_refs(cwd or self._cwd, word)
        return {"ok": True, "items": items, "engine": "local", "word": word}
    return {"ok": True, "items": items, "engine": "lsp"}


def _sc029_test_baslat(self, cwd=None):
    return _sc029_tools.TESTS.start(cwd or self._cwd)


def _sc029_test_durdur(self):
    return _sc029_tools.TESTS.stop()


def _sc029_test_durum(self):
    return {"ok": True, "busy": _sc029_tools.TESTS.busy()}


Api.todo_listele = _sc029_todo_listele
Api.todo_ekle = _sc029_todo_ekle
Api.todo_toggle = _sc029_todo_toggle
Api.todo_sil = _sc029_todo_sil
Api.sorunlar_tara = _sc029_sorunlar
Api.referanslar = _sc029_referanslar
Api.test_baslat = _sc029_test_baslat
Api.test_durdur = _sc029_test_durdur
Api.test_durum = _sc029_test_durum
# ===== /SC-TOOLS-029 =====
# ===== SC-TOOLS-030 =====
from . import tools30 as _t30

_sc30_orig_list_dir = Api._list_dir


def _sc30_split_yaz(self, path, content):
    return _t30.temp_write(path, content)


def _sc30_split_sil(self, path):
    return _t30.temp_delete(path)


def _sc30_split_temizle(self, folder=None):
    return _t30.temp_cleanup(folder or self._cwd)


def _sc30_debug_baslat(self, path, cwd=None):
    return _t30.DEBUG.start(path, cwd or self._cwd)


def _sc30_debug_komut(self, text):
    return _t30.DEBUG.send(text)


def _sc30_debug_durdur(self):
    return _t30.DEBUG.stop()


def _sc30_debug_durum(self):
    return {"ok": True, "busy": _t30.DEBUG.busy(),
            "file": _t30.DEBUG.file}


def _sc30_sorunlar(self, path, lang, text, uri):
    lsp_items, lint_issues = [], []
    try:
        if self.settings.get("diagnosticsEnabled", True):
            fn = getattr(self, "lsp_diagnostics", None)
            if fn:
                r = fn(lang, uri)
                lsp_items = (r or {}).get("items") or []
    except Exception:
        pass
    try:
        fn = getattr(self, "lint_dosya", None)
        if fn and path:
            r = fn(path)
            lint_issues = (r or {}).get("issues") or []
    except Exception:
        pass
    try:
        local = _t30.local_problems(path, lang, text)
    except Exception:
        local = []
    items = _t30.merge_problems(lsp_items, lint_issues, local)
    return {"ok": True, "items": items,
            "sources": {"lsp": len(lsp_items), "lint": len(lint_issues),
                        "local": len(local)}}


def _sc30_list_dir(self, cwd, top=False, max_items=5000):
    out = _sc30_orig_list_dir(self, cwd, top=top, max_items=max_items)
    try:
        out = [x for x in out if not _t30.is_temp_name(x.get("name"))]
    except Exception:
        pass
    return out


Api.split_temp_yaz = _sc30_split_yaz
Api.split_temp_sil = _sc30_split_sil
Api.split_temp_temizle = _sc30_split_temizle
Api.debug_baslat = _sc30_debug_baslat
Api.debug_komut = _sc30_debug_komut
Api.debug_durdur = _sc30_debug_durdur
Api.debug_durum = _sc30_debug_durum
Api.sorunlar_tara = _sc30_sorunlar
Api._list_dir = _sc30_list_dir
# ===== /SC-TOOLS-030 =====
# ===== SC-SPLIT-031 =====
from . import split031 as _s31

_s31_orig_list_dir = Api._list_dir


def _s31_calistir(self, src, content, cwd=None):
    return _s31.RUN.start(src, content, cwd or self._cwd)


def _s31_durdur(self):
    return _s31.RUN.stop()


def _s31_durum(self):
    return {"ok": True, "busy": _s31.RUN.busy()}


def _s31_sil(self, path):
    return _s31.delete_temp(path)


def _s31_yaz(self, src, content):
    return _s31.write_temp(src, content)


def _s31_list_dir(self, cwd, top=False, max_items=5000):
    out = _s31_orig_list_dir(self, cwd, top=top, max_items=max_items)
    try:
        out = [x for x in out if not _s31.is_temp(x.get("name"))]
    except Exception:
        pass
    return out


Api.split031_calistir = _s31_calistir
Api.split031_durdur = _s31_durdur
Api.split031_durum = _s31_durum
Api.split031_sil = _s31_sil
Api.split031_yaz = _s31_yaz
Api._list_dir = _s31_list_dir
# ===== /SC-SPLIT-031 =====
# ===== SC-SPLIT-032 =====
from . import split032 as _s32

_s32_orig_list_dir = Api._list_dir


def _s32_run(self, src, content, cwd=None):
    return _s32.RUN.start(src, content, cwd or self._cwd)


def _s32_stop(self):
    return _s32.RUN.stop()


def _s32_del(self, path):
    return _s32.delete_temp(path)


def _s32_status(self):
    return {"ok": True, "busy": _s32.RUN.busy()}


def _s32_list_dir(self, cwd, top=False, max_items=5000):
    out = _s32_orig_list_dir(self, cwd, top=top, max_items=max_items)
    try:
        out = [x for x in out if not _s32.is_temp(x.get("name"))]
    except Exception:
        pass
    return out


Api.split032_run = _s32_run
Api.split032_stop = _s32_stop
Api.split032_del = _s32_del
Api.split032_status = _s32_status
Api._list_dir = _s32_list_dir
# ===== /SC-SPLIT-032 =====

# ===== SC-I18N-038 =====
# DIKKAT: Api metotlari ASLA *args/**kwargs ile sarmalanmaz.
# pywebview JS koprusunu imzalardan uretir; sarmalama butun API'yi bozar.
import sys as _s38_sys
from . import i18n_rt as _rt38


def _sc38_dil_paket(self, lang):
    try:
        return _rt38.pack(lang)
    except Exception as e:
        return {"ok": False, "hata": str(e), "lang": "tr",
                "phrases": {}, "prefixes": {}, "words": {}}


def _sc38_dil_ayarla(self, lang):
    try:
        lang = (lang or "tr").lower()
        self.settings["language"] = lang
        save_settings(self.settings)
        try:
            clear_build_cache()
        except Exception:
            pass
        return {"ok": True, "lang": lang}
    except Exception as e:
        return {"ok": False, "hata": str(e)}


def _sc38_dil_listesi(self):
    try:
        return {"ok": True, "langs": _rt38.LANG_TR}
    except Exception:
        return {"ok": True, "langs": {"tr": "Türkçe", "en": "English"}}


# --- Frozen (exe) guvenligi: sys.executable kendi exe'miz olabilir ---
def _sc38_real_python():
    try:
        exe = _s38_sys.executable or ""
        base = os.path.basename(exe).lower()
        frozen = bool(getattr(_s38_sys, "frozen", False))
        if not frozen:
            return exe
        bad = {"splashcodestudio.exe", "splash.exe", base}
        cand = getattr(_s38_sys, "_base_executable", None)
        if cand and os.path.isfile(cand) and os.path.basename(cand).lower() not in bad:
            return cand
        for nm in ("python.exe", "python3.exe", "python3", "python"):
            w = shutil.which(nm)
            if w and os.path.basename(w).lower() not in bad:
                return os.path.abspath(w)
    except Exception:
        pass
    return ""


def _sc38_fix_cmd(cmd):
    if not isinstance(cmd, list) or not cmd:
        return cmd
    out = list(cmd)
    try:
        if str(out[0]) == _s38_sys.executable and getattr(_s38_sys, "frozen", False):
            p = _sc38_real_python()
            if not p:
                return None
            out[0] = p
    except Exception:
        pass
    return out


def _sc38_calistir(self, path, cwd):
    if not path:
        return {"ok": False, "hata": "Dosya yok"}
    ext = os.path.splitext(path)[1].lower()
    if ext in (".py", ".pyw"):
        py = _sc38_real_python() or _s38_sys.executable
        if getattr(_s38_sys, "frozen", False) and not _sc38_real_python():
            return {"ok": False, "hata": "Python bulunamadi"}
        cmd = [py, "-u", path]
    elif ext in (".js", ".mjs", ".cjs"):
        cmd = ["node", path]
    elif ext == ".sh":
        cmd = ["bash", path]
    elif ext == ".ps1":
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", path]
    elif ext == ".rb":
        cmd = ["ruby", path]
    elif ext == ".go":
        cmd = ["go", "run", path]
    elif ext == ".rs":
        cmd = ["cargo", "run", "--manifest-path",
               os.path.join(cwd or ".", "Cargo.toml")]
    else:
        return {"ok": False, "hata": "Desteklenmeyen: %s" % ext}
    return self._run_cmd("run1", cwd or os.path.dirname(path) or os.getcwd(), cmd)


def _sc38_lsp_kur(self, lang):
    try:
        cmd = LSP_INSTALL_CMDS.get(lang)
        if cmd is None:
            return {"ok": False, "manuel": True,
                    "hata": LSP_INSTALL_NOTES.get(lang, "Elle kurulum gerekli")}
        cmd = _sc38_fix_cmd(list(cmd))
        if not cmd:
            return {"ok": False, "hata": "Python bulunamadi"}
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = 0x08000000
        env = dict(os.environ)
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=600, env=env, **kw)
        ok = r.returncode == 0
        return {"ok": ok, "out": (r.stdout or "")[-2000:],
                "err": (r.stderr or "")[-2000:] if not ok else ""}
    except Exception as e:
        return {"ok": False, "hata": str(e)}


def _sc38_runtime(self):
    return {"ok": True, "frozen": bool(getattr(_s38_sys, "frozen", False)),
            "python": _sc38_real_python(), "executable": _s38_sys.executable}


Api.dil_paket = _sc38_dil_paket
Api.dil_ayarla = _sc38_dil_ayarla
Api.dil_listesi = _sc38_dil_listesi
Api.calistir = _sc38_calistir
Api.lsp_kur = _sc38_lsp_kur
Api.calisma_ortami = _sc38_runtime
# ===== /SC-I18N-038 =====
# ===== SC-RUN-044 =====
from . import runners as _r44


def _sc44_calistir(self, path, cwd=None):
    try:
        ext = os.path.splitext(path or "")[1].lower()
        spec = _r44.RUNNERS.get(ext)
        if not spec:
            return {"ok": False, "unsupported": True,
                    "hata": "Desteklenmeyen: " + (ext or "?")}
        if spec["rt"] == "browser":
            import webbrowser
            webbrowser.open("file:///" +
                            os.path.abspath(path).replace("\\", "/"))
            return {"ok": True, "browser": True}
        b = _r44.find_bin(spec["bin"])
        if not b:
            rt = spec["rt"]
            return {"ok": False, "missing": rt,
                    "hata": _r44.NAMES.get(rt, rt) + " kurulu degil",
                    "install": _r44.install_cmds(rt),
                    "manuel": _r44.MANUEL.get(rt, "")}
        cmd = spec["cmd"](os.path.abspath(path), b, cwd)
        base = cwd or os.path.dirname(os.path.abspath(path)) or os.getcwd()
        return self._run_cmd("run1", base, cmd)
    except Exception as e:
        return {"ok": False, "hata": str(e)}


def _sc44_runtime_kur(self, rt):
    cmds = _r44.install_cmds(rt)
    if not cmds:
        return {"ok": False, "manuel": _r44.MANUEL.get(rt, "Elle kurulum gerekli"),
                "hata": "Otomatik kurulum yok"}
    last = ""
    for c in cmds:
        try:
            r = subprocess.run(c, shell=True, capture_output=True, text=True,
                               timeout=1500, **_r44.nowin())
            last = ((r.stdout or "")[-1200:] + (r.stderr or "")[-1200:])
            if r.returncode == 0:
                return {"ok": True, "out": last}
        except Exception as e:
            last = str(e)
    return {"ok": False, "hata": last or "Kurulum basarisiz",
            "manuel": _r44.MANUEL.get(rt, "")}


def _sc44_runtime_durum(self):
    return {"ok": True, "runtimes": _r44.detect_all(),
            "names": _r44.NAMES}


Api.calistir = _sc44_calistir
Api.runtime_kur = _sc44_runtime_kur
Api.runtime_durum = _sc44_runtime_durum
# ===== /SC-RUN-044 =====
