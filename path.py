#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Splash Code Studio - Patch 046 "Sessiz IDE + Logo Flip"
1) Toast/bildirim politikasi: sadece ONEMLI mesajlar gosterilir
   (error her zaman; warning/success yalnizca kritik anahtar kelimeler)
2) Karsilama ekraninda logo altina ikon-only flip butonu:
   logo 3D doner, altindan assets/company_logo.png cikar
3) company_logo.png HTML'e base64 gomulur -> exe/her PC guvenli

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

PATCH_ID = "046"
TITLE = "Sessiz bildirim politikasi + logo flip (company logo)"
HB_REL = "splash_code/html_builder.py"
HTML_REL = "splash_code/templates/index.html"
LOGO_REL = "assets/company_logo.png"
HB_MARK = "# ===== SC-FLIP-046 ====="
HB_END = "# ===== /SC-FLIP-046 ====="
HTML_MARK = "<!--SC-FLIP-046-->"
HTML_END = "<!--/SC-FLIP-046-->"

HB_APPEND = r'''
# ===== SC-FLIP-046 =====
# company_logo.png -> base64 (HTML'e gomulu; exe/path bagimsiz)
import base64 as _sc046_b64
import os as _sc046_os

_sc046_orig_build = build_html


def _sc046_company_b64():
    try:
        p = _sc046_os.path.join(
            _sc046_os.path.dirname(_sc046_os.path.abspath(__file__)),
            "..", "assets", "company_logo.png")
        p = _sc046_os.path.normpath(p)
        if _sc046_os.path.isfile(p) and _sc046_os.path.getsize(p) > 32:
            with open(p, "rb") as f:
                return ("data:image/png;base64," +
                        _sc046_b64.b64encode(f.read()).decode("ascii"))
    except Exception:
        pass
    return ""


def build_html(settings):
    html = _sc046_orig_build(settings)
    try:
        html = html.replace("__SC_COMPANY_LOGO__", _sc046_company_b64())
    except Exception:
        try:
            html = html.replace("__SC_COMPANY_LOGO__", "")
        except Exception:
            pass
    return html


try:
    _build_cache.clear()
except Exception:
    pass
# ===== /SC-FLIP-046 =====
'''

INJECT = r"""
<!--SC-FLIP-046-->
<script>window.SC_COMPANY_LOGO="__SC_COMPANY_LOGO__";</script>
<style>
/* === logo flip === */
#welcomeView .logo-big{position:relative;perspective:900px}
.sc-flipcard{width:100%;height:100%;position:relative;transform-style:preserve-3d}
.sc-flip-inner{width:100%;height:100%;position:relative;transform-style:preserve-3d;
  transition:transform .75s cubic-bezier(.2,.85,.25,1)}
.sc-flipcard.flipped .sc-flip-inner{transform:rotateY(180deg)}
.sc-face{position:absolute;inset:0;backface-visibility:hidden;-webkit-backface-visibility:hidden;
  display:flex;align-items:center;justify-content:center}
.sc-face img,.sc-face svg{width:100%;height:100%;object-fit:contain;border:none;background:none;box-shadow:none}
.sc-back{transform:rotateY(180deg)}
.sc-flip-btn{margin:12px auto 0;display:flex;align-items:center;justify-content:center;
  width:34px;height:34px;border-radius:50%;border:1px solid var(--border);
  background:var(--bg-alt);color:var(--dim);cursor:pointer;transition:.25s;padding:0}
.sc-flip-btn:hover{color:var(--accent);border-color:var(--accent);transform:rotate(180deg) scale(1.06)}
.sc-flip-btn:active{transform:rotate(180deg) scale(.94)}
.sc-flip-btn svg{width:15px;height:15px;pointer-events:none}
</style>
<script>
(function(){
'use strict';
if(window.__SC046__)return;
window.__SC046__=true;

/* ═════════ 1) SESSIZ BILDIRIM POLITIKASI ═════════
   error      -> HER ZAMAN goster
   warning    -> sadece kritik (veri kaybi / kurulum / bulunamiyor / izin)
   success/info-> sadece kritik; digerleri SESSIZce gecilir            */
var CRIT=/(unsaved|kaydedilmemi|delete|silinsin|large|büyük|buyuk|install|kurul|missing|eksik|not\s?found|bulunamad|fail|başarısız|basarisiz|olmadı|olmadi|error|hata|cannot|could\s?not|yetki|permission|denied|reddedildi|invalid|geçersiz|gectersiz|crash|çök|cök|desteklenmiyor|supported)/i;
function installGate(){
  if(typeof window.toast!=="function"||window.toast.__sc046gate)return;
  var prev=window.toast;
  function gate(m,t,d){
    if(window.__sc046verbose)return prev(m,t,d);
    var type=t||"info";
    var msg=String(m==null?"":m);
    if(type==="error")return prev(m,t,d);
    if(CRIT.test(msg))return prev(m,t,d);
    return undefined; /* sessiz */
  }
  gate.__sc046gate=true;
  window.toast=gate;
  window.scToast=gate;
  try{window.sc23Toast=gate;}catch(e){}
}
installGate();
window.scToastVerbose=function(on){window.__sc046verbose=!!on;};

/* ═════════ 2) LOGO FLIP (ikon-only buton) ═════════ */
var FLIP_ICON='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/></svg>';
function augmentWelcome(){
  var hero=document.querySelector('#welcomeView .welcome-hero');
  if(!hero)return;
  var big=hero.querySelector('.logo-big');
  if(!big||big.dataset.sc046)return;
  big.dataset.sc046="1";
  var company=window.SC_COMPANY_LOGO||"";
  var card=document.createElement('div');card.className='sc-flipcard';
  var inner=document.createElement('div');inner.className='sc-flip-inner';
  var front=document.createElement('div');front.className='sc-face sc-front';
  var back=document.createElement('div');back.className='sc-face sc-back';
  while(big.firstChild)front.appendChild(big.firstChild);
  if(company){
    var img=document.createElement('img');
    img.src=company;img.alt="";img.draggable=false;
    back.appendChild(img);
  }else{
    back.appendChild(front.cloneNode(true).firstChild||document.createElement('span'));
  }
  inner.appendChild(front);inner.appendChild(back);
  card.appendChild(inner);
  big.appendChild(card);
  if(company){
    var btn=document.createElement('button');
    btn.type="button";btn.className="sc-flip-btn";
    btn.setAttribute("aria-label","logo");btn.title="";
    btn.innerHTML=FLIP_ICON;
    btn.addEventListener("click",function(ev){
      ev.preventDefault();ev.stopPropagation();
      card.classList.toggle("flipped");
    });
    if(big.nextSibling)hero.insertBefore(btn,big.nextSibling);
    else hero.appendChild(btn);
  }
}
var _origShow=window.showWelcome;
window.showWelcome=function(){
  var r;
  try{ r=_origShow?_origShow.apply(this,arguments):undefined; }catch(e){}
  setTimeout(augmentWelcome,0);
  setTimeout(augmentWelcome,120);
  return r;
};
/* acilista welcome zaten acikssa da yakala */
setTimeout(augmentWelcome,400);
setTimeout(augmentWelcome,1200);
})();
</script>
<!--/SC-FLIP-046-->
"""

SKIP = {".git", ".venv", "venv", "node_modules", "_backups", "_archive",
        ".idea", ".vscode", "dist", "build", "__pycache__"}


def find_root(cli=None):
    c = []
    if cli:
        c.append(os.path.abspath(cli))
    here = os.path.dirname(os.path.abspath(__file__))
    c += [here, os.getcwd(), os.path.dirname(here)]
    for p in c:
        if p and os.path.isdir(os.path.join(p, "splash_code")):
            return p
    return here


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


def pycache(root):
    t = []
    for dp, dn, fn in os.walk(root):
        if os.path.basename(dp) == "__pycache__":
            t.append(dp); dn[:] = []; continue
        dn[:] = [d for d in dn if d not in SKIP]
    for x in t:
        shutil.rmtree(x, ignore_errors=True)
    return len(t)

def check(root):
    def g(rel):
        p = os.path.join(root, rel)
        return rd(p) if os.path.isfile(p) else ""
    hb, idx = g(HB_REL), g(HTML_REL)
    lp = os.path.join(root, LOGO_REL)
    print("\n  --- TANI ---")
    print("  html_builder SC-FLIP-046 : %s" % ("VAR" if HB_MARK in hb else "YOK"))
    print("  index SC-FLIP-046        : %s" % ("VAR" if HTML_MARK in idx else "YOK"))
    print("  toast gate               : %s" % ("VAR" if "__sc046gate" in idx else "YOK"))
    print("  flip butonu              : %s" % ("VAR" if "sc-flip-btn" in idx else "YOK"))
    if os.path.isfile(lp):
        print("  assets/company_logo.png  : VAR (%.1f KB)"
              % (os.path.getsize(lp) / 1024.0))
    else:
        print("  assets/company_logo.png  : YOK -> flip butonu gizlenir")
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
        print("splash_code/ yok")
        return 1
    if a.check:
        return check(root)

    hb_p = os.path.join(root, HB_REL)
    html_p = os.path.join(root, HTML_REL)
    if not os.path.isfile(hb_p) or not os.path.isfile(html_p):
        print("html_builder.py / index.html yok")
        return 1

    hb_src = strip_block(rd(hb_p), HB_MARK, HB_END)
    hb_new = hb_src + ("\n" if not hb_src.endswith("\n") else "") \
        + HB_APPEND.strip("\n") + "\n"

    html_src = strip_block(rd(html_p), HTML_MARK, HTML_END)
    i = html_src.lower().rfind("</body>")
    if i < 0:
        print("</body> bulunamadi")
        return 2
    html_new = html_src[:i] + INJECT + html_src[i:]

    print("\n  On-kontrol...")
    try:
        compile(hb_new.encode("utf-8"), HB_REL, "exec")
    except SyntaxError as e:
        print("  X html_builder satir %s: %s" % (e.lineno, e.msg))
        return 2
    print("  Python OK")

    print("\n  Plan:")
    print("    %-34s APPEND (company logo base64)" % HB_REL)
    print("    %-34s INJECT (toast gate + flip)" % HTML_REL)

    if a.dry_run:
        print("\n  --dry-run: temiz.")
        return 0

    zp = None
    if not a.no_backup:
        zp, n = backup(root)
        print("\n  Backup: %s (%d dosya)" % (zp, n))

    touched = []
    try:
        wr(hb_p, hb_new); touched.append(HB_REL)
        wr(html_p, html_new); touched.append(HTML_REL)
        for t in touched:
            print("    + " + t)
    except Exception as e:
        print("    YAZMA HATASI: %s" % e)
        if zp:
            restore(root, zp)
        return 1

    bad = []
    for rel in touched:
        if rel.endswith(".py"):
            try:
                py_compile.compile(os.path.join(root, rel),
                                   cfile=os.path.join(tempfile.gettempdir(), "sc046.pyc"),
                                   doraise=True)
            except Exception as e:
                bad.append((rel, str(e)))
    if bad:
        for rel, err in bad:
            print("    X %s: %s" % (rel, err))
        if zp:
            restore(root, zp)
        return 1
    print("    OK · %d __pycache__ silindi" % pycache(root))

    print("\n" + "=" * 62)
    print("  Patch %s UYGULANDI" % PATCH_ID)
    if zp:
        print("  Geri al: py path.py --restore \"%s\"" % zp)
    print("  Bildirim politikasi:")
    print("    error                -> HER ZAMAN")
    print("    warning/success/info -> sadece kritik (kayip/kurulum/hata)")
    print("    'Kaydedildi', 'Terminal kapandi', 'Kopyalandi'... -> SESSIZ")
    print("    Acip kapamak icin konsol: scToastVerbose(true)")
    print("  Flip: karsilama ekrani -> logo altindaki yuvarlak ikon butonu")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
