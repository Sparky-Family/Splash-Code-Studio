"""
Splash Code Studio - Yardımcı Fonksiyonlar
Atomik dosya yazma, URI dönüşümü, binary kontrolü
"""
import os
import re
import shutil


def atomic_write(path: str, content: str) -> None:
    """Dosyayı atomik olarak yazar (tmp + rename)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        try:
            os.fsync(f.fileno())
        except Exception:
            pass
    if os.path.exists(path):
        try:
            shutil.copy2(path, path + ".bak")
        except Exception:
            pass
    os.replace(tmp, path)


def secure_file(path: str) -> None:
    """Dosya izinlerini kısıtlar (Unix)."""
    try:
        if os.name != "nt" and os.path.exists(path):
            os.chmod(path, 0o600)
    except Exception:
        pass


def path_to_uri(path: str) -> str:
    """Dosya yolunu file:// URI'ye çevirir."""
    try:
        from pathlib import Path
        return Path(os.path.abspath(str(path))).as_uri()
    except Exception:
        return "file:///" + str(path).replace("\\", "/").lstrip("/")


def uri_to_path(uri: str) -> str:
    """file:// URI'yi dosya yoluna çevirir."""
    try:
        from urllib.parse import urlparse, unquote
        from pathlib import Path
        if not uri:
            return ""
        if uri.startswith("file://"):
            return str(Path(unquote(urlparse(uri).path)))
        return uri
    except Exception:
        return uri


def is_binary_path(path: str) -> bool:
    """Dosyanın binary olup olmadığını kontrol eder."""
    try:
        if os.path.getsize(path) > 2 * 1024 * 1024:
            return True
        with open(path, "rb") as f:
            chunk = f.read(4096)
        return b"\x00" in chunk
    except Exception:
        return True
