"""
Splash Code Studio - Sabitler ve Yapılandırma
Paths, dosya uzantıları, LSP sunucuları, yerleşik tamamlamalar
"""
import sys
import os

# ── Uygulama Bilgisi ──────────────────────────────────
APP_NAME = "Splash Code Studio"
APP_VERSION = "3.0.0 - Modular"

# ── Dosya Yolları ─────────────────────────────────────
SETTINGS_DIR     = os.path.join(os.path.expanduser("~"), ".splash_code")
SETTINGS_FILE    = os.path.join(SETTINGS_DIR, "settings.json")
SETTINGS_BACKUP  = os.path.join(SETTINGS_DIR, "settings.json.bak")
SESSION_FILE     = os.path.join(SETTINGS_DIR, "session.json")
ICON_MAP_FILE    = os.path.join(SETTINGS_DIR, "icons.json")
THEMES_USER_FILE = os.path.join(SETTINGS_DIR, "themes_user.json")
CRASH_LOG        = os.path.join(SETTINGS_DIR, "error.log")

# ── Logo (base64 PNG, assets.py ile üretilir) ────────
SC_LOGO_DOSYA_YOLU = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "assets", "sc_logo.png"
)

# ── Sistem Fontları ───────────────────────────────────
SYSTEM_FONTS = [
    "JetBrains Mono", "Fira Code", "Cascadia Code", "Cascadia Mono",
    "Consolas", "Source Code Pro", "Ubuntu Mono", "Courier New",
    "Segoe UI", "Inter", "monospace", "sans-serif",
]

# ── Uzantı → Dil Eşlemesi ────────────────────────────
EXT_TO_LANG = {
    ".py": "python", ".pyw": "python", ".pyx": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".jsx": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".html": "html", ".htm": "html", ".xhtml": "html",
    ".css": "css", ".scss": "scss", ".sass": "scss", ".less": "less",
    ".json": "json", ".jsonc": "json", ".json5": "json",
    ".rs": "rust", ".go": "go", ".java": "java",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cxx": "cpp", ".cc": "cpp",
    ".hpp": "cpp", ".hxx": "cpp", ".cs": "csharp",
    ".md": "markdown", ".markdown": "markdown", ".mdx": "markdown",
    ".txt": "plaintext", ".text": "plaintext", ".log": "plaintext",
    ".sql": "sql",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".ps1": "powershell", ".psm1": "powershell", ".psd1": "powershell",
    ".bat": "bat", ".cmd": "bat",
    ".rb": "ruby", ".rake": "ruby", ".gemspec": "ruby",
    ".php": "php", ".lua": "lua", ".r": "r", ".rmd": "r",
    ".kt": "kotlin", ".kts": "kotlin", ".swift": "swift", ".dart": "dart",
    ".pl": "perl", ".pm": "perl", ".ex": "elixir", ".exs": "elixir",
    ".erl": "erlang", ".hrl": "erlang", ".hs": "haskell", ".lhs": "haskell",
    ".scala": "scala", ".sc": "scala", ".clj": "clojure", ".cljs": "clojure",
    ".vue": "html", ".svelte": "html",
    ".yaml": "yaml", ".yml": "yaml",
    ".toml": "ini", ".ini": "ini", ".conf": "ini", ".cfg": "ini",
    ".env": "ini",
    ".xml": "xml", ".svg": "xml", ".xsl": "xml", ".xsd": "xml",
    ".proto": "proto", ".graphql": "graphql", ".gql": "graphql",
    ".tf": "hcl", ".tfvars": "hcl",
    ".dockerfile": "dockerfile", ".makefile": "makefile", ".mk": "makefile",
    ".vim": "vim", ".asm": "asm", ".s": "asm",
    ".f": "fortran", ".f90": "fortran", ".f95": "fortran",
    ".nim": "nim", ".zig": "zig",
    ".v": "verilog", ".sv": "verilog", ".vhd": "vhdl", ".vhdl": "vhdl",
}


def get_lang(path: str) -> str:
    """Dosya yolundan dil kimliğini döndürür."""
    name = os.path.basename(path).lower()
    if name == "dockerfile" or name.startswith("dockerfile."):
        return "dockerfile"
    if name == "makefile" or name.startswith("makefile."):
        return "makefile"
    if name in (".gitignore", ".gitattributes", ".dockerignore",
                ".npmrc", ".prettierrc", ".eslintrc"):
        return "ini"
    return EXT_TO_LANG.get(os.path.splitext(name)[1].lower(), "plaintext")


# ── LSP Sunucu Komutları ─────────────────────────────
LSP_SERVERS = {
    "python":     [sys.executable, "-m", "basedpyright", "--stdio"],
    "rust":       ["rust-analyzer"],
    "go":         ["gopls"],
    "cpp":        ["clangd"], "c": ["clangd"],
    "csharp":     ["OmniSharp", "--languageserver"],
    "java":       ["jdtls"],
    "php":        ["intelephense", "--stdio"],
    "typescript": ["typescript-language-server", "--stdio"],
    "javascript": ["typescript-language-server", "--stdio"],
    "json":       ["vscode-json-languageserver", "--stdio"],
    "html":       ["vscode-html-languageserver", "--stdio"],
    "css":        ["vscode-css-languageserver", "--stdio"],
    "yaml":       ["yaml-language-server", "--stdio"],
    "docker":     ["docker-langserver", "--stdio"],
    "lua":        ["lua-language-server"],
    "bash":       ["bash-language-server", "start"],
    "cmake":      [sys.executable, "-m", "cmake_language_server"],
    "markdown":   ["marksman", "server"],
}

LSP_MONACO_IDS = set(LSP_SERVERS.keys())

LSP_INSTALL_CMDS = {
    "python":     [sys.executable, "-m", "pip", "install", "-U", "basedpyright"],
    "cmake":      [sys.executable, "-m", "pip", "install", "-U",
                   "cmake-language-server"],
    "typescript": ["npm", "install", "-g",
                   "typescript-language-server", "typescript"],
    "javascript": ["npm", "install", "-g",
                   "typescript-language-server", "typescript"],
    "json":       ["npm", "install", "-g", "vscode-langservers-extracted"],
    "php":        ["npm", "install", "-g", "intelephense"],
    "html":       ["npm", "install", "-g", "vscode-langservers-extracted"],
    "css":        ["npm", "install", "-g", "vscode-langservers-extracted"],
    "go":         ["go", "install", "golang.org/x/tools/gopls@latest"],
    "rust":       ["rustup", "component", "add", "rust-analyzer"],
    "yaml":       ["npm", "install", "-g", "yaml-language-server"],
    "docker":     ["npm", "install", "-g",
                   "dockerfile-language-server-nodejs"],
    "bash":       ["npm", "install", "-g", "bash-language-server"],
    "lua": None, "cpp": None, "c": None, "csharp": None, "java": None,
}

LSP_INSTALL_NOTES = {
    "cpp": "winget install LLVM.LLVM",
    "c": "winget install LLVM.LLVM",
    "csharp": "OmniSharp: github.com/OmniSharp/omnisharp-roslyn/releases",
    "java": "jdtls: download.eclipse.org/jdtls/milestones/",
}

# ── Yerleşik Tamamlama Sözlükleri ────────────────────
BUILTINS = {
    "python": [
        "print", "input", "len", "range", "str", "int", "float", "list",
        "dict", "set", "tuple", "bool", "type", "isinstance", "getattr",
        "setattr", "hasattr", "delattr", "open", "close", "read", "write",
        "append", "extend", "insert", "remove", "pop", "sort", "reverse",
        "keys", "values", "items", "update", "copy", "clear", "enumerate",
        "zip", "map", "filter", "sorted", "reversed", "sum", "min", "max",
        "abs", "round", "pow", "divmod", "hex", "oct", "bin", "chr", "ord",
        "repr", "hash", "id", "iter", "next", "all", "any", "callable",
        "vars", "dir", "globals", "locals", "True", "False", "None",
        "self", "cls", "super", "object", "Exception", "ValueError",
        "TypeError", "KeyError", "IndexError", "AttributeError",
        "ImportError", "RuntimeError", "NotImplementedError",
        "AssertionError", "def", "class", "import", "from", "as",
        "return", "yield", "if", "elif", "else", "for", "while", "break",
        "continue", "pass", "try", "except", "finally", "with", "async",
        "await", "lambda", "global", "nonlocal", "assert", "del", "raise",
        "in", "is", "not", "and", "or", "__init__", "__name__", "__main__",
        "__str__", "__repr__", "f-string", "format", "join", "split",
        "strip", "replace", "startswith", "endswith", "lower", "upper",
        "title", "capitalize",
    ],
    "javascript": [
        "console", "document", "window", "navigator", "function", "const",
        "let", "var", "if", "else", "for", "while", "do", "switch", "case",
        "break", "continue", "return", "true", "false", "null", "undefined",
        "new", "this", "class", "extends", "super", "constructor", "async",
        "await", "Promise", "Array", "Object", "String", "Number",
        "Boolean", "Math", "JSON", "Date", "RegExp", "Error", "TypeError",
        "console.log", "console.error", "setTimeout", "setInterval",
        "clearTimeout", "clearInterval", "parseInt", "parseFloat", "isNaN",
        "isFinite", "document.getElementById", "document.querySelector",
        "document.querySelectorAll", "addEventListener", "forEach", "map",
        "filter", "reduce",
    ],
    "typescript": [
        "interface", "type", "enum", "namespace", "declare", "readonly",
        "private", "public", "protected", "implements", "extends",
        "abstract", "as", "any", "unknown", "never", "void", "string",
        "number", "boolean",
    ],
    "go": [
        "func", "type", "struct", "interface", "map", "chan", "go",
        "defer", "select", "range", "package", "import", "var", "const",
        "nil", "true", "false", "make", "append", "len", "cap", "new",
        "delete", "close", "panic", "recover",
    ],
    "rust": [
        "fn", "let", "mut", "const", "static", "struct", "enum", "trait",
        "impl", "pub", "mod", "use", "crate", "self", "Self", "super",
        "match", "if", "else", "loop", "while", "for", "break", "continue",
        "return", "as", "in", "where", "unsafe", "async", "await", "move",
        "ref", "type", "dyn", "true", "false", "Some", "None", "Ok", "Err",
    ],
    "c": [
        "int", "char", "float", "double", "void", "long", "short",
        "unsigned", "signed", "struct", "union", "enum", "typedef",
        "sizeof", "return", "if", "else", "for", "while", "do", "switch",
        "case", "break", "continue", "goto", "const", "static", "extern",
        "register", "volatile", "NULL", "printf", "scanf", "malloc", "free",
        "strcpy", "strlen", "strcmp",
    ],
    "cpp": [
        "class", "public", "private", "protected", "virtual", "override",
        "template", "typename", "namespace", "using", "new", "delete",
        "this", "nullptr", "true", "false", "const", "static", "auto",
        "sizeof", "try", "catch", "throw",
    ],
    "java": [
        "public", "private", "protected", "class", "interface", "extends",
        "implements", "static", "final", "abstract", "void", "int", "char",
        "float", "double", "long", "short", "boolean", "String", "Object",
        "new", "this", "super", "null", "true", "false", "try", "catch",
        "finally", "throw", "throws", "if", "else", "for", "while", "do",
        "switch", "case", "break", "continue", "return", "package",
        "import", "System", "System.out.println",
    ],
    "csharp": [
        "public", "private", "protected", "internal", "class", "interface",
        "struct", "enum", "namespace", "using", "static", "readonly",
        "const", "void", "int", "char", "float", "double", "long",
        "string", "bool", "object", "new", "this", "base", "null", "true",
        "false", "try", "catch", "finally", "throw", "if", "else", "for",
        "foreach", "while", "do",
    ],
    "php": [
        "function", "class", "interface", "extends", "implements",
        "public", "private", "protected", "static", "const", "var",
        "echo", "print", "return", "if", "else", "elseif", "for",
        "foreach", "while", "do", "switch", "case", "break", "continue",
        "new", "null", "true", "false", "$this", "__construct", "isset",
        "unset", "empty", "array",
    ],
    "ruby": [
        "def", "class", "module", "end", "if", "else", "elsif", "unless",
        "while", "until", "for", "do", "begin", "rescue", "ensure",
        "raise", "return", "yield", "block_given?", "puts", "print", "p",
        "require", "require_relative", "attr_accessor",
    ],
    "lua": [
        "function", "local", "end", "if", "then", "else", "elseif", "for",
        "while", "repeat", "until", "do", "return", "break", "and", "or",
        "not", "nil", "true", "false", "print", "pairs", "ipairs",
        "table", "string", "math",
    ],
    "shell": [
        "if", "then", "else", "elif", "fi", "for", "while", "do", "done",
        "case", "esac", "function", "return", "exit", "echo", "printf",
        "read", "cd", "ls", "mkdir", "rm", "cp", "mv", "cat", "grep",
        "sed", "awk", "export",
    ],
    "powershell": [
        "function", "param", "if", "else", "elseif", "foreach", "for",
        "while", "do", "switch", "break", "continue", "return", "try",
        "catch", "finally", "throw", "Write-Host", "Write-Output",
        "Get-ChildItem", "Set-Location", "New-Item",
    ],
}

# ── Varsayılan İkon Eşlemesi ─────────────────────────
DEFAULT_ICON_MAP = {
    ".py": "py", ".js": "js", ".mjs": "js", ".cjs": "js", ".jsx": "js",
    ".ts": "ts", ".tsx": "ts",
    ".html": "html", ".htm": "html", ".vue": "html", ".svelte": "html",
    ".css": "css", ".scss": "css", ".sass": "css", ".less": "css",
    ".json": "json", ".jsonc": "json",
    ".md": "md", ".markdown": "md",
    ".rs": "rs", ".go": "go", ".java": "java",
    ".c": "c", ".h": "c", ".cpp": "cpp", ".cxx": "cpp", ".cc": "cpp",
    ".hpp": "cpp", ".cs": "cs",
    ".sh": "sh", ".bash": "sh", ".zsh": "sh", ".ps1": "sh",
    ".bat": "sh", ".cmd": "sh",
    ".rb": "sh", ".php": "php", ".lua": "sh", ".pl": "sh", ".r": "sh",
    ".sql": "sql", ".txt": "txt", ".text": "txt", ".log": "log",
    ".png": "img", ".jpg": "img", ".jpeg": "img", ".gif": "img",
    ".svg": "img", ".webp": "img", ".bmp": "img", ".ico": "img",
    ".zip": "zip", ".tar": "zip", ".gz": "zip", ".rar": "zip",
    ".7z": "zip",
    ".lock": "lock", ".xml": "xml",
    ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".ini": "toml", ".conf": "toml", ".env": "toml",
    ".gitignore": "gitignore",
    ".dart": "dart", ".swift": "swift",
    ".kt": "java", ".kts": "java",
    ".scala": "java", ".hs": "hs",
    ".ex": "ex", ".exs": "ex",
    ".astro": "html", ".prisma": "sql",
    ".graphql": "graphql", ".gql": "graphql",
    ".wasm": "wasm", ".dockerfile": "docker",
    ".editorconfig": "toml", ".npmrc": "toml",
}

# ── İkon Paketleri (renk paleti) ─────────────────────
ICON_PACKS = {
    "splash": {
        "name": "Splash", "desc": "Varsayılan renkli",
        "colors": {
            "py": "#3776AB", "js": "#F7DF1E", "ts": "#3178C6",
            "html": "#E34F26", "css": "#1572B6", "json": "#F5DE19",
            "md": "#6E9BC5", "rs": "#DEA584", "go": "#00ADD8",
            "java": "#ED8B00", "c": "#A8B9CC", "cpp": "#00599C",
            "cs": "#239120", "sh": "#4EAA25", "php": "#777BB4",
            "sql": "#336791", "img": "#E25A9B", "zip": "#F2C94C",
            "lock": "#E74C3C", "xml": "#E67E22", "yaml": "#CB3837",
            "toml": "#9B7653", "default": "#7D8590",
        },
    },
    "minimal": {
        "name": "Minimal", "desc": "Tek renk, sade",
        "colors": {k: "#9AA0A6" for k in [
            "py", "js", "ts", "html", "css", "json", "md", "rs", "go",
            "java", "c", "cpp", "cs", "sh", "php", "sql", "img", "zip",
            "lock", "xml", "yaml", "toml", "default",
        ]},
    },
    "neon": {
        "name": "Neon", "desc": "Parlak neon",
        "colors": {
            "py": "#00E5FF", "js": "#FFFF00", "ts": "#00FF9D",
            "html": "#FF2D95", "css": "#00B8FF", "json": "#FFD500",
            "md": "#B967FF", "rs": "#FF6B35", "go": "#00F0FF",
            "java": "#FF9F1C", "c": "#00FFC8", "cpp": "#00A8FF",
            "cs": "#BFFF00", "sh": "#39FF14", "php": "#C07DFF",
            "sql": "#FF3D71", "img": "#FF6B9D", "zip": "#FFE600",
            "lock": "#FF1744", "xml": "#FF9100", "yaml": "#FF4081",
            "toml": "#FFAB00", "default": "#E0E0E0",
        },
    },
    "pastel": {
        "name": "Pastel", "desc": "Yumuşak pastel",
        "colors": {
            "py": "#A8C5E5", "js": "#F5E6A0", "ts": "#A0C4E8",
            "html": "#F2A9A0", "css": "#A0C8E8", "json": "#E8D9A0",
            "md": "#C5D9E8", "rs": "#E8B8A0", "go": "#A0D8E0",
            "java": "#E8C5A0", "c": "#C0D0E0", "cpp": "#A8B8E8",
            "cs": "#B8D8B8", "sh": "#B8E0B8", "php": "#C8B8E8",
            "sql": "#A8C8D8", "img": "#F0B8D0", "zip": "#E8E0A0",
            "lock": "#E8A0A0", "xml": "#E8C0A0", "yaml": "#E0A0A0",
            "toml": "#D0B8A0", "default": "#B0B8C0",
        },
    },
}


def icon_pack_colors(name: str) -> dict:
    """İkon paketi renk paletini döndürür."""
    return (ICON_PACKS.get(name) or ICON_PACKS["splash"])["colors"]

# ===== SC-PATCH-003 =====
# get_lang() 'dockerfile'/'shell' dondurur ama LSP_SERVERS 'docker'/'bash' kullaniyordu.
for _old, _new in (('docker', 'dockerfile'), ('bash', 'shell')):
    if _old in LSP_SERVERS:
        LSP_SERVERS.setdefault(_new, LSP_SERVERS[_old])
        LSP_SERVERS.pop(_old, None)
    if _old in LSP_INSTALL_CMDS:
        LSP_INSTALL_CMDS.setdefault(_new, LSP_INSTALL_CMDS[_old])
        LSP_INSTALL_CMDS.pop(_old, None)
EXT_TO_LANG.setdefault('.cmake', 'cmake')
_sc003_orig_get_lang = get_lang
def get_lang(path):
    # CMakeLists.txt ve rc dosyalari icin dogru dil
    try:
        n = os.path.basename(str(path)).lower()
        if n == 'cmakelists.txt' or n.endswith('.cmake'):
            return 'cmake'
        if n in ('bashrc', '.bashrc', '.bash_profile', '.zshrc', '.profile'):
            return 'shell'
    except Exception:
        pass
    return _sc003_orig_get_lang(path)
LSP_MONACO_IDS.clear()
LSP_MONACO_IDS.update(LSP_SERVERS.keys())
# ===== /SC-PATCH-003 =====
