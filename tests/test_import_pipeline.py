from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frimaral_bi.models import ImportConfig
from frimaral_bi.pipeline import MotorImportacionMGAP


def test_pipeline_creates_database_and_log(tmp_path):
    config = ImportConfig(
        source_path=Path("tests/fixtures/mgap_sample.csv"),
        database_path=tmp_path / "frimaral_bi.db",
        normalized_copy_path=tmp_path / "normalizado.csv",
        log_path=tmp_path / "log.md",
    )
    result = MotorImportacionMGAP().run(config)

    assert result.stats.row_count == 25
    assert config.database_path.exists()
    assert config.normalized_copy_path.exists()
    assert config.log_path.exists()

    with sqlite3.connect(config.database_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM movimientos").fetchone()[0] == 25
        assert conn.execute("SELECT COUNT(*) FROM empresas").fetchone()[0] >= 5
        # CALIRAL, ARBIZA, FRIGORIFICO TACUAREMBO y SAN JACINTO deben existir como empresas
        for nombre in ["CALIRAL", "ARBIZA", "FRIGORIFICO TACUAREMBO", "SAN JACINTO"]:
            row = conn.execute(
                "SELECT COUNT(*) FROM empresas WHERE nombre_normalizado = ?",
                (nombre,),
            ).fetchone()[0]
            assert row == 1, f"Empresa esperada faltante: {nombre}"
