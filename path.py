#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Splash Code Studio - Patch 028
1) Harici terminal FIX (schtasks yok, dogrudan Popen, cd yoksa bos ac)
2) __APP_VERSION__ kalabaligini gizle
3) Dil adi "Turkce" -> "Türkçe"
4) i18n TR sozlugu gercek Turkce karakterlerle

    py path.py --check
    py path.py --dry-run
    py path.py
"""

import argparse
import os
import shutil
import sys
import tempfile
import time
import zipfile

PATCH_ID = "028"
TITLE = "Harici terminal fix + TR karakterler + version gizle"
API_REL = "splash_code/api.py"
I18N_REL = "splash_code/i18n.py"
HTML_REL = "splash_code/templates/index.html"

API_MARK = "# ===== SC-TERM-028 ====="
API_END = "# ===== /SC-TERM-028 ====="
I18N_MARK = "# ===== SC-I18N-028 ====="
I18N_END = "# ===== /SC-I18N-028 ====="
HTML_MARK = "<!--SC-FIX-028-->"
HTML_END = "<!--/SC-FIX-028-->"

# ══════════════════════════════════════════════════════════════
#  api.py APPEND — harici terminal FIX
# ══════════════════════════════════════════════════════════════

API_APPEND = r"""
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
"""

# ══════════════════════════════════════════════════════════════
#  i18n.py APPEND — Türkçe düzeltme
# ══════════════════════════════════════════════════════════════

I18N_APPEND = r"""
# ===== SC-I18N-028 =====
# Türkçe düzeltme: dogru karakterler (ç ğ ı İ ö ş ü)
LANGS["tr"] = "Türkçe"
T["tr"] = {
"new": "Yeni", "open": "Aç", "openFolder": "Klasör Aç",
"save": "Kaydet", "saveAs": "Farklı Kaydet",
"run": "Çalıştır", "stop": "Durdur", "terminal": "Terminal",
"settings": "Ayarlar", "themeGallery": "Tema Galerisi",
"explorer": "Gezgin", "git": "Git", "welcome": "Karşılama",
"notifications": "Bildirimler", "aiAssistant": "YZ Asistanı",
"commandPalette": "Komut Paleti", "quickOpen": "Hızlı Aç",
"search": "Projede Ara", "searchPlaceholder": "Aranacak metin...",
"noFolder": "Klasör açılmadı",
"noFolderDesc": "Bir proje klasörü açmak için yukarıdaki klasör simgesine tıklayın.",
"openFolderBtn": "Klasör Aç",
"commit": "Commit", "push": "Push", "pull": "Pull",
"commitMsg": "Commit mesajı...",
"noGit": "Git deposu değil veya git bulunamadı",
"noChanges": "Değişiklik yok",
"aiHello": "Merhaba! Ben YZ asistanınım. Bir şey sormak için aşağıya yaz.",
"aiPlaceholder": "YZ'ya bir şey sor...",
"aiExplain": "Açıkla", "aiRefactor": "Yeniden Düzenle", "aiBug": "Hata Bul", "aiClear": "Temizle",
"ready": "Hazır", "noGitBranch": "git yok",
"output": "Çıktı", "clear": "Temizle", "close": "Kapat",
"cancel": "İptal", "ok": "Tamam", "yes": "Evet", "no": "Hayır",
"delete": "Sil", "rename": "Yeniden Adlandır",
"newFile": "Yeni Dosya", "newFolder": "Yeni Klasör",
"copyPath": "Yolu Kopyala", "openInTerminal": "Terminalde Aç",
"openFile": "Aç", "refresh": "Yenile",
"saved": "Kaydedildi", "created": "Oluşturuldu", "deleted": "Silindi",
"renamed": "Yeniden adlandırıldı", "copied": "Yol kopyalandı",
"unsavedChanges": "Kaydedilmemiş değişiklikler var. Yine de kapatılsın mı?",
"largeFile": "Bu dosya çok büyük. Yine de açılsın mı?",
"deleteConfirm": "Bu öge silinsin mi?",
"fileName": "Dosya adı:", "folderName": "Klasör adı:", "newName": "Yeni ad:",
"settingsTitle": "Ayarlar", "general": "Genel",
"rememberProject": "Proje klasörünü hatırla",
"saveBeforeRun": "Çalıştırmadan önce kaydet",
"splitDir": "Bölme yönü", "runLocation": "Çalıştırma yeri",
"terminalMode": "Terminal kipi", "lspSupport": "LSP Desteği",
"diagnostics": "Tanılama (hata / uyarı)",
"formatOnSave": "Kaydederken biçimlendir", "lintOnSave": "Kaydederken denetle",
"treeSitter": "Tree-Sitter (hat / parantez)",
"aiProvider": "Sağlayıcı", "editor": "Düzenleyici",
"fontFamily": "Yazı Tipi", "fontSize": "Yazı Boyutu",
"tabSize": "Sekme Boyutu", "minimap": "Mini Harita",
"wordWrap": "Sözcük Kaydır", "ligatures": "Bitişik Harfler",
"lineNumbers": "Satır Numaraları",
"terminalFontSize": "Terminal yazı boyutu",
"terminalScrollback": "Geri kaydırma (satır)",
"appearance": "Görünüm", "customAccent": "Özel Vurgu",
"fileIcons": "Dosya Simgeleri", "edit": "Düzenle",
"session": "Oturum", "autosave": "Otomatik kaydet",
"rememberSession": "Oturumu hatırla", "welcomePage": "Karşılama sayfası",
"language": "Dil", "internal": "Dahili", "external": "Harici",
"internalPanel": "Dahili panel", "externalTerminal": "Harici terminal",
"off": "Kapalı", "vertical": "Dikey", "horizontal": "Yatay",
"welcomeTitle": "Splash Code Studio",
"welcomeTagline": "Modern, hızlı ve YZ destekli kod düzenleyici",
"getStarted": "Başlayın", "shortcuts": "Klavye Kısayolları",
"recentFiles": "Son Dosyalar",
"cmdNewFile": "Yeni Dosya", "cmdOpenFile": "Dosya Aç",
"cmdOpenFolder": "Klasör Aç", "cmdSave": "Kaydet",
"cmdSaveAs": "Farklı Kaydet", "cmdRun": "Çalıştır",
"cmdTerminal": "Terminali Aç/Kapat", "cmdTheme": "Tema Galerisi",
"cmdSettings": "Ayarlar", "cmdSearch": "Projede Ara",
"cmdQuickOpen": "Hızlı Aç", "cmdAI": "YZ Paneli",
"cmdNotif": "Bildirimler", "cmdRefresh": "Yenile (Ağaç)",
"cmdGitRefresh": "Git Yenile",
"noResults": "Sonuç yok", "results": "sonuç",
"searchHint": "Bir proje açın ve aramak için yazın",
"closeTab": "Kapat", "closeOthers": "Diğerlerini Kapat",
"closeAll": "Tümünü Kapat",
"running": "Çalışıyor...", "finished": "bitti",
"error": "Hata", "success": "Başarılı", "warning": "Uyarı",
"loading": "Yükleniyor...", "emptyFolder": "Klasör boş",
}
# ===== /SC-I18N-028 =====
"""

# ══════════════════════════════════════════════════════════════
#  index.html INJECT — version gizle + dil adı düzelt
# ══════════════════════════════════════════════════════════════

HTML_INJECT = r"""
<!--SC-FIX-028-->
<style>
/* __APP_VERSION__ kalabaligini gizle (topbar + welcome) */
#brand .ver, .welcome-hero .version { display:none !important; }
</style>
<script>
(function(){
'use strict';
if(window.__SC028_FIX__) return;
window.__SC028_FIX__ = true;
/* Dil secicide "Turkce" -> "Türkçe" */
var nameFixes = { tr:'Türkçe' };
function fixLangDropdown(){
    var dd = document.getElementById('scLangDropdown');
    if(!dd || !dd.options || !dd.options.length) return false;
    for(var i=0;i<dd.options.length;i++){
        var v = dd.options[i].value;
        if(nameFixes[v]) dd.options[i].textContent = nameFixes[v];
    }
    return true;
}
var tries=0;
var t=setInterval(function(){
    tries++;
    if(tries>80){ clearInterval(t); return; }
    if(fixLangDropdown()) clearInterval(t);
},200);
})();
</script>
<!--/SC-FIX-028-->
"""

# ══════════════════════════════════════════════════════════════
#  ENGINE
# ══════════════════════════════════════════════════════════════

SKIP = {".git", ".venv", "venv", "node_modules", "_backups",
        ".idea", ".vscode", "dist", "build"}


def find_root(cli=None):
    c = []
    if cli:
        c.append(os.path.abspath(cli))
    here = os.path.dirname(os.path.abspath(__file__))
    c += [here, os.getcwd(), os.path.dirname(here)]
    for p in c:
        if p and os.path.isdir(os.path.join(p, "splash_code")):
            return p
    return c[0] if c else os.getcwd()


def rd(p):
    with open(p, "r", encoding="utf-8", newline="") as f:
        return f.read()


def wr(path, content):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".sctmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise


def strip_block(src, s, e):
    i = src.find(s)
    if i < 0:
        return src
    j = src.find(e, i)
    if j < 0:
        return src[:i]
    return src[:i] + src[j + len(e):]


def backup(root):
    bd = os.path.join(root, "_backups")
    os.makedirs(bd, exist_ok=True)
    zp = os.path.join(bd, "pre_patch%s_%s.zip"
                      % (PATCH_ID, time.strftime("%Y%m%d_%H%M%S")))
    n = 0
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, dn, fns in os.walk(root):
            dn[:] = [d for d in dn if d not in SKIP]
            for fn in fns:
                full = os.path.join(dp, fn)
                rel = os.path.relpath(full, root).replace("\\", "/")
                try:
                    if os.path.getsize(full) > 25 * 1024 * 1024:
                        continue
                    z.write(full, rel)
                    n += 1
                except Exception:
                    pass
    return zp, n


def restore(root, zp):
    if not os.path.isfile(zp):
        print("Backup yok: " + zp)
        return 1
    n = 0
    with zipfile.ZipFile(zp) as z:
        for name in z.namelist():
            t = os.path.join(root, name.replace("/", os.sep))
            try:
                os.makedirs(os.path.dirname(t), exist_ok=True)
                with open(t, "wb") as f:
                    f.write(z.read(name))
                n += 1
            except Exception:
                pass
    print("%d dosya geri yuklendi." % n)
    return 0


def check(root):
    api = rd(os.path.join(root, API_REL)) if os.path.isfile(os.path.join(root, API_REL)) else ""
    i18n = rd(os.path.join(root, I18N_REL)) if os.path.isfile(os.path.join(root, I18N_REL)) else ""
    idx = rd(os.path.join(root, HTML_REL)) if os.path.isfile(os.path.join(root, HTML_REL)) else ""
    print("\n  --- TANI ---")
    print("  api SC-TERM-028      : %s" % ("VAR" if API_MARK in api else "YOK"))
    print("  api eski schtasks    : %s" % ("VAR (eski yontem)" if "_sc010_open_win" in api else "YOK"))
    print("  i18n SC-I18N-028     : %s" % ("VAR" if I18N_MARK in i18n else "YOK"))
    print("  i18n Türkçe          : %s" % ("VAR" if "Türkçe" in i18n else "YOK"))
    print("  index SC-FIX-028     : %s" % ("VAR" if HTML_MARK in idx else "YOK"))
    print("  index version gizle  : %s" % ("VAR" if "#brand .ver" in idx else "YOK"))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument("--restore", metavar="ZIP")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    root = find_root(a.root)

    print("=" * 62)
    print("  Splash Code Studio - Patch %s" % PATCH_ID)
    print("  " + TITLE)
    print("=" * 62)
    print("  Kok: " + root)

    if a.restore:
        return restore(root, a.restore)
    if not os.path.isdir(os.path.join(root, "splash_code")):
        print("\n  HATA: splash_code/ yok.")
        return 1
    if a.check:
        return check(root)

    api_p = os.path.join(root, API_REL)
    i18n_p = os.path.join(root, I18N_REL)
    html_p = os.path.join(root, HTML_REL)
    if not os.path.isfile(api_p):
        print("api.py yok")
        return 1
    if not os.path.isfile(html_p):
        print("index.html yok")
        return 1

    # api.py append
    api_src = strip_block(rd(api_p), API_MARK, API_END)
    api_new = api_src + ("\n" if not api_src.endswith("\n") else "") + API_APPEND.strip("\n") + "\n"

    # i18n.py append (varsa)
    i18n_new = None
    if os.path.isfile(i18n_p):
        i18n_src = strip_block(rd(i18n_p), I18N_MARK, I18N_END)
        i18n_new = i18n_src + ("\n" if not i18n_src.endswith("\n") else "") + I18N_APPEND.strip("\n") + "\n"

    # index.html inject
    html_src = strip_block(rd(html_p), HTML_MARK, HTML_END)
    i = html_src.lower().rfind("</body>")
    if i < 0:
        print("</body> bulunamadi")
        return 2
    html_new = html_src[:i] + HTML_INJECT + html_src[i:]

    print("\n  Plan:")
    print("    %-34s APPEND (harici terminal fix)" % API_REL)
    if i18n_new is not None:
        print("    %-34s APPEND (Türkçe düzeltme)" % I18N_REL)
    print("    %-34s INJECT (version gizle + dil adı)" % HTML_REL)

    # Python compile ön-kontrol
    try:
        compile(api_new.encode("utf-8"), API_REL, "exec")
    except SyntaxError as e:
        print("  X api.py satir %s: %s" % (e.lineno, e.msg))
        return 2
    if i18n_new is not None:
        try:
            compile(i18n_new.encode("utf-8"), I18N_REL, "exec")
        except SyntaxError as e:
            print("  X i18n.py satir %s: %s" % (e.lineno, e.msg))
            return 2
    print("  Python compile: OK")

    if a.dry_run:
        print("\n  --dry-run: temiz.")
        return 0

    zp = None
    if not a.no_backup:
        print("\n  Backup...")
        zp, n = backup(root)
        print("    %s (%d dosya)" % (zp, n))

    touched = []
    try:
        wr(api_p, api_new)
        touched.append(API_REL)
        print("    + " + API_REL)
        if i18n_new is not None:
            wr(i18n_p, i18n_new)
            touched.append(I18N_REL)
            print("    + " + I18N_REL)
        wr(html_p, html_new)
        touched.append(HTML_REL)
        print("    + " + HTML_REL)
    except Exception as e:
        print("    YAZMA HATASI: %s" % e)
        if zp:
            restore(root, zp)
        return 1

    print("\n" + "=" * 62)
    print("  Patch %s UYGULANDI" % PATCH_ID)
    if zp:
        print("  Geri al: py path.py --restore \"%s\"" % zp)
    print("  Test: py main.py")
    print("    1) Ust bar ve karsilamada __APP_VERSION__ YOK")
    print("    2) Dil secicide 'Türkçe' yaziyor")
    print("    3) Dil=Türkçe -> menuler dogru TR karakterli")
    print("    4) Harici terminal: tree doluysa o klasorde,")
    print("       tree bossa cd'siz acilir ve ACIK KALIR")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
