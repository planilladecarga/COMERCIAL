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
    ficha = service.construir("CALIRAL")

    assert ficha.informacion_general["nombre"] == "CALIRAL"
    assert ficha.roles["certificador"] is True
    # CALIRAL aparece como certificador en 11 movimientos del fixture ampliado
    assert ficha.indicadores["cantidad_movimientos"] >= 10
    assert ficha.indicadores["kg_totales"] > 0
    assert ficha.depositos_utilizados
    assert ficha.mercados
    assert ficha.productos
    assert ficha.cortes
    assert ficha.movimientos[0]["id_movimiento"] is not None


def test_empresa360_answers_reusable_commercial_questions(tmp_path):
    service = Empresa360(build_database(tmp_path))

    mercados = service.responder("CALIRAL", "¿Qué mercados trabaja CALIRAL?")
    productores = service.responder("CALIRAL", "¿Qué productores utilizan CALIRAL?")
    competidores = service.responder("CALIRAL", "¿Qué competidores tiene CALIRAL?")

    assert mercados
    assert productores
    assert isinstance(competidores, list)


def test_empresa360_reports_missing_company(tmp_path):
    service = Empresa360(build_database(tmp_path))
    with pytest.raises(ValueError):
        service.construir("Empresa Inexistente")
