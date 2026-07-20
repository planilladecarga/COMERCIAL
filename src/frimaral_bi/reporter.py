"""Reporte operativo de importación."""
from __future__ import annotations

from pathlib import Path

from .models import ImportStats, Row, ValidationIssue


class ReporteImportacion:
    """Genera un log legible para auditoría del proceso MGAP."""

    def write(self, path: Path, stats: ImportStats, issues: list[ValidationIssue], catalogs: dict[str, list[Row]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        errors = [issue for issue in issues if issue.level == "error"]
        warnings = [issue for issue in issues if issue.level != "error"]
        lines = [
            "# Reporte de importación MGAP",
            "",
            f"- Archivo importado: `{stats.source_file}`",
            f"- Hoja detectada: `{stats.sheet_name or 'N/A'}`",
            f"- Cantidad de filas: {stats.row_count}",
            f"- Cantidad de columnas: {stats.column_count}",
            f"- Tiempo de importación: {stats.elapsed_seconds} segundos",
            f"- Errores: {len(errors)}",
            f"- Advertencias: {len(warnings)}",
            f"- Empresas nuevas detectadas: {len(catalogs.get('empresas', []))}",
            f"- Países nuevos: {len(catalogs.get('paises', []))}",
            f"- Productos nuevos: {len(catalogs.get('productos', []))}",
            "",
            "## Detalle de incidencias",
        ]
        for issue in issues:
            lines.append(f"- [{issue.level.upper()}] {issue.code}: {issue.message} fila={issue.row_number or '-'} columna={issue.column or '-'} valor={issue.value or '-'}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
