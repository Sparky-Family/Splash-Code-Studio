"""
Splash Code Studio - AI Sağlayıcıları
Gemini ve Claude API entegrasyonu
"""
import json
import urllib.request
import urllib.error


def ai_gemini(key: str, model: str, messages: list) -> dict:
    """Google Gemini API ile sohbet."""
    if not key:
        return {"ok": False, "hata": "Gemini API key yok"}
    model = model or "gemini-2.5-flash"
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    contents = []
    for m in messages:
        role = "user" if m.get("role") == "user" else "model"
        contents.append({
            "role": role,
            "parts": [{"text": m.get("content", "")}],
        })
    body = json.dumps({"contents": contents}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        cands = data.get("candidates", [])
        if cands:
            parts = cands[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            return {"ok": True, "text": text}
        return {"ok": False, "hata": "Boş cevap"}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "ignore")[:300]
        return {"ok": False, "hata": f"HTTP {e.code}: {err}"}
    except Exception as e:
        return {"ok": False, "hata": str(e)}


def ai_claude(key: str, model: str, messages: list) -> dict:
    """Anthropic Claude API ile sohbet."""
    if not key:
        return {"ok": False, "hata": "Claude API key yok"}
    model = model or "claude-3-5-sonnet-20241022"
    sys_msg = ""
    msgs = []
    for m in messages:
        if m.get("role") == "system":
            sys_msg = m.get("content", "")
        else:
            msgs.append({
                "role": m.get("role", "user"),
                "content": m.get("content", ""),
            })
    payload = {"model": model, "max_tokens": 4096, "messages": msgs}
    if sys_msg:
        payload["system"] = sys_msg
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
        content = data.get("content", [])
        text = "".join(
            c.get("text", "") for c in content
            if c.get("type") == "text"
        )
        return {"ok": True, "text": text}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "ignore")[:300]
        return {"ok": False, "hata": f"HTTP {e.code}: {err}"}
    except Exception as e:
        return {"ok": False, "hata": str(e)}

# ===== SC-PATCH-003 =====
import json as _sc003_json
import urllib.request as _sc003_req
import urllib.error as _sc003_err
_SC003_GEMINI_DEFAULT = 'gemini-2.5-flash'
def ai_gemini(key, model, messages):
    # system mesaji 'model' rolune degil systemInstruction'a gidiyor
    if not key:
        return {'ok': False, 'hata': 'Gemini API key yok'}
    model = (model or _SC003_GEMINI_DEFAULT).strip()
    sys_parts, contents = [], []
    for m in (messages or []):
        role = m.get('role')
        txt = m.get('content') or ''
        if role == 'system':
            sys_parts.append(txt)
            continue
        contents.append({'role': 'user' if role == 'user' else 'model',
                         'parts': [{'text': txt}]})
    if not contents:
        return {'ok': False, 'hata': 'Bos mesaj'}
    if contents[0]['role'] != 'user':
        contents.insert(0, {'role': 'user', 'parts': [{'text': '(baglam)'}]})
    payload = {'contents': contents}
    if sys_parts:
        payload['systemInstruction'] = {'parts': [{'text': '\n\n'.join(sys_parts)}]}
    url = ('https://generativelanguage.googleapis.com/v1beta/models/'
           + model + ':generateContent')
    req = _sc003_req.Request(
        url, data=_sc003_json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'x-goog-api-key': key},
        method='POST')
    try:
        with _sc003_req.urlopen(req, timeout=90) as r:
            data = _sc003_json.loads(r.read().decode('utf-8'))
        cands = data.get('candidates') or []
        if not cands:
            fb = (data.get('promptFeedback') or {}).get('blockReason')
            return {'ok': False, 'hata': ('Engellendi: ' + fb) if fb else 'Bos cevap'}
        parts = (cands[0].get('content') or {}).get('parts') or []
        text = ''.join(p.get('text', '') for p in parts)
        if not text.strip():
            return {'ok': False, 'hata': 'Bos cevap'}
        return {'ok': True, 'text': text}
    except _sc003_err.HTTPError as e:
        try:
            err = e.read().decode('utf-8', 'ignore')[:400]
        except Exception:
            err = ''
        return {'ok': False, 'hata': 'HTTP %s: %s' % (e.code, err)}
    except Exception as e:
        return {'ok': False, 'hata': str(e)}
# ===== /SC-PATCH-003 =====
