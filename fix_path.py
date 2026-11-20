#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Patch 009 hotfix: find_root icindeki 'for c in c:' golgeleme hatasi.
# Fonksiyonu temiz surumle degistirir, path.py'yi derleyerek dogrular.

import os
import py_compile
import sys
import tempfile

TARGET = sys.argv[1] if len(sys.argv) > 1 else "path.py"

NEW_FUNC = [
    "def find_root(cli=None):",
    "    cands = []",
    "    if cli:",
    "        cands.append(os.path.abspath(cli))",
    "    here = os.path.dirname(os.path.abspath(__file__))",
    "    cands.append(here)",
    "    cands.append(os.getcwd())",
    "    cands.append(os.path.dirname(here))",
    "    for p in cands:",
    "        try:",
    "            if p and os.path.isdir(os.path.join(p, 'splash_code')):",
    "                return p",
    "        except Exception:",
    "            continue",
    "    return here",
    "",
    "",
]


def main():
    p = os.path.abspath(TARGET)
    if not os.path.isfile(p):
        print("Dosya yok: %s" % p)
        return 1

    with open(p, "r", encoding="utf-8", newline="") as f:
        src = f.read()

    nl = "\r\n" if "\r\n" in src else "\n"
    lines = src.split(nl)

    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("def find_root("):
            start = i
            break
    if start is None:
        print("find_root bulunamadi.")
        return 2

    end = start + 1
    while end < len(lines):
        ln = lines[end]
        if ln.strip() and not ln[0].isspace():
            break
        end += 1

    old = lines[start:end]
    if "cands" in "\n".join(old):
        print("Zaten duzeltilmis.")
    else:
        bak = p + ".bak"
        if not os.path.exists(bak):
            with open(bak, "w", encoding="utf-8", newline="") as f:
                f.write(src)
        lines = lines[:start] + NEW_FUNC + lines[end:]
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(nl.join(lines))
        print("find_root degistirildi: %d satir -> %d satir"
              % (len(old), len(NEW_FUNC)))
        print("Yedek: %s" % bak)

    print("Derleme kontrolu...")
    try:
        py_compile.compile(
            p,
            cfile=os.path.join(tempfile.gettempdir(), "sc009fix.pyc"),
            doraise=True)
    except Exception as e:
        print("HALA HATA: %s" % e)
        return 1

    print("OK. Simdi: py path.py --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
