"""
Splash Code Studio - Runners (SC-RUN-044)
Genel amacli calistirma: hangi dil varsa onu calistirir.
Runtime yoksa INSTALL komutlariyla (winget/apt/brew) kurulum onerilir.
Hicbir sey gomulmez; sistemde ne varsa o kullanilir.
"""
import os
import shutil
import subprocess
import sys

NAMES = {
    "python": "Python", "node": "Node.js", "go": "Go", "rust": "Rust",
    "java": "Java (JDK)", "gcc": "C/C++ derleyicisi (MinGW/gcc)",
    "ruby": "Ruby", "php": "PHP", "lua": "Lua", "perl": "Perl",
    "bash": "Bash", "powershell": "PowerShell", "pywinpty": "pywinpty",
    "ptyprocess": "ptyprocess",
}

MANUEL = {
    "rust": "https://rustup.rs",
    "go": "https://go.dev/dl",
    "java": "https://adoptium.net",
    "gcc": "https://www.mingw-w64.org",
}


def plat():
    if os.name == "nt":
        return "win"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def nowin():
    if os.name == "nt":
        return {"creationflags": 0x08000000}
    return {}


def find_bin(names):
    for n in names:
        w = shutil.which(n)
        if w:
            return w
    return None


def _out(p):
    base = os.path.splitext(p)[0]
    return base + (".exe" if os.name == "nt" else ".out")


def _cc(binp, p):
    o = _out(p)
    return '%s "%s" -o "%s" && "%s"' % (binp, p, o, o)


def _cxx(binp, p):
    o = _out(p)
    return '%s "%s" -o "%s" && "%s"' % (binp, p, o, o)


def _rs(binp, p, cwd):
    man = os.path.join(cwd or os.path.dirname(p), "Cargo.toml")
    if os.path.isfile(man):
        return [binp, "run", "--manifest-path", man]
    o = _out(p)
    return 'rustc "%s" -o "%s" && "%s"' % (p, o, o)


RUNNERS = {
    ".py":   {"rt": "python", "bin": ["python", "python3"],
              "cmd": lambda p, b, c: [b or sys.executable, "-u", p]},
    ".pyw":  {"rt": "python", "bin": ["python", "python3"],
              "cmd": lambda p, b, c: [b or sys.executable, "-u", p]},
    ".js":   {"rt": "node", "bin": ["node"], "cmd": lambda p, b, c: [b, p]},
    ".mjs":  {"rt": "node", "bin": ["node"], "cmd": lambda p, b, c: [b, p]},
    ".cjs":  {"rt": "node", "bin": ["node"], "cmd": lambda p, b, c: [b, p]},
    ".ts":   {"rt": "node", "bin": ["npx"],
              "cmd": lambda p, b, c: [b, "--yes", "tsx", p]},
    ".tsx":  {"rt": "node", "bin": ["npx"],
              "cmd": lambda p, b, c: [b, "--yes", "tsx", p]},
    ".go":   {"rt": "go", "bin": ["go"], "cmd": lambda p, b, c: [b, "run", p]},
    ".rs":   {"rt": "rust", "bin": ["cargo"], "cmd": _rs},
    ".java": {"rt": "java", "bin": ["java"], "cmd": lambda p, b, c: [b, p]},
    ".c":    {"rt": "gcc", "bin": ["gcc", "clang", "cc"], "cmd": _cc},
    ".cpp":  {"rt": "gcc", "bin": ["g++", "clang++", "c++"], "cmd": _cxx},
    ".cc":   {"rt": "gcc", "bin": ["g++", "clang++"], "cmd": _cxx},
    ".rb":   {"rt": "ruby", "bin": ["ruby"], "cmd": lambda p, b, c: [b, p]},
    ".php":  {"rt": "php", "bin": ["php"], "cmd": lambda p, b, c: [b, p]},
    ".lua":  {"rt": "lua", "bin": ["lua", "lua5.4", "lua5.3", "luajit"],
              "cmd": lambda p, b, c: [b, p]},
    ".pl":   {"rt": "perl", "bin": ["perl"], "cmd": lambda p, b, c: [b, p]},
    ".sh":   {"rt": "bash", "bin": ["bash", "sh"], "cmd": lambda p, b, c: [b, p]},
    ".ps1":  {"rt": "powershell", "bin": ["powershell", "pwsh"],
              "cmd": lambda p, b, c: [b, "-ExecutionPolicy", "Bypass",
                                      "-File", p]},
    ".bat":  {"rt": "powershell", "bin": ["cmd"],
              "cmd": lambda p, b, c: [b, "/c", p]},
    ".cmd":  {"rt": "powershell", "bin": ["cmd"],
              "cmd": lambda p, b, c: [b, "/c", p]},
    ".html": {"rt": "browser", "bin": [], "cmd": None},
    ".htm":  {"rt": "browser", "bin": [], "cmd": None},
}

INSTALL = {
    "node": {
        "win": ["winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements",
                "choco install -y nodejs-lts"],
        "linux": ["sudo apt-get install -y nodejs npm",
                  "sudo dnf install -y nodejs npm",
                  "sudo pacman -S --noconfirm nodejs npm"],
        "darwin": ["brew install node"],
    },
    "go": {
        "win": ["winget install -e --id GoLang.Go --accept-source-agreements --accept-package-agreements",
                "choco install -y golang"],
        "linux": ["sudo apt-get install -y golang-go", "sudo dnf install -y golang"],
        "darwin": ["brew install go"],
    },
    "rust": {
        "win": ["winget install -e --id Rustlang.Rust.MSVC --accept-source-agreements --accept-package-agreements"],
        "linux": ["curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y"],
        "darwin": ["brew install rust"],
    },
    "java": {
        "win": ["winget install -e --id Microsoft.OpenJDK.21 --accept-source-agreements --accept-package-agreements"],
        "linux": ["sudo apt-get install -y openjdk-21-jdk-headless",
                  "sudo dnf install -y java-21-openjdk-devel"],
        "darwin": ["brew install openjdk@21"],
    },
    "gcc": {
        "win": ["winget install -e --id Mingw-w64.Mingw-w64 --accept-source-agreements --accept-package-agreements",
                "choco install -y mingw"],
        "linux": ["sudo apt-get install -y build-essential",
                  "sudo dnf groupinstall -y 'Development Tools'"],
        "darwin": ["xcode-select --install"],
    },
    "ruby": {
        "win": ["winget install -e --id RubyInstallerTeam.RubyWithDevKit.3.3 --accept-source-agreements --accept-package-agreements"],
        "linux": ["sudo apt-get install -y ruby-full"],
        "darwin": ["brew install ruby"],
    },
    "php": {
        "win": ["winget install -e --id PHP.PHP.8.3 --accept-source-agreements --accept-package-agreements"],
        "linux": ["sudo apt-get install -y php-cli"],
        "darwin": ["brew install php"],
    },
    "lua": {
        "win": ["winget install -e --id LuaJIT.LuaJIT --accept-source-agreements --accept-package-agreements"],
        "linux": ["sudo apt-get install -y lua5.4"],
        "darwin": ["brew install lua"],
    },
    "perl": {
        "win": ["winget install -e --id StrawberryPerl.StrawberryPerl --accept-source-agreements --accept-package-agreements"],
        "linux": ["sudo apt-get install -y perl"],
        "darwin": ["brew install perl"],
    },
    "bash": {
        "linux": ["sudo apt-get install -y bash"],
        "darwin": ["brew install bash"],
    },
    "python": {
        "win": ["winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements"],
        "linux": ["sudo apt-get install -y python3"],
        "darwin": ["brew install python@3.12"],
    },
    "pywinpty": {
        "win": [sys.executable + " -m pip install --user pywinpty"],
        "linux": [sys.executable + " -m pip install --user ptyprocess"],
        "darwin": [sys.executable + " -m pip install --user ptyprocess"],
    },
    "ptyprocess": {
        "win": [sys.executable + " -m pip install --user ptyprocess"],
        "linux": [sys.executable + " -m pip install --user ptyprocess"],
        "darwin": [sys.executable + " -m pip install --user ptyprocess"],
    },
}


def install_cmds(rt):
    return INSTALL.get(rt, {}).get(plat(), [])


def detect_all():
    out = {}
    seen = set()
    for ext, spec in RUNNERS.items():
        rt = spec["rt"]
        if rt in seen or rt == "browser":
            continue
        seen.add(rt)
        out[rt] = bool(find_bin(spec["bin"])) if spec["bin"] else True
    return out
