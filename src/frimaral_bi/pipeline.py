"""Orquestación del flujo XLSB → BI sin dashboards ni interfaz."""
from __future__ import annotations

import csv
from dataclasses import dataclass

from .catalogos import ConstructorCatalogos
from .database import BaseDatosBI
from .importador import ImportadorMGAP
from .models import ImportConfig, ImportStats, Row, ValidationIssue
from .normalizador import NormalizadorMGAP
from .reporter import ReporteImportacion
from .validador import ValidadorMGAP


@dataclass(frozen=True)
class PipelineResult:
    stats: ImportStats
    issues: list[ValidationIssue]
    catalogs: dict[str, list[Row]]


class MotorImportacionMGAP:
    """Ejecuta lectura, validación, normalización, catálogos, SQLite y log."""

    def __init__(self) -> None:
        self.importador = ImportadorMGAP()
        self.validador = ValidadorMGAP()
        self.normalizador = NormalizadorMGAP()
        self.catalogos = ConstructorCatalogos()
        self.reporter = ReporteImportacion()

    def run(self, config: ImportConfig) -> PipelineResult:
        raw_rows, stats, import_issues = self.importador.read(config.source_path)
        validation_issues = self.validador.validate(raw_rows, config.required_columns) if raw_rows else []
        normalized_rows = self.normalizador.normalize(raw_rows)
        catalogs = self.catalogos.build(normalized_rows)
        self._write_normalized_copy(config.normalized_copy_path, normalized_rows)
        BaseDatosBI(config.database_path).load(normalized_rows, catalogs)
        issues = [*import_issues, *validation_issues]
        self.reporter.write(config.log_path, stats, issues, catalogs)
        return PipelineResult(stats, issues, catalogs)

    def _write_normalized_copy(self, path, rows: list[Row]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        columns = list(rows[0].keys())
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
