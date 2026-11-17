"""Contrato v2 (proposta): schema coerente."""
import json
import re

from pmb import config

V2 = json.loads((config.CONTRATO / "parada_v2.schema.json").read_text(encoding="utf-8"))


def _rx(nome):
    return re.compile(next(c["regex"] for c in V2["colunas"] if c["nome"] == nome))


def test_v2_e_proposta():
    assert "NÃO vigente" in V2["status"]
    assert V2["carga"]["chave"] == ["id_lancamento"]


def test_regex_da_v2():
    assert _rx("os_ref").match("11112222") and not _rx("os_ref").match("1111222")
    assert _rx("hora_inicio").match("2026-04-02T08:15") and not _rx("hora_inicio").match("02/04/2026 08:15")
    for ok in ("20", "125"):
        assert _rx("duracao_min").match(ok)
    for ruim in ("0,33", "1.5", "00:20", "", "-5"):
        assert not _rx("duracao_min").match(ruim)

