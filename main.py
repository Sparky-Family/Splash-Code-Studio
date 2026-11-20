# Splash Code Studio v3.0 - Moduler Entry Point
# Tum mantik splash_code/ paketinde.
import sys
import os
import json
import threading
import traceback
import datetime

_CRASH_LOG = os.path.join(os.path.expanduser('~'), '.splash_code', 'error.log')
_PKG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'splash_code')


def _install_crash_handler():
    def handler(et, ev, etb):
        try:
            os.makedirs(os.path.dirname(_CRASH_LOG), exist_ok=True)
            with open(_CRASH_LOG, 'a', encoding='utf-8') as f:
                f.write('\n' + '=' * 60 + '\n')
                f.write(datetime.datetime.now().isoformat() + '\n')
                f.write('=' * 60 + '\n')
                traceback.print_exception(et, ev, etb, file=f)
            import webview
            if webview.windows:
                webview.windows[0].evaluate_js(
                    'if(window.scToast) scToast("Hata: " + '
                    + json.dumps(str(ev)[:200]) + ', "error", 8000);')
        except Exception:
            pass
        sys.__excepthook__(et, ev, etb)
    sys.excepthook = handler


_install_crash_handler()

# SC005_IMPORT_GUARD
try:
    from splash_code import app_name, version
except ImportError:
    try:
        from splash_code.constants import (
            APP_NAME as app_name, APP_VERSION as version)
    except Exception:
        app_name, version = 'Splash Code Studio', '3.0.0'

from splash_code.settings import load_settings
from splash_code.api import Api
from splash_code.html_builder import build_html


def _local_monaco_ready():
    return os.path.isfile(
        os.path.join(_PKG_DIR, 'static', 'monaco', 'vs', 'loader.js'))


def _start_local_server(root):
    # Koku kesin bilinen mini HTTP sunucusu (stdlib).
    # Ayni origin -> Monaco worker'lari calisir.
    import functools
    from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            p = self.path.split('?')[0].lower()
            if p.endswith(('.py', '.pyc')) and not p.startswith('/static/'):
                self.send_error(403)
                return
            return SimpleHTTPRequestHandler.do_GET(self)

    handler = functools.partial(Handler, directory=root)
    srv = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def main():
    print('=' * 60)
    print(app_name + ' v' + version)
    print('=' * 60)
    import webview
    settings = load_settings()
    api = Api()
    html = build_html(settings)
    offline = _local_monaco_ready() and not os.environ.get('SPLASH_FORCE_CDN')
    srv = None
    window = None
    if offline:
        try:
            out = os.path.join(_PKG_DIR, 'index.sc.html')
            with open(out, 'w', encoding='utf-8', newline='') as f:
                f.write(html)
            srv, port = _start_local_server(_PKG_DIR)
            url = 'http://127.0.0.1:%d/index.sc.html' % port
            print('  Offline mod: ' + url)
            window = webview.create_window(
                app_name, url=url, js_api=api,
                width=1400, height=900, min_size=(900, 600),
                text_select=True)
        except Exception as e:
            print('  Offline mod kurulamadi, CDN moduna donuluyor: ' + str(e))
            if srv is not None:
                try:
                    srv.shutdown()
                except Exception:
                    pass
                srv = None
            window = None
    if window is None:
        print('  Online mod: Monaco CDN')
        window = webview.create_window(
            app_name, html=html, js_api=api,
            width=1400, height=900, min_size=(900, 600),
            text_select=True)

    def on_closed():
        try:
            api.cleanup()
        except Exception:
            pass
        if srv is not None:
            try:
                srv.shutdown()
            except Exception:
                pass

    window.events.closed += on_closed
    webview.start(debug=False, http_server=False)


if __name__ == '__main__':
    main()
