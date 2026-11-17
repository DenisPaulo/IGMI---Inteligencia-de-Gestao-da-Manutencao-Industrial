"""Contrato v0 do CSV de parada: validação apenas; hora_parada_min continua nula."""
import pytest

from pmb import config, parada

EXEMPLO = config.ROOT / "dados_sinteticos" / "parada" / "parada_exemplo.csv"


def _csv(tmp_path, corpo, nome="p.csv"):
    p = tmp_path / nome
    p.write_text("os_ref,hora_lancada,data_parada\n" + corpo, encoding="utf-8")
    return p


def test_exemplo_valido_e_11112222_lido_como_texto():
    assert parada.validar(EXEMPLO) == []
    _, rows = parada.ler(EXEMPLO)
    assert ("11112222", "0.92", None) in rows


@pytest.mark.parametrize("linha", ["4e5,1.00,", "ABCDEF12,1.00,", "1234567,1.00,", ",1.00,", "ffff0001,0,", "ffff0001,-1,", "ffff0001,00:30,", "ffff0001,1,5,", "ffff0001,1.00,01/10/2026"])
def test_linha_invalida(tmp_path, linha):
    assert parada.validar(_csv(tmp_path, linha + "\n")) != []


def test_cabecalho_fora_do_contrato(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("os,hora\nffff0001,1\n", encoding="utf-8")
    assert parada.validar(p)


def test_particao_imutavel_substitui_e_bloqueia_incremental(tmp_path):
    land = tmp_path / "landing"
    assert parada.registrar(EXEMPLO, "2026-10-12", land) == "OK"
    assert parada.registrar(EXEMPLO, "2026-10-13", land) == "SEM_MUDANCA"          # mesmo sha256: nada
    menor = _csv(tmp_path, "ffff0001,0.50,\n")
    with pytest.raises(ValueError, match="incremental"):
        parada.registrar(menor, "2026-10-13", land)
    maior = _csv(tmp_path, EXEMPLO.read_text(encoding="utf-8").split("\n", 1)[1] + "ffff0003,0.25,\n", "maior.csv")
    with pytest.raises(FileExistsError):
        parada.registrar(maior, "2026-10-12", land)
    assert parada.registrar(maior, "2026-10-13", land) == "OK"
    assert sorted(p.name for p in land.iterdir()) == ["data_carga=2026-10-12", "data_carga=2026-10-13"]


def test_fato_os_so_tem_hora_de_parada_sintetica(con):
    assert con.sql("SELECT count(*) FROM gold.fato_os WHERE hora_parada_min IS NOT NULL AND NOT starts_with(task_id, 'SINT-')").fetchone()[0] == 0
