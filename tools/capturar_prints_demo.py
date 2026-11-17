"""Prints de cada seção do dashboard demo, desktop (1400 px) e celular (390 px), com Chrome/Chromium headless.
Usa o modo "uma seção" do dashboard (#so-<seção>). Sem dependência Python extra.
Uso: python run.py simular demo demo-preview && python tools/capturar_prints_demo.py [pasta_saida]   (padrão: docs/img, prefixo demo_)"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "export" / "demo_dashboard.html"
# seção -> (altura desktop, altura celular)
SECOES = {"geral": (1250, 2500), "linha": (1050, 2300), "timeline": (760, 1050), "timeline-LT56": (760, 1050),
          "equipamento": (1900, 4600), "backlog": (1750, 5200), "alertas": (700, 1900), "pareto": (1150, 2300)}


def main(saida: Path, prefixo: str, telas=("desktop", "mobile")):
    chrome = next((c for c in ("google-chrome", "chromium", "chromium-browser", "chrome") if shutil.which(c)), None)
    if not chrome:
        sys.exit("Chrome/Chromium não encontrado")
    saida.mkdir(parents=True, exist_ok=True)
    for sec, (hd, hm) in SECOES.items():
        for tela in telas:
            w, h = (1400, hd) if tela == "desktop" else (390, hm)
            out = saida / f"{prefixo}{sec}_{tela}.png"
            subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", f"--window-size={w},{h}",
                            "--virtual-time-budget=5000", f"--screenshot={out}", f"{HTML.as_uri()}#so-{sec}"],
                           check=True, capture_output=True, timeout=120)
            print(out)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(Path(sys.argv[1]), "")
    else:
        main(ROOT / "docs" / "img", "demo_", telas=("desktop",))
