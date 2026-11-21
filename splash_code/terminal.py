"""
Splash Code Studio - Terminal PTY Yonetimi  (SC-PATCH-007)

  * RLock -> ic ice kilitlenme yok
  * Kilit altinda asla I/O yok
  * Queue'lu writer -> sirali cikti + zaman tabanli flush
  * env winpty'ye de geciriliyor
  * Reader: olu surecte sonsuz dongu korumasi
  * Coklu terminal altyapisi hazir (term_list)
"""
import os
import queue
import shutil
import threading
import time

try:
    from .log import exc, info, warn
except Exception:
    def exc(*a, **k):
        pass

    def info(*a, **k):
        pass

    def warn(*a, **k):
        pass

_TERM_PROCS = {}
_TERM_LOCK = threading.RLock()
_MAX_CHUNK = 8000
_FLUSH_INTERVAL = 0.035
_READ_ERRORS_LIMIT = 20


def _alive(proc):
    try:
        return bool(proc.isalive())
    except Exception:
        return False


def _notify_frontend(func_name, data, term_id):
    try:
        import webview
        if not webview.windows:
            return
        import json as _json
        if data is None:
            js = ("if(window.%s) window.%s(%s);"
                  % (func_name, func_name, _json.dumps(term_id)))
        else:
            js = ("if(window.%s) window.%s(%s, %s);"
                  % (func_name, func_name,
                     _json.dumps(data), _json.dumps(term_id)))
        webview.windows[0].evaluate_js(js)
    except Exception as e:
        warn("term notify %s: %s", func_name, e)


def term_spawn(term_id, cwd, shell_cmd=None):
    term_id = str(term_id or "t1")
    try:
        term_close(term_id)

        if not cwd or not os.path.isdir(str(cwd)):
            cwd = os.getcwd()
        cwd = os.path.abspath(cwd)

        env = dict(os.environ)
        env.setdefault("TERM", "xterm-256color")
        env.setdefault("COLORTERM", "truecolor")
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        if os.name == "nt":
            try:
                from winpty import PtyProcess as WPy
            except ImportError:
                return {"ok": False,
                        "hata": "pywinpty yok. pip install pywinpty"}
            shell = shell_cmd or (
                shutil.which("pwsh")
                or shutil.which("powershell")
                or "powershell.exe")
            argv = [shell] if isinstance(shell, str) else list(shell)
            try:
                proc = WPy.spawn(argv, cwd=cwd, env=env,
                                 dimensions=(30, 120))
            except TypeError:
                proc = WPy.spawn(argv, cwd=cwd, dimensions=(30, 120))
        else:
            try:
                import ptyprocess
            except ImportError:
                return {"ok": False,
                        "hata": "ptyprocess yok. pip install ptyprocess"}
            shell = shell_cmd or os.environ.get("SHELL", "/bin/bash")
            argv = [shell] if isinstance(shell, str) else list(shell)
            proc = ptyprocess.PtyProcessUnicode.spawn(
                argv, cwd=cwd, env=env, dimensions=(30, 120))

        q = queue.Queue()
        stop = threading.Event()
        entry = {"proc": proc, "q": q, "stop": stop, "cwd": cwd}
        with _TERM_LOCK:
            _TERM_PROCS[term_id] = entry

        def reader():
            errs = 0
            while not stop.is_set():
                try:
                    data = proc.read(4096)
                except EOFError:
                    break
                except Exception:
                    errs += 1
                    if errs > _READ_ERRORS_LIMIT or not _alive(proc):
                        break
                    time.sleep(0.02)
                    continue
                if not data:
                    if not _alive(proc):
                        break
                    continue
                errs = 0
                if isinstance(data, bytes):
                    data = data.decode("utf-8", "replace")
                q.put(data)
            q.put(None)

        def writer():
            buf, size, first = [], 0, 0.0
            while True:
                wait = _FLUSH_INTERVAL if not size else _FLUSH_INTERVAL / 3
                try:
                    item = q.get(timeout=wait)
                except queue.Empty:
                    item = ""
                if item is None:
                    break
                if item:
                    if not size:
                        first = time.time()
                    buf.append(item)
                    size += len(item)
                if size and (size >= _MAX_CHUNK
                             or time.time() - first >= _FLUSH_INTERVAL):
                    chunk = "".join(buf)
                    buf, size, first = [], 0, 0.0
                    _notify_frontend("termWrite", chunk, term_id)
            if buf:
                _notify_frontend("termWrite", "".join(buf), term_id)
            _notify_frontend("termClosed", None, term_id)
            with _TERM_LOCK:
                if _TERM_PROCS.get(term_id) is entry:
                    _TERM_PROCS.pop(term_id, None)
            info("terminal kapandi: %s", term_id)

        threading.Thread(target=reader, name="term-r-%s" % term_id,
                         daemon=True).start()
        threading.Thread(target=writer, name="term-w-%s" % term_id,
                         daemon=True).start()
        info("terminal basladi: %s (cwd=%s)", term_id, cwd)
        return {"ok": True, "cwd": cwd, "term_id": term_id}

    except Exception as e:
        exc("term_spawn", e)
        return {"ok": False, "hata": str(e)}


def _get_proc(term_id):
    with _TERM_LOCK:
        entry = _TERM_PROCS.get(term_id)
        return entry["proc"] if entry else None


def term_write(term_id, data):
    try:
        proc = _get_proc(term_id)
        if not proc:
            return {"ok": False}
        if not isinstance(data, str):
            data = str(data)
        proc.write(data)
        return {"ok": True}
    except Exception as e:
        exc("term_write", e)
        return {"ok": False, "hata": str(e)}


def term_resize(term_id, rows, cols):
    try:
        rows = max(5, min(200, int(rows or 30)))
        cols = max(20, min(500, int(cols or 120)))
        proc = _get_proc(term_id)
        if not proc:
            return {"ok": False}
        done = False
        for args in ((rows, cols), (cols, rows)):
            try:
                proc.setwinsize(*args)
                done = True
                break
            except Exception:
                continue
        if not done:
            warn("term_resize basarisiz: %s", term_id)
        return {"ok": True, "rows": rows, "cols": cols}
    except Exception as e:
        exc("term_resize", e)
        return {"ok": False}


def term_close(term_id):
    try:
        with _TERM_LOCK:
            entry = _TERM_PROCS.pop(term_id, None)
        if not entry:
            return {"ok": True}
        entry["stop"].set()
        proc = entry["proc"]
        try:
            proc.terminate(force=True)
        except TypeError:
            try:
                proc.terminate()
            except Exception:
                pass
        except Exception:
            pass
        try:
            entry["q"].put_nowait(None)
        except Exception:
            pass
        return {"ok": True}
    except Exception as e:
        exc("term_close", e)
        return {"ok": False}


def term_list():
    with _TERM_LOCK:
        return list(_TERM_PROCS.keys())


def close_all_terminals():
    with _TERM_LOCK:
        ids = list(_TERM_PROCS.keys())
    for tid in ids:
        try:
            term_close(tid)
        except Exception as e:
            exc("close_all_terminals", e)
