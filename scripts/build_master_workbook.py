"""CLI para generar el Libro Maestro BI desde la base SQLite normalizada."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frimaral_bi.workbook import build_master_workbook


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera FRIMARAL_BI_Libro_Maestro.xlsx desde SQLite.")
    parser.add_argument("--db", type=Path, default=Path("output/frimaral_bi.db"), help="Base SQLite creada por el Sprint 2.")
    parser.add_argument("--output", type=Path, default=Path("output/FRIMARAL_BI_Libro_Maestro.xlsx"), help="Libro Maestro XLSX a generar.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_master_workbook(args.db, args.output)
    print(f"Libro Maestro creado: {args.output}")


if __name__ == "__main__":
    main()
