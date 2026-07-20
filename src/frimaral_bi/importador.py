"""Lectura no destructiva del archivo MGAP."""
from __future__ import annotations

import csv
import importlib
import importlib.util
import time
from pathlib import Path
from typing import Any

from .models import ImportStats, Row, ValidationIssue


class ImportadorMGAP:
    """Importa XLSB del MGAP sin modificar nunca el archivo original."""

    def read(self, source_path: Path) -> tuple[list[Row], ImportStats, list[ValidationIssue]]:
        started = time.perf_counter()
        stats = ImportStats(source_file=str(source_path))
        issues: list[ValidationIssue] = []
        if not source_path.exists():
            issues.append(ValidationIssue("error", "FILE_NOT_FOUND", "No existe el archivo de origen."))
            stats.finished_at = stats.started_at
            return [], stats, issues

        suffix = source_path.suffix.lower()
        if suffix == ".xlsb":
            rows, sheet_name, read_issues = self._read_xlsb(source_path)
            stats.sheet_name = sheet_name
            issues.extend(read_issues)
        elif suffix == ".csv":
            rows = self._read_csv(source_path)
            stats.sheet_name = source_path.name
        else:
            rows = []
            issues.append(ValidationIssue("error", "UNSUPPORTED_FORMAT", f"Formato no soportado: {suffix}"))

        stats.row_count = len(rows)
        stats.column_count = len(rows[0]) if rows else 0
        stats.elapsed_seconds = round(time.perf_counter() - started, 4)
        return rows, stats, issues

    def _read_csv(self, source_path: Path) -> list[Row]:
        with source_path.open("r", encoding="utf-8-sig", newline="") as file:
            return [dict(row) for row in csv.DictReader(file)]

    def _read_xlsb(self, source_path: Path) -> tuple[list[Row], str | None, list[ValidationIssue]]:
        if importlib.util.find_spec("pandas") is None:
            return [], None, [ValidationIssue("error", "MISSING_PANDAS", "Para leer XLSB instale pandas y pyxlsb.")]
        pandas = importlib.import_module("pandas")
        book = pandas.ExcelFile(source_path, engine="pyxlsb")
        best_sheet = self._detect_sheet(book)
        frame = pandas.read_excel(source_path, sheet_name=best_sheet, engine="pyxlsb")
        frame = frame.dropna(how="all")
        rows = frame.where(frame.notna(), None).to_dict(orient="records")
        return rows, str(best_sheet), []

    def _detect_sheet(self, book: Any) -> str:
        """Selecciona la primera hoja con filas y columnas detectables."""
        pandas = importlib.import_module("pandas")
        for sheet in book.sheet_names:
            preview = pandas.read_excel(book, sheet_name=sheet, engine="pyxlsb", nrows=20)
            if not preview.empty and len(preview.columns) > 1:
                return str(sheet)
        return str(book.sheet_names[0])
