from pathlib import Path

import pytest

from frimaral_bi.empresa360 import Empresa360
from frimaral_bi.models import ImportConfig
from frimaral_bi.pipeline import MotorImportacionMGAP


def build_database(tmp_path):
    database_path = tmp_path / "frimaral_bi.db"
    MotorImportacionMGAP().run(
        ImportConfig(
            source_path=Path("tests/fixtures/mgap_sample.csv"),
            database_path=database_path,
            normalized_copy_path=tmp_path / "normalizado.csv",
            log_path=tmp_path / "log.md",
        )
    )
    return database_path


def test_empresa360_builds_generic_company_profile(tmp_path):
    service = Empresa360(build_database(tmp_path))
    ficha = service.construir("Frigorifico Norte")

    assert ficha.informacion_general["nombre"] == "FRIGORIFICO NORTE"
    assert ficha.roles["productor"] is True
    assert ficha.indicadores["cantidad_movimientos"] == 3
    assert ficha.indicadores["kg_totales"] == 2669.0
    assert ficha.depositos_utilizados
    assert ficha.mercados
    assert ficha.productos
    assert ficha.cortes
    assert ficha.movimientos[0]["id_movimiento"] is not None


def test_empresa360_answers_reusable_commercial_questions(tmp_path):
    service = Empresa360(build_database(tmp_path))

    mercados = service.responder("Cert Uno", "¿Qué mercados trabaja Cert Uno?")
    productores = service.responder("Cert Uno", "¿Qué productores utilizan Cert Uno?")
    competidores = service.responder("Cert Uno", "¿Qué competidores tiene Cert Uno?")

    assert mercados
    assert productores
    assert isinstance(competidores, list)


def test_empresa360_reports_missing_company(tmp_path):
    service = Empresa360(build_database(tmp_path))
    with pytest.raises(ValueError):
        service.construir("Empresa Inexistente")
