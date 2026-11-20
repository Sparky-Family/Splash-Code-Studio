#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Splash Code Studio - Patch 014 (FIXED)
Oturum & Proje Hatırlama Fix

    py path.py --check
    py path.py --dry-run
    py path.py
"""

import argparse
import os
import py_compile
import shutil
import sys
import tempfile
import time
import zipfile

PATCH_ID = "014"
TITLE = "Oturum & Proje Hatırlama Fix"
API_REL = "splash_code/api.py"
HTML_REL = "splash_code/templates/index.html"
PY_MARK = "# ===== SC-SESSION-014 ====="
PY_END = "# ===== /SC-SESSION-014 ====="
HTML_MARK = "<!--SC-SESSION-014-->"
HTML_END = "<!--/SC-SESSION-014-->"

# ══════════════════════════════════════════════════════════════
#  api.py APPEND
# ══════════════════════════════════════════════════════════════

API_APPEND = r"""
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
"""

# ══════════════════════════════════════════════════════════════
#  index.html INJECT — tab restoration
# ══════════════════════════════════════════════════════════════

HTML_INJECT = r"""
<!--SC-SESSION-014-->
<script>
(function(){
'use strict';
if(window.__SC014__)return;
window.__SC014__=true;

var attempts=0;
var timer=setInterval(function(){
  attempts++;
  if(attempts>120){clearInterval(timer);return;}
  // App hazir mi?
  if(!window.pywebview||!window.pywebview.api)return;
  if(!window.tabs)return;
  if(typeof dosyaAcYol!=='function')return;
  if(window._sc014_done)return;
  window._sc014_done=true;
  clearInterval(timer);

  var a=window.pywebview.api;
  a.oturum_yukle().then(function(sess){
    if(!sess||!sess.tabs||!sess.tabs.length)return;
    if(!window.settings||!window.settings.rememberSession)return;

    var count=0;
    sess.tabs.forEach(function(t){
      if(t.path){
        dosyaAcYol(t.path);
        count++;
      }
    });

    // Aktif sekmeyi ayarla
    if(count>0){
      setTimeout(function(){
        var target=null;
        if(sess.activeTab!=null){
          target=window.tabs.find(function(x){return x.id===sess.activeTab;});
        }
        if(!target&&window.tabs.length)target=window.tabs[0];
        if(target&&typeof aktifSekmeYap==='function')aktifSekmeYap(target.id);
      },count*250+600);
    }
  }).catch(function(){});
},250);
})();
</script>
<!--/SC-SESSION-014-->
"""

# ══════════════════════════════════════════════════════════════
#  MOTOR
# ══════════════════════════════════════════════════════════════

SKIP = {".git", ".venv", "venv", "node_modules", "_backups",
        ".idea", ".vscode", "dist", "build"}
MAXB = 25 * 1024 * 1024


def find_root(cli=None):
    cands = []
    if cli:
        cands.append(os.path.abspath(cli))
    here = os.path.dirname(os.path.abspath(__file__))
    cands += [here, os.getcwd(), os.path.dirname(here)]
    for p in cands:
        if p and os.path.isdir(os.path.join(p, "splash_code")):
            return p
    return cands[0] if cands else os.getcwd()


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


def strip_block(src, start, end):
    i = src.find(start)
    if i < 0:
        return src
    j = src.find(end, i)
    if j < 0:
        return src[:i]
    return src[:i] + src[j + len(end):]


def pycache(root):
    targets = []
    for dp, dn, fn in os.walk(root):
        if os.path.basename(dp) == "__pycache__":
            targets.append(dp)
            dn[:] = []
            continue
        dn[:] = [d for d in dn if d not in SKIP]
    for t in targets:
        shutil.rmtree(t, ignore_errors=True)
    return len(targets)


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
                    if os.path.getsize(full) > MAXB:
                        continue
                    z.write(full, rel)
                    n += 1
                except Exception:
                    pass
    return zp, n


def make_plan(root):
    ops = []
    probs = []

    # api.py
    ap = os.path.join(root, API_REL)
    if not os.path.isfile(ap):
        probs.append(API_REL + " yok")
    else:
        src = rd(ap)
        src = strip_block(src, PY_MARK, PY_END)
        if PY_MARK in rd(ap):
            ops.append((API_REL, None, "ZATEN"))
        else:
            body = API_APPEND.strip("\n")
            new = src if src.endswith("\n") else src + "\n"
            new += "\n" + body + "\n"
            ops.append((API_REL, new, "append"))

    # index.html
    hp = os.path.join(root, HTML_REL)
    if not os.path.isfile(hp):
        probs.append(HTML_REL + " yok")
    else:
        src = rd(hp)
        src = strip_block(src, HTML_MARK, HTML_END)
        if HTML_MARK in rd(hp):
            ops.append((HTML_REL, None, "ZATEN"))
        else:
            low = src.lower()
            i = low.rfind("</body>")
            if i < 0:
                probs.append(HTML_REL + ": </body> yok")
            else:
                new = src[:i] + HTML_INJECT + src[i:]
                ops.append((HTML_REL, new, "inject"))

    return ops, probs


def verify(root, rels):
    bad = []
    for rel in rels:
        if not rel.endswith(".py"):
            continue
        try:
            py_compile.compile(
                os.path.join(root, rel),
                cfile=os.path.join(tempfile.gettempdir(), "sc014.pyc"),
                doraise=True)
        except Exception as e:
            bad.append((rel, str(e)))
    return bad


def rollback(root, zp, rels):
    print("  ! GERI ALINIYOR")
    try:
        with zipfile.ZipFile(zp) as z:
            names = set(z.namelist())
            for rel in rels:
                k = rel.replace("\\", "/")
                if k in names:
                    with open(os.path.join(root, rel), "wb") as f:
                        f.write(z.read(k))
                    print("    geri: " + rel)
    except Exception as e:
        print("    GERI ALMA BASARISIZ: %s" % e)
        print("    Elle ac: %s" % zp)


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
    pycache(root)
    print("%d dosya geri yuklendi." % n)
    return 0


def check(root):
    print("\n  --- TANI ---")

    def g(rel):
        try:
            return rd(os.path.join(root, rel))
        except Exception:
            return ""

    api = g(API_REL)
    idx = g(HTML_REL)
    print("  api rememberProject fix  : %s"
          % ("VAR" if "_sc014_init" in api else "YOK"))
    print("  api rememberSession fix  : %s"
          % ("VAR" if "_sc014_oturum_yukle" in api else "YOK"))
    print("  index tab restoration    : %s"
          % ("VAR" if HTML_MARK in idx else "YOK"))
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

    print("=" * 64)
    print("  Splash Code Studio - Patch %s (FIXED)" % PATCH_ID)
    print("  " + TITLE)
    print("=" * 64)
    print("  Kok: " + root)

    if a.restore:
        return restore(root, a.restore)
    if not os.path.isdir(os.path.join(root, "splash_code")):
        print("\n  HATA: splash_code/ yok.")
        return 1
    if a.check:
        return check(root)

    ops, probs = make_plan(root)
    print("\n  Plan:")
    for item in ops:
        print("    %-34s %s" % (item[0], item[2]))
    if probs:
        print("\n  !! SORUN:")
        for x in probs:
            print("     - " + x)
        return 2

    # todo: sadece icerigi olanlari yaz
    todo = []
    for item in ops:
        if item[1] is not None:
            todo.append(item)

    if not todo:
        print("\n  Zaten uygulanmis.")
        return 0
    if a.dry_run:
        print("\n  --dry-run: temiz. (%d dosya)" % len(todo))
        return 0

    zp = None
    if not a.no_backup:
        print("\n  Backup...")
        zp, n = backup(root)
        print("    %s (%d dosya)" % (zp, n))

    touched = []
    try:
        for item in todo:
            rel = item[0]
            content = item[1]
            wr(os.path.join(root, rel), content)
            touched.append(rel)
            print("    + " + rel)
    except Exception as e:
        print("    YAZMA HATASI: %s" % e)
        if zp:
            rollback(root, zp, touched)
        return 1

    print("\n  Dogrulama...")
    bad = verify(root, touched)
    if bad:
        for rel, err in bad:
            print("    X %s\n      %s" % (rel, err))
        if zp:
            rollback(root, zp, touched)
        return 1
    print("    OK  ·  %d __pycache__ silindi" % pycache(root))

    print("\n" + "=" * 64)
    print("  Patch %s UYGULANDI" % PATCH_ID)
    if zp:
        print("  Geri al: py path.py --restore \"%s\"" % zp)
    print("  Test: py main.py")
    print("    1) Ayarlar > 'Oturumu hatırla' AÇIK")
    print("    2) Birkaç dosya aç, IDE'yi kapat")
    print("    3) Tekrar aç -> sekmeler geri gelmeli")
    print("    4) Ayarlar > 'Proje klasörünü hatırla' AÇIK")
    print("    5) Klasör aç, IDE'yi kapat")
    print("    6) Tekrar aç -> tree geri gelmeli")
    print("    7) Her iki ayarı KAPAT -> yeniden başlat")
    print("    8) Sekmeler ve tree boş gelmeli")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    sys.exit(main())
