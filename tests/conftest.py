import shutil

import pytest

from pmb import config, db


@pytest.fixture
def build(tmp_path):
    """Monta um warehouse em memória com crua num diretório temporário (nada toca raw/ do repo)."""
    def _b(entrada=None):
        return db.build(entrada=entrada, raw=tmp_path / "raw")
    return _b


@pytest.fixture
def con(build):
    return build()


@pytest.fixture
def entrada_copia(tmp_path):
    d = tmp_path / "entrada_csv"
    shutil.copytree(config.ENTRADA_CSV, d)
    return d
