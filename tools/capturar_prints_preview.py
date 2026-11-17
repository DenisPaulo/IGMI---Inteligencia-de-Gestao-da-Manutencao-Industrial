"""Captura os prints da PRÉVIA (docs/img/dashboard_*.png) a 1280 px. Requer Playwright + Chromium (fora do requirements).
Uso: python run.py all && python run.py preview && python tools/capturar_prints_preview.py"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "export" / "dashboard_preview.html"
IMG = ROOT / "docs" / "img"

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1)
    pg.goto(HTML.as_uri())
    pg.wait_for_load_state("networkidle")
    for aba, nome in (("geral", "dashboard_geral.png"), ("maquina", "dashboard_maquina.png"), ("linha", "dashboard_linha.png")):
        pg.click(f"nav button[data-aba={aba}]")
        pg.wait_for_timeout(400)
        pg.screenshot(path=str(IMG / nome), full_page=True)
        print(nome)
    b.close()
