"""Normalización de datos MGAP sin alterar el archivo fuente."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .models import Row

INVISIBLE = re.compile(r"[\u200B-\u200D\uFEFF]")
DOUBLE_SPACES = re.compile(r"\s+")
SOLO_DEPOSITO = "(SOLO A DEPÓSITOS)"


class NormalizadorMGAP:
    """Aplica reglas de limpieza y prepara campos BI extensibles."""

    def normalize(self, rows: list[Row]) -> list[Row]:
        return [self._normalize_row(row) for row in rows]

    def _normalize_row(self, row: Row) -> Row:
        normalized = {self._clean_text(key): self._normalize_value(value) for key, value in row.items()}
        pais = str(normalized.get("Pais", "") or "")
        normalized["solo_deposito"] = SOLO_DEPOSITO in pais.upper()
        normalized["Pais"] = self._clean_text(pais.upper().replace(SOLO_DEPOSITO, ""))
        normalized["Peso"] = self._to_float(normalized.get("Peso"))
        normalized["Fecha"] = self._to_iso_date(normalized.get("Fecha"))
        return normalized

    def _normalize_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._clean_text(value).upper()
        return value

    def _clean_text(self, value: str) -> str:
        return DOUBLE_SPACES.sub(" ", INVISIBLE.sub("", value)).strip()

    def _to_float(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _to_iso_date(self, value: Any) -> str | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(text[:10], fmt).date().isoformat()
            except ValueError:
                continue
        return text
