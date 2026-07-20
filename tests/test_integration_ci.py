"""Test de integración end-to-end: pipeline → empresa360 → CI engine → workbook."""
from __future__ import annotations

import sqlite3
import zipfile
from pathlib import Path

from frimaral_bi.ci import CompetitiveIntelligenceEngine
from frimaral_bi.empresa360 import Empresa360
from frimaral_bi.models import ImportConfig
from frimaral_bi.pipeline import MotorImportacionMGAP
from frimaral_bi.workbook import MASTER_WORKBOOK_SHEETS, build_master_workbook


def test_end_to_end_pipeline_ci_workbook(tmp_path: Path) -> None:
    """Flujo completo: importar MGAP → Empresa360 → CI Engine → Workbook."""
    # 1) Pipeline: CSV → SQLite
    database_path = tmp_path / "frimaral_bi.db"
    MotorImportacionMGAP().run(
        ImportConfig(
            source_path=Path("tests/fixtures/mgap_sample.csv"),
            database_path=database_path,
            normalized_copy_path=tmp_path / "normalizado.csv",
            log_path=tmp_path / "log.md",
        )
    )
    assert database_path.exists()

    # 2) Empresa360 sigue funcionando
    ficha = Empresa360(database_path).construir("CALIRAL")
    assert ficha.informacion_general["nombre"] == "CALIRAL"

    # 3) CI Engine se ejecuta y persiste
    engine = CompetitiveIntelligenceEngine(database_path)
    resultado = engine.ejecutar("CALIRAL", persistir=True)
    assert resultado.resumen.total_competidores > 0
    assert 0 <= resultado.indices.indice_general <= 100

    # 4) Las tablas ci_* existen y tienen datos
    with sqlite3.connect(database_path) as conn:
        for tabla in ["ci_competencia", "ci_oportunidades", "ci_indices"]:
            n = conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
            assert n > 0, f"Tabla {tabla} vacía tras persistir"

    # 5) Workbook se genera con las 6 hojas CI nuevas
    workbook_path = tmp_path / "FRIMARAL_BI_Libro_Maestro.xlsx"
    build_master_workbook(database_path, workbook_path)
    assert workbook_path.exists()

    with zipfile.ZipFile(workbook_path) as z:
        wb_xml = z.read("xl/workbook.xml").decode()
        for sheet in MASTER_WORKBOOK_SHEETS:
            assert sheet in wb_xml, f"Hoja faltante: {sheet}"

        # Las hojas CI contienen datos
        ci_indices_idx = MASTER_WORKBOOK_SHEETS.index("45_CI_Indices") + 1
        ci_indices_xml = z.read(f"xl/worksheets/sheet{ci_indices_idx}.xml").decode()
        assert "CALIRAL" in ci_indices_xml or "Sin datos" in ci_indices_xml
