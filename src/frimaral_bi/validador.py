"""Validaciones de calidad que acumulan errores sin interrumpir la importación."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .models import Row, ValidationIssue


class ValidadorMGAP:
    """Valida estructura, tipos, fechas, pesos y duplicados."""

    def validate(self, rows: list[Row], required_columns: Iterable[str]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        columns = set(rows[0].keys()) if rows else set()
        for column in required_columns:
            if column not in columns:
                issues.append(ValidationIssue("error", "MISSING_COLUMN", "Falta columna obligatoria.", column=column))
        seen: set[tuple[object, ...]] = set()
        for index, row in enumerate(rows, start=2):
            issues.extend(self._validate_row(row, index, required_columns))
            fingerprint = tuple(row.get(column) for column in sorted(columns))
            if fingerprint in seen:
                issues.append(ValidationIssue("warning", "DUPLICATE_ROW", "Fila duplicada detectada.", row_number=index))
            seen.add(fingerprint)
        return issues

    def _validate_row(self, row: Row, index: int, required_columns: Iterable[str]) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        for column in required_columns:
            if row.get(column) in (None, ""):
                issues.append(ValidationIssue("warning", "NULL_VALUE", "Valor nulo en columna obligatoria.", index, column))
        self._validate_date(row.get("Fecha"), index, issues)
        self._validate_weight(row.get("Peso"), index, issues)
        return issues

    def _validate_date(self, value: object, index: int, issues: list[ValidationIssue]) -> None:
        if value in (None, ""):
            return
        if isinstance(value, datetime):
            return
        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                datetime.strptime(text[:10], fmt)
                return
            except ValueError:
                continue
        issues.append(ValidationIssue("error", "INVALID_DATE", "Fecha inválida.", index, "Fecha", value))

    def _validate_weight(self, value: object, index: int, issues: list[ValidationIssue]) -> None:
        if value in (None, ""):
            return
        try:
            number = float(str(value).replace(".", "").replace(",", "."))
        except ValueError:
            issues.append(ValidationIssue("error", "INVALID_WEIGHT", "Peso no numérico.", index, "Peso", value))
            return
        if number < 0:
            issues.append(ValidationIssue("error", "NEGATIVE_WEIGHT", "Peso negativo.", index, "Peso", value))
