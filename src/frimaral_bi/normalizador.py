"""Normalización de datos MGAP sin alterar el archivo fuente."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .models import Row

INVISIBLE = re.compile(r"[\u200B-\u200D\uFEFF]")
DOUBLE_SPACES = re.compile(r"\s+")
# Patrón flexible: detecta "(sólo a depósitos)", "(solo a deposito)",
# "(solo a depositos)" y variantes sin paréntesis.
SOLO_DEPOSITO_RE = re.compile(
    r"\(?s[óo]lo\s+a\s+dep[óo]sito(s)?\)?",
    re.IGNORECASE,
)


class NormalizadorMGAP:
    """Aplica reglas de limpieza y prepara campos BI extensibles."""

    def normalize(self, rows: list[Row]) -> list[Row]:
        return [self._normalize_row(row) for row in rows]

    def _normalize_row(self, row: Row) -> Row:
        normalized = {self._clean_text(key): self._normalize_value(value) for key, value in row.items()}
        pais = str(normalized.get("Pais", "") or "")
        normalized["solo_deposito"] = bool(SOLO_DEPOSITO_RE.search(pais))
        normalized["Pais"] = self._clean_text(SOLO_DEPOSITO_RE.sub("", pais).upper())
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
        text = str(value).replace(".", "").replace(",", ".")
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
        # Serial de Excel (ej. 45665 = 2025-01-01). El epoch de Excel es
        # 1899-12-30 (para compensar el bug de año bisiesto de 1900).
        if isinstance(value, (int, float)):
            try:
                serial = float(value)
                if 1 < serial < 100_000:  # rango razonable para fechas Excel
                    from datetime import timedelta
                    base = datetime(1899, 12, 30)
                    d = base + timedelta(days=serial)
                    return d.date().isoformat()
            except (ValueError, OverflowError):
                pass
        text = str(value).strip()
        # Si el texto es numérico, también intentar como serial
        if text.replace(".", "").isdigit():
            try:
                serial = float(text)
                if 1 < serial < 100_000:
                    from datetime import timedelta
                    base = datetime(1899, 12, 30)
                    d = base + timedelta(days=serial)
                    return d.date().isoformat()
            except (ValueError, OverflowError):
                pass
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(text[:10], fmt).date().isoformat()
            except ValueError:
                continue
        return text
