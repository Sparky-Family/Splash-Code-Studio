"""
Splash Code Studio - Ayar Yönetimi
Yükleme, kaydetme, şema doğrulama, oturum yönetimi
"""
import json
import os

from .constants import (
    SETTINGS_DIR, SETTINGS_FILE, SETTINGS_BACKUP,
    SESSION_FILE, ICON_PACKS,
)
from .utils import atomic_write, secure_file

# ── Ayar Şeması (tip zorlama) ────────────────────────
SETTINGS_SCHEMA = {
    "fontSize": float, "tabSize": int, "minimap": bool,
    "wordWrap": bool, "fontLigatures": bool, "lineNumbers": bool,
    "autosave": bool, "autoSaveBeforeRun": bool, "saveBeforeRun": bool,
    "formatOnSave": bool, "lintOnSave": bool,
    "lspEnabled": bool, "diagnosticsEnabled": bool,
    "showProblems": bool, "treesitterEnabled": bool,
    "rememberSession": bool, "rememberProject": bool,
    "showWelcome": bool, "useCustomAccent": bool, "ai_panel_open": bool,
    "terminalMode": str, "runMode": str, "theme": str,
    "iconPack": str, "language": str, "encoding": str,
    "endOfLine": str, "terminalFontSize": int,
    "terminalScrollback": int, "lspDebounceMs": int, "lspCacheTtl": int,
}

DEFAULT_SETTINGS = {
    "fontSize": 13.5, "fontFamily": "JetBrains Mono", "tabSize": 4,
    "minimap": True, "wordWrap": False, "fontLigatures": True,
    "lineNumbers": True,
    "theme": "obsidian", "customAccent": "#2F81F7",
    "useCustomAccent": False,
    "rememberSession": True, "showWelcome": False,
    "themeCategory": None, "themeSearch": "",
    "ai_provider": "", "ai_gemini_key": "", "ai_claude_key": "",
    "ai_model": "", "ai_panel_open": False,
    "autosave": True, "endOfLine": "\n", "encoding": "utf-8",
    "language": "tr", "rememberProject": True, "lastProject": None,
    "largeFileWarnSize": 5 * 1024 * 1024,
    "autoSaveBeforeRun": True,
    "splitMode": "none", "runMode": "internal",
    "terminalMode": "internal",
    "lspEnabled": True, "formatOnSave": False,
    "treesitterEnabled": True, "terminalFontSize": 13,
    "terminalScrollback": 1000, "saveBeforeRun": True,
    "iconPack": "splash", "lspDebounceMs": 250, "lspCacheTtl": 30,
    "diagnosticsEnabled": True, "showProblems": True, "lintOnSave": True,
}


def normalize_settings(s: dict) -> dict:
    """Ayarları şemaya göre doğrular ve normalize eder."""
    out = dict(DEFAULT_SETTINGS)
    try:
        data = dict(s or {})
        # alias: saveBeforeRun -> autoSaveBeforeRun
        if "saveBeforeRun" in data and "autoSaveBeforeRun" not in data:
            data["autoSaveBeforeRun"] = bool(data["saveBeforeRun"])
        for k, typ in SETTINGS_SCHEMA.items():
            if k not in data:
                continue
            v = data[k]
            try:
                if typ is bool:
                    if isinstance(v, str):
                        v = v.strip().lower() in ("1", "true", "yes",
                                                   "evet", "on")
                    else:
                        v = bool(v)
                elif typ is int:
                    v = int(float(v))
                elif typ is float:
                    v = float(v)
                elif typ is str:
                    v = str(v)
            except Exception:
                continue
            out[k] = v
        # enum doğrulama
        if out.get("terminalMode") not in ("internal", "external"):
            out["terminalMode"] = "internal"
        if out.get("runMode") not in ("internal", "external"):
            out["runMode"] = "internal"
        if out.get("iconPack") not in ICON_PACKS:
            out["iconPack"] = "splash"
        out["tabSize"] = max(1, min(8, out.get("tabSize", 4)))
        out["fontSize"] = max(8, min(32, out.get("fontSize", 13.5)))
        out["terminalFontSize"] = max(
            8, min(28, out.get("terminalFontSize", 13)))
        out["terminalScrollback"] = max(
            100, min(10000, out.get("terminalScrollback", 1000)))
        # bilinmeyen anahtarları koru (ileriye dönük)
        for k, v in data.items():
            if k not in out:
                out[k] = v
    except Exception:
        pass
    return out


def load_settings() -> dict:
    """Ayarları dosyadan yükler."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return normalize_settings(data)
    except Exception:
        try:
            if os.path.exists(SETTINGS_BACKUP):
                with open(SETTINGS_BACKUP, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    merged = dict(DEFAULT_SETTINGS)
                    merged.update(data)
                    return merged
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)


def save_settings(s: dict) -> bool:
    """Ayarları dosyaya kaydeder."""
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        atomic_write(SETTINGS_FILE,
                     json.dumps(s, indent=2, ensure_ascii=False))
        secure_file(SETTINGS_FILE)
        return True
    except Exception:
        return False


def load_session() -> dict:
    """Oturum bilgisini yükler."""
    try:
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"cwd": None, "tabs": [], "activeTab": None,
            "recentFiles": []}


def save_session(s: dict) -> bool:
    """Oturum bilgisini kaydeder."""
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        atomic_write(SESSION_FILE,
                     json.dumps(s, indent=2, ensure_ascii=False))
        secure_file(SESSION_FILE)
        return True
    except Exception:
        return False


def load_icon_map() -> dict:
    """İkon eşlemesini yükler."""
    from .constants import DEFAULT_ICON_MAP, ICON_MAP_FILE
    try:
        if os.path.exists(ICON_MAP_FILE):
            with open(ICON_MAP_FILE, "r", encoding="utf-8") as f:
                m = dict(DEFAULT_ICON_MAP)
                m.update(json.load(f))
                return m
    except Exception:
        pass
    return dict(DEFAULT_ICON_MAP)


def save_icon_map(m: dict) -> bool:
    """İkon eşlemesini kaydeder."""
    from .constants import ICON_MAP_FILE
    try:
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        atomic_write(ICON_MAP_FILE,
                     json.dumps(m, indent=2, ensure_ascii=False))
        return True
    except Exception:
        return False

# ===== SC-PATCH-003 =====
import shutil as _sc003_shutil
SETTINGS_SCHEMA.update({
    'fontFamily': str, 'customAccent': str, 'splitMode': str,
    'ai_provider': str, 'ai_gemini_key': str, 'ai_claude_key': str,
    'ai_model': str, 'largeFileWarnSize': int,
})
_sc003_orig_normalize = normalize_settings
_sc003_orig_save = save_settings
def normalize_settings(s):
    # enum + clamp dogrulamasi
    out = _sc003_orig_normalize(s)
    try:
        if out.get('splitMode') not in ('none', 'vertical', 'horizontal'):
            out['splitMode'] = 'none'
        if out.get('encoding') not in ('utf-8', 'utf-8-sig', 'latin-1', 'cp1254'):
            out['encoding'] = 'utf-8'
        if out.get('endOfLine') not in ('\n', '\r\n'):
            out['endOfLine'] = '\n'
        for _k in ('lastProject', 'themeCategory'):
            if out.get(_k) in ('', 'None'):
                out[_k] = None
        out['largeFileWarnSize'] = max(65536, min(67108864, int(out.get('largeFileWarnSize') or 5242880)))
        out['lspDebounceMs'] = max(50, min(2000, int(out.get('lspDebounceMs') or 250)))
        out['lspCacheTtl'] = max(1, min(600, int(out.get('lspCacheTtl') or 30)))
    except Exception:
        pass
    return out
def save_settings(s):
    # .bak artik gercekten yaziliyor -> load_settings fallback'i calisir
    try:
        if os.path.exists(SETTINGS_FILE):
            _sc003_shutil.copy2(SETTINGS_FILE, SETTINGS_BACKUP)
    except Exception:
        pass
    return _sc003_orig_save(s)
# ===== /SC-PATCH-003 =====
