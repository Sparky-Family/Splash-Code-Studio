"""Splash Code Studio - Modüler IDE"""

__version__ = "3.0.0"
__app_name__ = "Splash Code Studio"
__version_name__ = "Modular"

# ===== SC-PATCH-005 =====
# main.py 'from splash_code import app_name, version' kullaniyor.
# Bu isimler eksikse ImportError olusuyordu; guard'li tanimlar.
if 'app_name' not in globals():
    app_name = 'Splash Code Studio'
if 'version' not in globals():
    version = '3.0.0'
if 'version_name' not in globals():
    version_name = 'Modular'
if 'APP_NAME' not in globals():
    APP_NAME = app_name
if 'APP_VERSION' not in globals():
    APP_VERSION = version + ' - ' + version_name
# ===== /SC-PATCH-005 =====
