"""
Splash Code Studio - İkon Sistemi
SVG ikon tanımları ve svg() yardımcı fonksiyonu
"""

# ── SVG İkon Path'leri ────────────────────────────────
ICONS = {
    "new_file": '<path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/><path d="M12 11v6"/><path d="M9 14h6"/>',
    "open": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "folder_open": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "save": '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8"/><path d="M7 3v5h8"/>',
    "save_as": '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><path d="M17 21v-8H7v8"/><path d="M20 14l-4 4-2-2"/>',
    "run": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "stop": '<rect x="6" y="6" width="12" height="12" rx="1"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-2.64-6.36"/><polyline points="21 3 21 9 15 9"/>',
    "folder_plus": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/>',
    "terminal": '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
    "split_v": '<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="12" y1="3" x2="12" y2="21"/>',
    "split_h": '<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="12" x2="21" y2="12"/>',
    "git": '<circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><line x1="6" y1="9" x2="6" y2="21"/>',
    "palette": '<circle cx="13.5" cy="6.5" r=".5"/><circle cx="17.5" cy="10.5" r=".5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.555-2.503 5.555-5.554C21.965 6.012 17.461 2 12 2z"/>',
    "file": '<path d="M14 3v4a1 1 0 0 0 1 1h4"/><path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "x": '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
    "plus": '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    "chevron": '<polyline points="9 18 15 12 9 6"/>',
    "chevron_down": '<polyline points="6 9 12 15 18 9"/>',
    "search": '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
    "welcome": '<path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>',
    "trash": '<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>',
    "command": '<path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 0 0 3-3z"/>',
    "sparkle": '<path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z"/>',
    "send": '<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>',
    "robot": '<rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><line x1="12" y1="7" x2="12" y2="11"/>',
    "bell": '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
    "history": '<path d="M3 12a9 9 0 1 0 3-6.7"/><polyline points="3 4 3 10 9 10"/><polyline points="12 7 12 12 15 15"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "py": '<path d="M9 3h6v3a3 3 0 0 1-3 3 3 3 0 0 1-3-3z"/><path d="M3 9h3a3 3 0 0 1 3 3 3 3 0 0 1-3 3H3z"/><path d="M9 21h6v-3a3 3 0 0 0-3-3 3 3 0 0 0-3 3z"/><path d="M21 9h-3a3 3 0 0 0-3 3 3 3 0 0 0 3 3h3z"/>',
    "js": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M8 16v-4h2"/><path d="M13 12v3a1 1 0 0 0 2 0"/>',
    "ts": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M8 9h4"/><line x1="10" y1="9" x2="10" y2="16"/>',
    "html": '<polyline points="4 5 3 19 12 22 21 19 20 5 12 3 4 5"/>',
    "css": '<polyline points="4 5 3 19 12 22 21 19 20 5 12 3 4 5"/><path d="M8 9h8l-1 5h-6"/>',
    "json": '<path d="M8 3H7a2 2 0 0 0-2 2v4a2 2 0 0 1-2 2 2 2 0 0 1 2 2v4a2 2 0 0 0 2 2h1"/><path d="M16 3h1a2 2 0 0 1 2 2v4a2 2 0 0 0 2 2 2 2 0 0 0-2 2v4a2 2 0 0 1-2 2h-1"/>',
    "md": '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M6 15v-6l2 3 2-3v6"/><path d="M15 15v-6l3 4v2"/>',
    "rs": '<circle cx="12" cy="12" r="9"/><path d="M8 12h4a2 2 0 0 0 0-4H8v8"/>',
    "go": '<rect x="3" y="6" width="18" height="12" rx="2"/><circle cx="9" cy="13" r="1.5"/>',
    "java": '<path d="M9 3c0 3-4 4-4 8 0 3 2 5 5 5"/><path d="M14 3c0 3 4 4 4 8 0 3-2 5-5 5"/><circle cx="12" cy="20" r="1"/>',
    "c": '<path d="M15 9a3 3 0 1 0 0 6"/>',
    "cpp": '<path d="M15 9a3 3 0 1 0 0 6"/><line x1="19" y1="9" x2="19" y2="12"/><line x1="17.5" y1="10.5" x2="20.5" y2="10.5"/>',
    "cs": '<path d="M15 9a3 3 0 1 0 0 6"/><line x1="19" y1="9" x2="19" y2="12"/><line x1="17.5" y1="10.5" x2="20.5" y2="10.5"/>',
    "sh": '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
    "sql": '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
    "txt": '<path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/><line x1="8" y1="12" x2="16" y2="12"/>',
    "img": '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="M21 15l-5-5-9 9"/>',
    "zip": '<rect x="4" y="3" width="16" height="18" rx="1"/><line x1="12" y1="3" x2="12" y2="9"/>',
    "lock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "xml": '<polyline points="9 6 4 12 9 18"/><polyline points="15 6 20 12 15 18"/>',
    "yaml": '<path d="M5 4l4 6v6"/><path d="M13 4l-4 6"/><path d="M5 16h8"/>',
    "toml": '<rect x="3" y="6" width="18" height="12" rx="2"/><line x1="7" y1="10" x2="17" y2="10"/>',
    "gitignore": '<circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M6 9v6a3 3 0 0 0 3 3h6"/>',
    "log": '<path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z"/><line x1="9" y1="12" x2="15" y2="12"/>',
    "logo": '<path d="M12 2L3 7v10l9 5 9-5V7z"/><path d="M8 9l4 2 4-2"/><path d="M12 11v6"/>',
}

# ── SVG Cache ─────────────────────────────────────────
_svg_cache = {}


def svg(name: str, size: int = 16) -> str:
    """İkon adından SVG string'i üretir (cache'li)."""
    key = (name, size)
    if key in _svg_cache:
        return _svg_cache[key]
    result = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" '
        f'height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round">'
        f'{ICONS.get(name, "")}</svg>'
    )
    _svg_cache[key] = result
    return result

# ===== SC-PATCH-003 =====
ICONS.setdefault('php', '<ellipse cx="12" cy="12" rx="10" ry="6"/><path d="M6 15l1.5-6h2a1.5 1.5 0 0 1 0 3h-2"/><path d="M12 15l1.5-6h2a1.5 1.5 0 0 1 0 3h-2"/>')
ICONS.setdefault('dart', '<path d="M5 12L12 3l7 7v9h-9z"/><path d="M12 3v9h7"/>')
ICONS.setdefault('swift', '<path d="M4 4c6 5 9 8 11 12"/><path d="M9 4c4 4 6 7 7 10"/><path d="M4 16c4 3 9 3 13 0"/>')
ICONS.setdefault('hs', '<path d="M3 4l6 8-6 8"/><path d="M9 4l6 8-6 8"/><path d="M15 10h6"/><path d="M17 14h4"/>')
ICONS.setdefault('ex', '<path d="M12 3c4 5 6 8 6 11a6 6 0 0 1-12 0c0-3 2-6 6-11z"/>')
ICONS.setdefault('wasm', '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M6 9l2 6 2-4 2 4 2-6"/><path d="M16 15v-5h2"/>')
ICONS.setdefault('docker', '<rect x="4" y="10" width="3" height="3"/><rect x="8" y="10" width="3" height="3"/><rect x="12" y="10" width="3" height="3"/><rect x="8" y="6" width="3" height="3"/><path d="M3 14c0 3 3 5 7 5s8-2 9-5"/>')
ICONS.setdefault('graphql', '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><circle cx="12" cy="3" r="1.4"/><circle cx="20" cy="7.5" r="1.4"/><circle cx="20" cy="16.5" r="1.4"/><circle cx="12" cy="21" r="1.4"/><circle cx="4" cy="16.5" r="1.4"/><circle cx="4" cy="7.5" r="1.4"/>')
_sc003_orig_svg = svg
def svg(name, size=16):
    # bilinmeyen isim -> 'file' (bos SVG donup ikon kaybolmasin)
    return _sc003_orig_svg(name if name in ICONS else 'file', size)
_svg_cache.clear()
# ===== /SC-PATCH-003 =====
