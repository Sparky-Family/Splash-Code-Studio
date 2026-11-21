"""
Splash Code Studio - Merkezi loglama  (SC-PATCH-007)
~/.splash_code/splash.log  (2MB x 3 rotasyon)
"""
import functools
import logging
import logging.handlers
import os
import sys
import traceback

from .constants import SETTINGS_DIR

LOG_FILE = os.path.join(SETTINGS_DIR, "splash.log")
_logger = None


def get_logger():
    global _logger
    if _logger is not None:
        return _logger
    lg = logging.getLogger("splash")
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    if not lg.handlers:
        try:
            os.makedirs(SETTINGS_DIR, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(
                LOG_FILE, maxBytes=2 * 1024 * 1024,
                backupCount=3, encoding="utf-8")
            fh.setFormatter(logging.Formatter(
                "%(asctime)s %(levelname)-7s [%(threadName)s] %(message)s"))
            lg.addHandler(fh)
        except Exception:
            lg.addHandler(logging.NullHandler())
        if os.environ.get("SPLASH_DEBUG"):
            sh = logging.StreamHandler(sys.stderr)
            sh.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
            lg.addHandler(sh)
    _logger = lg
    return lg


def info(msg, *args):
    try:
        get_logger().info(msg, *args)
    except Exception:
        pass


def warn(msg, *args):
    try:
        get_logger().warning(msg, *args)
    except Exception:
        pass


def error(msg, *args):
    try:
        get_logger().error(msg, *args)
    except Exception:
        pass


def exc(msg, e=None):
    try:
        suffix = (": %s" % e) if e is not None else ""
        get_logger().error("%s%s\n%s", msg, suffix, traceback.format_exc())
    except Exception:
        pass


def safe(default=None):
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **kw):
            try:
                return fn(*a, **kw)
            except Exception as e:
                exc(fn.__qualname__, e)
                return default() if callable(default) else default
        return wrap
    return deco
