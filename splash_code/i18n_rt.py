"""Splash Code Studio - i18n runtime"""
# ===== SC-RT-038 =====
# pack() ve translate_text() garantisi. Onceki bloklar yoksa da calisir.
try:
    ORDER
except NameError:
    ORDER = ["en", "de", "fr", "es", "it", "pt", "ru", "ja", "ko", "zh", "ar"]
try:
    P
except NameError:
    P = {}
try:
    PRE
except NameError:
    PRE = {}
try:
    WORD
except NameError:
    WORD = {}
try:
    LANG_TR
except NameError:
    LANG_TR = {
        "tr": "Türkçe", "en": "English", "de": "Deutsch", "fr": "Français",
        "es": "Español", "it": "Italiano", "pt": "Português", "ru": "Русский",
        "ja": "日本語", "ko": "한국어", "zh": "中文", "ar": "العربية",
    }


def pack(lang):
    lang = (lang or "tr").lower()
    if lang == "tr" or lang not in ORDER:
        return {"ok": True, "lang": "tr", "names": LANG_TR,
                "phrases": {}, "prefixes": {}, "words": {}}
    i = ORDER.index(lang)
    ph, pr, wd = {}, {}, {}
    for k, v in P.items():
        try:
            ph[k] = v[i]
        except Exception:
            pass
    for k, v in PRE.items():
        try:
            pr[k] = v[i]
        except Exception:
            pass
    for k, v in WORD.items():
        try:
            wd[k] = v[i]
        except Exception:
            pass
    return {"ok": True, "lang": lang, "names": LANG_TR,
            "phrases": ph, "prefixes": pr, "words": wd}


def translate_text(s, lang):
    try:
        if not s or not lang or lang == "tr" or lang not in ORDER:
            return s
        i = ORDER.index(lang)
        raw = str(s)
        key = raw.strip()
        if key in P:
            return raw.replace(key, P[key][i])
        out = raw
        for k, v in PRE.items():
            if key.startswith(k):
                out = raw.replace(k, v[i], 1)
                break
        for k, v in WORD.items():
            if k in out:
                out = out.replace(k, v[i])
        return out
    except Exception:
        return s
# ===== /SC-RT-038 =====
