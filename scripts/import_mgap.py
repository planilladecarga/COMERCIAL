"""CLI técnica para ejecutar el motor de importación MGAP."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frimaral_bi.models import ImportConfig
from frimaral_bi.pipeline import MotorImportacionMGAP


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Importa el archivo oficial MGAP para FRIMARAL BI.")
    parser.add_argument("source", type=Path, help="Ruta al archivo XLSB del MGAP. CSV se acepta para pruebas técnicas.")
    parser.add_argument("--db", type=Path, default=Path("output/frimaral_bi.db"), help="Ruta de la base SQLite generada.")
    parser.add_argument("--normalized", type=Path, default=Path("output/mgap_normalizado.csv"), help="Copia normalizada generada.")
    parser.add_argument("--log", type=Path, default=Path("output/importacion_mgap_log.md"), help="Reporte de importación generado.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = ImportConfig(source_path=args.source, database_path=args.db, normalized_copy_path=args.normalized, log_path=args.log)
    result = MotorImportacionMGAP().run(config)
    print(f"Filas importadas: {result.stats.row_count}")
    print(f"Incidencias registradas: {len(result.issues)}")
    print(f"Base SQLite: {config.database_path}")


if __name__ == "__main__":
    main()
