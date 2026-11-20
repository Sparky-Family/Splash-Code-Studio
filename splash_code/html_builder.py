"""
Splash Code Studio - HTML Builder
Template dosyasını okur ve placeholder'ları doldurur
"""
import json
import os

from .constants import (
    APP_NAME, SYSTEM_FONTS, LSP_MONACO_IDS,
    BUILTINS, DEFAULT_ICON_MAP, SC_LOGO_DOSYA_YOLU,
)
from .icons import ICONS, svg
from .themes import all_themes

_TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "templates", "index.html",
)

_svg_cache = {}
_themes_json_cache = None
_build_cache = {}
_BUILD_CACHE_MAX = 3


def _load_logo_b64() -> str:
    """Logo dosyasından base64 yükler."""
    import base64
    logo_path = os.path.abspath(SC_LOGO_DOSYA_YOLU)
    if os.path.exists(logo_path):
        try:
            with open(logo_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except Exception:
            pass
    # Fallback: küçük bir placeholder SVG
    return ""


def _icon_btn(name: str, onclick: str, title: str,
              cls: str = "", size: int = 16) -> str:
    return (
        f'<button class="icon-btn {cls}" onclick="{onclick}" '
        f'title="{title}">{svg(name, size)}</button>'
    )


def _cached_themes_json(themes: dict) -> str:
    global _themes_json_cache
    if _themes_json_cache is None:
        _themes_json_cache = json.dumps(
            themes, ensure_ascii=False)
    return _themes_json_cache


def build_html(settings: dict) -> str:
    """HTML template'i placeholder'larla doldurur."""
    cache_key = (
        settings.get("theme"),
        settings.get("fontSize"),
        settings.get("fontFamily"),
        settings.get("iconPack"),
        settings.get("language"),
    )
    if cache_key in _build_cache:
        return _build_cache[cache_key]

    with open(_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template = f.read()

    logo_b64 = _load_logo_b64()
    themes = all_themes()
    font_options = "".join(
        f'<option value="{f}">{f}</option>' for f in SYSTEM_FONTS
    )

    replacements = {
        "__APP_NAME__": APP_NAME,
        "__LOGO_SVG__": (
            f'<img src="data:image/png;base64,{logo_b64}" '
            f'style="width:24px;height:24px;display:block;'
            f'border:none;outline:none;background:none" alt="SC">'
            if logo_b64 else
            f'<svg xmlns="http://www.w3.org/2000/svg" width="24" '
            f'height="24" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="1.6">'
            f'{ICONS.get("logo", "")}</svg>'
        ),
        "__ICON_FOLDER__": svg("folder", 16),
        "__ICON_GIT__": svg("git", 16),
        "__ICON_WELCOME__": svg("welcome", 16),
        "__ICON_BELL__": svg("bell", 16),
        "__ICON_ROBOT__": svg("robot", 16),
        "__ICON_COMMAND__": svg("command", 16),
        "__ICON_SEARCH__": svg("search", 16),
        "__ICON_SPARKLE__": svg("sparkle", 16),
        "__ICON_X__": svg("x", 16),
        "__ICON_PLUS__": svg("plus", 16),
        "__ICON_SEND__": svg("send", 16),
        "__ICON_TRASH__": svg("trash", 16),
        "__ICON_REFRESH__": svg("refresh", 16),
        "__ICON_TERM__": svg("terminal", 14),
        "__ICON_SPLIT_V__": svg("split_v", 16),
        "__ICON_SPLIT_H__": svg("split_h", 16),
        "__ICON_GIT_SM__": svg("git", 12),
        "__BTN_NEW__": _icon_btn(
            "new_file", "yeniSekme()", "Yeni (Ctrl+N)"),
        "__BTN_OPEN__": _icon_btn(
            "open", "dosyaAc()", "Aç (Ctrl+O)"),
        "__BTN_FOLDEROPEN__": _icon_btn(
            "folder_open", "klasorSec()", "Klasör Aç"),
        "__BTN_SAVE__": _icon_btn(
            "save", "kaydet()", "Kaydet (Ctrl+S)"),
        "__BTN_SAVEAS__": _icon_btn(
            "save_as", "farkliKaydet()",
            "Farklı Kaydet (Ctrl+Shift+S)"),
        "__BTN_RUN__": _icon_btn(
            "run", "calistir()", "Çalıştır (F5)", "primary"),
        "__BTN_STOP__": _icon_btn(
            "stop", "durdur()", "Durdur", "danger"),
        "__BTN_TERM__": _icon_btn(
            "terminal", "terminalToggle()", "Terminal (Ctrl+`)"),
        "__BTN_PALETTE__": _icon_btn(
            "palette", "temaGalerisiAc()", "Tema Galerisi"),
        "__BTN_SETTINGS__": _icon_btn(
            "settings", "ayarlariAc()", "Ayarlar"),
        "__BTN_NEWFOLDER__": _icon_btn(
            "folder_plus", "treeAction('newfolder')",
            "Yeni Klasör", size=14),
        "__BTN_REFRESHTREE__": _icon_btn(
            "refresh", "refreshTree()", "Yenile", size=14),
        "__FONT_OPTIONS__": font_options,
        "__CWD__": settings.get("lastProject") or "Proje yok",
        "__THEMES_JSON__": _cached_themes_json(themes),
        "__FONTS_JSON__": json.dumps(
            SYSTEM_FONTS, ensure_ascii=False),
        "__SC_LOGO_JSON__": json.dumps(
            f'<img src="data:image/png;base64,{logo_b64}" '
            f'style="width:110px;height:110px;display:block;'
            f'border:none;outline:none;background:none" '
            f'alt="Splash Code">'
            if logo_b64 else
            f'<svg xmlns="http://www.w3.org/2000/svg" width="110" '
            f'height="110" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="1.6">'
            f'{ICONS.get("logo", "")}</svg>'
        ),
        "__ICON_MAP_JSON__": json.dumps(DEFAULT_ICON_MAP),
        "__ICONS_JSON__": json.dumps(ICONS),
        "__LSP_IDS_JSON__": json.dumps(list(LSP_MONACO_IDS)),
        "__BUILTINS_JSON__": json.dumps(BUILTINS),
        "__INITIAL_SETTINGS_JSON__": json.dumps(
            settings, ensure_ascii=False),
    }

    html = template
    for k, v in replacements.items():
        html = html.replace(k, v)

    if len(_build_cache) >= _BUILD_CACHE_MAX:
        _build_cache.clear()
    _build_cache[cache_key] = html
    return html


def clear_build_cache():
    """HTML build cache'ini temizler."""
    _build_cache.clear()

# ===== SC-PATCH-003 =====
from .constants import THEMES_USER_FILE as _sc003_TF, ICON_MAP_FILE as _sc003_IF
_sc003_sig = None
_sc003_orig_build = build_html
def _sc003_mtime(p):
    try:
        return os.path.getmtime(p)
    except Exception:
        return 0
def build_html(settings):
    # proje / tema / ikon dosyasi degisince cache'i otomatik dusur
    global _sc003_sig, _themes_json_cache
    s = settings or {}
    sig = (s.get('lastProject'), s.get('theme'), s.get('iconPack'),
           s.get('useCustomAccent'), s.get('customAccent'),
           _sc003_mtime(_TEMPLATE_PATH), _sc003_mtime(_sc003_TF),
           _sc003_mtime(_sc003_IF))
    if sig != _sc003_sig:
        _sc003_sig = sig
        _build_cache.clear()
        _themes_json_cache = None
    return _sc003_orig_build(settings)
def clear_build_cache():
    # tema JSON cache'i de temizlenir (yeni tema restart istemez)
    global _themes_json_cache, _sc003_sig
    _build_cache.clear()
    _themes_json_cache = None
    _sc003_sig = None
# ===== /SC-PATCH-003 =====

# ===== SC-PATCH-004 =====
import os as _sc004_os
_SC004_CDN = 'https://cdn.jsdelivr.net/npm/monaco-editor@0.44.0/min/vs'
_SC004_LOCAL = 'static/monaco/vs'
_sc004_orig_build = build_html
def _sc004_local_ready():
    try:
        d = _sc004_os.path.dirname(_sc004_os.path.abspath(__file__))
        p = _sc004_os.path.join(d, 'static', 'monaco', 'vs', 'loader.js')
        return _sc004_os.path.isfile(p)
    except Exception:
        return False
def build_html(settings):
    # Yerel Monaco varsa CDN adreslerini yerel yola cevir (offline)
    html = _sc004_orig_build(settings)
    try:
        if _sc004_local_ready() and not _sc004_os.environ.get('SPLASH_FORCE_CDN'):
            html = html.replace(_SC004_CDN, _SC004_LOCAL)
    except Exception:
        pass
    return html
# ===== /SC-PATCH-004 =====

# ===== SC-STUDIO-008 =====
import re as _sc008_re
_sc008_orig_build = build_html


def build_html(settings):
    html = _sc008_orig_build(settings)
    try:
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "static", "fonts", "sc-fonts.css")
        if os.path.isfile(p) and not os.environ.get("SPLASH_FORCE_CDN"):
            html = _sc008_re.sub(
                r"<link[^>]*fonts\.googleapis\.com[^>]*>",
                '<link rel="stylesheet" href="static/fonts/sc-fonts.css">',
                html)
            html = _sc008_re.sub(
                r"<link[^>]*fonts\.gstatic\.com[^>]*>", "", html)
    except Exception:
        pass
    return html
# ===== /SC-STUDIO-008 =====
