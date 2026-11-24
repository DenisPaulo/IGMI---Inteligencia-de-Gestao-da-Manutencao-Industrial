"""Renderiza saídas reais do terminal como PNG (docs/img/run_all.png, run_parada.png, pytest.png, tree.png).
Requer Playwright + Chromium (fora do requirements). Uso: python tools/capturar_prints_terminal.py"""
import html as H
import os
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "docs" / "img"
ENV = {**os.environ, "PYTHONUTF8": "1"}


def run(*args):
    r = subprocess.run([sys.executable, *args], cwd=ROOT, env=ENV, capture_output=True, text=True)
    return "\n".join(l.rstrip() for l in (r.stdout + r.stderr).splitlines()) + "\n"


def arvore():
    files = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=ROOT, capture_output=True, text=True).stdout.split()
    tree = {}
    for f in files:
        d = tree
        for p in f.split("/"):
            d = d.setdefault(p, {})
    out = ["IGMI/"]

    def walk(d, pre):
        ks = sorted(d, key=lambda k: (not d[k], k))
        for i, k in enumerate(ks):
            last = i == len(ks) - 1
            out.append(pre + ("└── " if last else "├── ") + k + ("/" if d[k] else ""))
            if d[k]:
                walk(d[k], pre + ("    " if last else "│   "))
    walk(tree, "")
    return "\n".join(out) + "\n"


def main():
    run("run.py", "clean")
    caps = {"run_all.png": ("python run.py all", run("run.py", "all")),
            "run_parada.png": ("python run.py parada", run("run.py", "parada"))}
    pyt = run("-m", "pytest", "-p", "no:cacheprovider")
    pyt = "\n".join("rootdir: IGMI" if l.startswith("rootdir:") else l for l in pyt.splitlines()) + "\n"
    caps["pytest.png"] = ("python run.py test", pyt)
    run("run.py", "clean")
    shutil.rmtree(ROOT / "export", ignore_errors=True)
    caps["tree.png"] = ("git ls-files | tree --fromfile", arvore())
    for _, t in caps.values():
        assert "/home/" not in t, "caminho absoluto no print"
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"])
        for nome, (titulo, corpo) in caps.items():
            pg = b.new_page(viewport={"width": 1100, "height": 800}, device_scale_factor=2)
            esc = H.escape(corpo)
            for a, c in (("OK ", "#3fb950"), ("FALHA", "#f85149")):
                esc = "\n".join(f"<span style='color:{c}'>{l[:10]}</span>{l[10:]}" if l.startswith(a) else l for l in esc.split("\n"))
            esc = "\n".join(f"<span style='color:#d2a8ff'>{l}</span>" if l.startswith("## ") else l for l in esc.split("\n"))
            pg.set_content(f"""<html><body style="margin:0;background:#0d1117"><div id=w style="font:13px/1.45 ui-monospace,Menlo,Consolas,monospace;
                color:#c9d1d9;padding:14px 16px 18px;width:max-content;min-width:780px"><div style="color:#8b949e;margin-bottom:8px">$ <b style="color:#58a6ff">{H.escape(titulo)}</b></div>
                <pre style="margin:0">{esc}</pre></div></body></html>""")
            box = pg.locator("#w").bounding_box()
            pg.set_viewport_size({"width": max(1100, int(box["width"]) + 40), "height": int(box["height"]) + 40})
            pg.locator("#w").screenshot(path=str(IMG / nome))
            pg.close()
            print(nome)
        b.close()


if __name__ == "__main__":
    main()
