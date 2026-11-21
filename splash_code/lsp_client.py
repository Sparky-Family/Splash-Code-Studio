"""
Splash Code Studio - LSP Istemcisi  (SC-PATCH-007)

  * stderr drain thread -> pipe dolup sunucu bloke olmuyor
  * bufsize=-1 + _read_exact -> kismi okuma / bozuk JSON yok
  * Istek oncesi _sync() -> sunucu asla bayat dokuman gormuyor
  * initialize() cevap dogrulamasi
  * Pool eviction kilit DISINDA
  * peek_lsp() -> diagnostics icin sunucu spawn etmez
"""
import json
import os
import shutil
import subprocess
import threading
import time
from collections import deque

from .constants import LSP_SERVERS
from .utils import path_to_uri

try:
    from .log import exc, info, warn
except Exception:
    def exc(*a, **k):
        pass

    def info(*a, **k):
        pass

    def warn(*a, **k):
        pass

_THROTTLE = 0.25
_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class LspClient:

    def __init__(self, lang, root_path):
        self.lang = lang
        self.cmd = LSP_SERVERS.get(lang)
        self.proc = None
        self._id = 0
        self._wlock = threading.Lock()
        self._plock = threading.RLock()
        self._pending = {}
        self._open_files = set()
        self._versions = {}
        self._diagnostics = {}
        self._diag_lock = threading.Lock()
        self._last_text = {}
        self._pending_text = {}
        self._last_did_change = {}
        self._last_used = time.time()
        self._ready = False
        self._init_lock = threading.RLock()
        self.capabilities = {}
        self.stderr_tail = deque(maxlen=200)
        self._root = root_path or os.getcwd()
        self._reader = None
        self._errreader = None
        self._start()

    def _start(self):
        if not self.cmd:
            return
        exe = self.cmd[0]
        if not (shutil.which(exe)
                or (os.path.isabs(exe) and os.path.isfile(exe))):
            return
        try:
            kw = {}
            if _CREATE_NO_WINDOW:
                kw["creationflags"] = _CREATE_NO_WINDOW
            if os.path.isdir(self._root):
                kw["cwd"] = self._root
            self.proc = subprocess.Popen(
                self.cmd, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                bufsize=-1, **kw)
        except Exception as e:
            exc("lsp start %s" % self.lang, e)
            self.proc = None
            return

        p = self.proc

        def drain_stderr():
            try:
                for raw in iter(p.stderr.readline, b""):
                    line = raw.decode("utf-8", "replace").rstrip()
                    if line:
                        self.stderr_tail.append(line)
            except Exception:
                pass

        self._errreader = threading.Thread(
            target=drain_stderr, name="lsp-err-%s" % self.lang, daemon=True)
        self._errreader.start()
        self._reader = threading.Thread(
            target=self._read_loop, name="lsp-r-%s" % self.lang, daemon=True)
        self._reader.start()
        info("lsp basladi: %s (root=%s)", self.lang, self._root)

    def _read_headers(self, stream):
        headers = {}
        while True:
            line = stream.readline()
            if not line:
                return None
            try:
                line = line.decode("ascii", errors="ignore").strip()
            except Exception:
                return None
            if not line:
                return headers
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()

    def _read_exact(self, stream, n):
        chunks = []
        left = n
        while left > 0:
            b = stream.read(left)
            if not b:
                return None
            chunks.append(b)
            left -= len(b)
        return b"".join(chunks)

    def _read_loop(self):
        p = self.proc
        try:
            while p and p.poll() is None:
                headers = self._read_headers(p.stdout)
                if not headers:
                    break
                try:
                    length = int(headers.get("Content-Length", 0))
                except Exception:
                    continue
                if length <= 0:
                    continue
                body = self._read_exact(p.stdout, length)
                if body is None:
                    break
                try:
                    msg = json.loads(body.decode("utf-8", "replace"))
                except Exception as e:
                    warn("lsp %s bozuk mesaj: %s", self.lang, e)
                    continue
                try:
                    self._dispatch(msg)
                except Exception as e:
                    exc("lsp dispatch %s" % self.lang, e)
        except Exception:
            pass
        finally:
            self._ready = False
            with self._plock:
                for pend in self._pending.values():
                    try:
                        pend["event"].set()
                    except Exception:
                        pass
            info("lsp reader bitti: %s", self.lang)

    def _dispatch(self, msg):
        mid = msg.get("id")
        method = msg.get("method")
        if method is not None and mid is None:
            self._handle_notification(msg)
            return
        if method is not None and mid is not None:
            self._handle_server_request(msg, mid)
            return
        if mid is not None:
            with self._plock:
                pend = self._pending.get(mid)
            if pend:
                pend["response"] = msg
                pend["event"].set()

    def _handle_notification(self, msg):
        method = msg.get("method", "")
        params = msg.get("params") or {}
        if method == "textDocument/publishDiagnostics":
            uri = params.get("uri", "")
            diags = params.get("diagnostics") or []
            with self._diag_lock:
                self._diagnostics[uri] = diags[:200]
        elif method in ("window/logMessage", "window/showMessage"):
            warn("lsp %s: %s", self.lang, params.get("message", ""))

    def _handle_server_request(self, msg, mid):
        method = msg.get("method", "")
        params = msg.get("params") or {}
        if method == "workspace/configuration":
            items = params.get("items") or [{}]
            result = [{} for _ in items]
        elif method == "workspace/workspaceFolders":
            result = [{"uri": path_to_uri(self._root),
                       "name": os.path.basename(self._root) or "root"}]
        elif method == "workspace/applyEdit":
            result = {"applied": False}
        else:
            result = None
        body = json.dumps({"jsonrpc": "2.0", "id": mid,
                           "result": result}).encode("utf-8")
        self._write_raw(body)

    def _write_raw(self, body):
        try:
            header = ("Content-Length: %d\r\n\r\n" % len(body)).encode("ascii")
            with self._wlock:
                if not self.proc or not self.proc.stdin:
                    return False
                self.proc.stdin.write(header + body)
                self.proc.stdin.flush()
            return True
        except Exception as e:
            exc("lsp write %s" % self.lang, e)
            return False

    def _send(self, method, params, is_request=True):
        if not self.proc or self.proc.poll() is not None:
            return None
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        mid = None
        if is_request:
            with self._plock:
                self._id += 1
                mid = self._id
                self._pending[mid] = {"event": threading.Event(),
                                      "response": None}
            msg["id"] = mid
        body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
        if not self._write_raw(body):
            if mid is not None:
                with self._plock:
                    self._pending.pop(mid, None)
            return None
        return mid if is_request else True

    def _request(self, method, params, timeout=10):
        mid = self._send(method, params, True)
        if mid is None:
            return None
        with self._plock:
            pend = self._pending.get(mid)
        if pend is None:
            return None
        try:
            ok = pend["event"].wait(timeout)
        finally:
            with self._plock:
                self._pending.pop(mid, None)
        if not ok:
            warn("lsp %s timeout: %s", self.lang, method)
            return None
        return pend["response"]

    def initialize(self):
        if self._ready:
            return True
        if not self.proc:
            return False
        with self._init_lock:
            if self._ready:
                return True
            if not self.proc or self.proc.poll() is not None:
                return False
            root_uri = path_to_uri(self._root)
            resp = self._request("initialize", {
                "processId": os.getpid(),
                "rootUri": root_uri,
                "rootPath": self._root,
                "clientInfo": {"name": "Splash Code Studio",
                               "version": "3.0.0"},
                "workspaceFolders": [{
                    "uri": root_uri,
                    "name": os.path.basename(self._root) or "root",
                }],
                "capabilities": {
                    "workspace": {
                        "workspaceFolders": True,
                        "configuration": True,
                        "didChangeConfiguration": {
                            "dynamicRegistration": False},
                    },
                    "textDocument": {
                        "synchronization": {
                            "dynamicRegistration": False, "didSave": True},
                        "completion": {
                            "dynamicRegistration": False,
                            "completionItem": {
                                "snippetSupport": False,
                                "documentationFormat": [
                                    "markdown", "plaintext"],
                            },
                        },
                        "hover": {
                            "dynamicRegistration": False,
                            "contentFormat": ["markdown", "plaintext"],
                        },
                        "definition": {
                            "dynamicRegistration": False,
                            "linkSupport": True},
                        "publishDiagnostics": {"relatedInformation": True},
                        "documentSymbol": {
                            "hierarchicalDocumentSymbolSupport": True},
                        "formatting": {"dynamicRegistration": False},
                    },
                    "window": {"workDoneProgress": True},
                },
            }, timeout=20)
            if not resp or "result" not in resp:
                warn("lsp %s initialize basarisiz: %s",
                     self.lang, (resp or {}).get("error"))
                return False
            self.capabilities = (resp.get("result") or {}).get(
                "capabilities") or {}
            self._send("initialized", {}, False)
            self._ready = True
            info("lsp hazir: %s", self.lang)
            return True

    def did_open(self, file_uri, text):
        if file_uri in self._open_files:
            return
        ok = self._send("textDocument/didOpen", {
            "textDocument": {"uri": file_uri, "languageId": self.lang,
                             "version": 1, "text": text},
        }, False)
        if ok:
            self._open_files.add(file_uri)
            self._versions[file_uri] = 1
            self._last_text[file_uri] = text
            self._last_did_change[file_uri] = time.time()

    def _sync(self, file_uri, text):
        self._last_used = time.time()
        if text is None:
            text = self._pending_text.get(file_uri)
            if text is None:
                text = self._last_text.get(file_uri, "")
        if file_uri not in self._open_files:
            self._pending_text.pop(file_uri, None)
            self.did_open(file_uri, text)
            return
        if (self._last_text.get(file_uri) == text
                and file_uri not in self._pending_text):
            return
        self._pending_text.pop(file_uri, None)
        self._last_text[file_uri] = text
        self._last_did_change[file_uri] = time.time()
        self._versions[file_uri] = self._versions.get(file_uri, 1) + 1
        self._send("textDocument/didChange", {
            "textDocument": {"uri": file_uri,
                             "version": self._versions[file_uri]},
            "contentChanges": [{"text": text}],
        }, False)

    def did_change(self, file_uri, text):
        if file_uri not in self._open_files:
            self._sync(file_uri, text)
            return
        if (self._last_text.get(file_uri) == text
                and file_uri not in self._pending_text):
            return
        self._pending_text[file_uri] = text
        if time.time() - self._last_did_change.get(file_uri, 0) < _THROTTLE:
            return
        self._sync(file_uri, text)

    def did_save(self, file_uri, text=None):
        try:
            self._send("textDocument/didSave", {
                "textDocument": {"uri": file_uri},
            }, False)
        except Exception as e:
            exc("lsp did_save", e)

    def did_close(self, file_uri):
        if not self.proc:
            return
        try:
            self._send("textDocument/didClose", {
                "textDocument": {"uri": file_uri},
            }, False)
        except Exception as e:
            exc("lsp did_close", e)
        self._open_files.discard(file_uri)
        self._pending_text.pop(file_uri, None)

    def completion(self, file_uri, line, col, text):
        if not self.initialize():
            return None
        self._sync(file_uri, text)
        resp = self._request("textDocument/completion", {
            "textDocument": {"uri": file_uri},
            "position": {"line": line, "character": col},
        }, timeout=3)
        if not resp:
            return None
        result = resp.get("result")
        if not result:
            return None
        if isinstance(result, list):
            return result
        return result.get("items", [])

    def hover(self, file_uri, line, col, text):
        if not self.initialize():
            return None
        self._sync(file_uri, text)
        resp = self._request("textDocument/hover", {
            "textDocument": {"uri": file_uri},
            "position": {"line": line, "character": col},
        }, timeout=10)
        return resp.get("result") if resp else None

    def definition(self, file_uri, line, col, text):
        if not self.initialize():
            return None
        self._sync(file_uri, text)
        resp = self._request("textDocument/definition", {
            "textDocument": {"uri": file_uri},
            "position": {"line": line, "character": col},
        }, timeout=10)
        return resp.get("result") if resp else None

    def formatting(self, file_uri, text, tab_size=4, insert_spaces=True):
        if not self.initialize():
            return None
        self._sync(file_uri, text)
        resp = self._request("textDocument/formatting", {
            "textDocument": {"uri": file_uri},
            "options": {"tabSize": int(tab_size),
                        "insertSpaces": bool(insert_spaces)},
        }, timeout=10)
        return resp.get("result") if resp else None

    def diagnostics_for(self, file_uri):
        with self._diag_lock:
            return list(self._diagnostics.get(file_uri, []))

    def shutdown(self):
        proc = self.proc
        if not proc:
            return
        try:
            if proc.poll() is None:
                try:
                    self._request("shutdown", {}, timeout=2)
                except Exception:
                    pass
                try:
                    self._send("exit", {}, False)
                except Exception:
                    pass
                try:
                    proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    try:
                        proc.wait(timeout=2)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
        finally:
            self._ready = False
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    if stream:
                        stream.close()
                except Exception:
                    pass
            with self._plock:
                for pend in self._pending.values():
                    try:
                        pend["event"].set()
                    except Exception:
                        pass
                self._pending.clear()
            self.proc = None
            info("lsp kapandi: %s", self.lang)


_LSP_CLIENTS = {}
_LSP_LOCK = threading.RLock()
_MAX_CLIENTS = 3


def get_lsp(lang, root):
    root = root or os.getcwd()
    key = (lang, root)
    doomed = []
    with _LSP_LOCK:
        c = _LSP_CLIENTS.get(key)
        if c is not None:
            if c.proc and c.proc.poll() is None:
                c._last_used = time.time()
                return c
            _LSP_CLIENTS.pop(key, None)
            doomed.append(c)
        while len(_LSP_CLIENTS) >= _MAX_CLIENTS:
            oldest = min(_LSP_CLIENTS,
                         key=lambda k: getattr(_LSP_CLIENTS[k],
                                               "_last_used", 0))
            doomed.append(_LSP_CLIENTS.pop(oldest))
        c = LspClient(lang, root)
        _LSP_CLIENTS[key] = c
    for d in doomed:
        threading.Thread(target=d.shutdown, daemon=True).start()
    return c


def peek_lsp(lang, root=None):
    root = root or os.getcwd()
    with _LSP_LOCK:
        c = _LSP_CLIENTS.get((lang, root))
        if c and c.proc and c.proc.poll() is None:
            return c
    return None


def shutdown_all_lsp():
    with _LSP_LOCK:
        clients = list(_LSP_CLIENTS.values())
        _LSP_CLIENTS.clear()
    threads = []
    for c in clients:
        t = threading.Thread(target=c.shutdown, daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join(timeout=3)
