"""Modelos compartidos del motor de importación FRIMARAL BI."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

Row = dict[str, Any]


@dataclass(frozen=True)
class ImportConfig:
    """Configuración declarativa para importar el archivo oficial MGAP."""

    source_path: Path
    database_path: Path = Path("output/frimaral_bi.db")
    normalized_copy_path: Path = Path("output/mgap_normalizado.csv")
    log_path: Path = Path("output/importacion_mgap_log.md")
    required_columns: tuple[str, ...] = (
        "Fecha",
        "Establecimiento Productor",
        "Establecimiento Certificador",
        "Destino",
        "Pais",
        "Producto",
        "Corte",
        "Peso",
    )


@dataclass
class ImportStats:
    """Métricas operativas de una importación."""

    source_file: str
    sheet_name: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    row_count: int = 0
    column_count: int = 0
    elapsed_seconds: float = 0.0


@dataclass(frozen=True)
class ValidationIssue:
    """Error o advertencia detectado sin detener el flujo completo."""

    level: str
    code: str
    message: str
    row_number: int | None = None
    column: str | None = None
    value: Any | None = None
