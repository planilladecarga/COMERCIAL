"""Repositorios reutilizables sobre el modelo estrella SQLite."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .models import Row


class BIRepository:
    """Repositorio de lectura optimizado para consultas comerciales genéricas."""

    ROLE_COLUMNS = {
        "productor": "m.id_productor",
        "certificador": "m.id_certificador",
        "deposito": "m.id_destino",
        "cliente": "m.id_destino",
    }

    DIMENSION_JOINS = """
        FROM movimientos m
        LEFT JOIN empresas prod ON prod.id_empresa = m.id_productor
        LEFT JOIN empresas cert ON cert.id_empresa = m.id_certificador
        LEFT JOIN empresas dest ON dest.id_empresa = m.id_destino
        LEFT JOIN paises pais ON pais.id_pais = m.id_pais
        LEFT JOIN productos producto ON producto.id_producto = m.id_producto
        LEFT JOIN cortes corte ON corte.id_corte = m.id_corte
    """

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def fetch_one(self, sql: str, params: tuple[object, ...] = ()) -> Row | None:
        with self._connect() as conn:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None

    def fetch_all(self, sql: str, params: tuple[object, ...] = ()) -> list[Row]:
        with self._connect() as conn:
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def company_by_name(self, name: str) -> Row | None:
        normalized = self.normalize_name(name)
        return self.fetch_one("SELECT * FROM empresas WHERE nombre_normalizado = ? OR UPPER(nombre) = ?", (normalized, normalized))

    def company_movements(self, company_id: int) -> list[Row]:
        sql = f"""
            SELECT m.id_movimiento, m.fecha, prod.nombre AS productor, cert.nombre AS certificador,
                   dest.nombre AS deposito, pais.nombre_pais AS mercado, producto.nombre_producto AS producto,
                   corte.nombre_corte AS corte, m.peso, m.solo_deposito,
                   CASE WHEN m.solo_deposito = 0 THEN 'Exportado' ELSE 'No Exportado' END AS estado_comercial
            {self.DIMENSION_JOINS}
            WHERE m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?
            ORDER BY m.fecha DESC, m.id_movimiento DESC
        """
        return self.fetch_all(sql, (company_id, company_id, company_id))

    def aggregate_relation(self, company_id: int, dimension_sql: str, dimension_alias: str) -> list[Row]:
        sql = f"""
            WITH base AS (
                SELECT m.*, {dimension_sql} AS dimension_nombre
                {self.DIMENSION_JOINS}
                WHERE m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?
            ), totals AS (SELECT COALESCE(SUM(peso), 0) AS total_kg FROM base)
            SELECT dimension_nombre AS nombre, COALESCE(SUM(peso), 0) AS kg,
                   CASE WHEN totals.total_kg = 0 THEN 0 ELSE ROUND(SUM(peso) * 100.0 / totals.total_kg, 2) END AS participacion_pct,
                   COUNT(*) AS cantidad_movimientos, MIN(fecha) AS primera_fecha, MAX(fecha) AS ultima_fecha,
                   '{dimension_alias}' AS dimension
            FROM base, totals
            WHERE dimension_nombre IS NOT NULL
            GROUP BY dimension_nombre, totals.total_kg
            ORDER BY kg DESC, cantidad_movimientos DESC
        """
        return self.fetch_all(sql, (company_id, company_id, company_id))

    def monthly_evolution(self, company_id: int) -> list[Row]:
        sql = f"""
            SELECT SUBSTR(m.fecha, 1, 7) AS periodo, COALESCE(SUM(m.peso), 0) AS kg,
                   COUNT(*) AS cantidad_movimientos
            {self.DIMENSION_JOINS}
            WHERE m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?
            GROUP BY SUBSTR(m.fecha, 1, 7)
            ORDER BY periodo
        """
        return self.fetch_all(sql, (company_id, company_id, company_id))

    def distinct_set(self, company_id: int, expression: str) -> set[str]:
        sql = f"""
            SELECT DISTINCT {expression} AS value
            {self.DIMENSION_JOINS}
            WHERE m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?
        """
        return {str(row["value"]).upper() for row in self.fetch_all(sql, (company_id, company_id, company_id)) if row.get("value")}

    def all_companies(self) -> list[Row]:
        return self.fetch_all("SELECT * FROM empresas WHERE activo = 1 ORDER BY nombre")

    def total_kg(self, company_id: int) -> float:
        row = self.fetch_one(
            "SELECT COALESCE(SUM(peso), 0) AS kg FROM movimientos WHERE id_productor = ? OR id_certificador = ? OR id_destino = ?",
            (company_id, company_id, company_id),
        )
        return float(row["kg"] if row else 0)

    def count_distinct(self, company_id: int, column: str) -> int:
        if column not in self.ROLE_COLUMNS.values() and not column.startswith("m."):
            raise ValueError(f"Columna no permitida para conteo distintivo: {column}")
        row = self.fetch_one(
            f"SELECT COUNT(DISTINCT {column}) AS total FROM movimientos m WHERE m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?",
            (company_id, company_id, company_id),
        )
        return int(row["total"] if row else 0)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def normalize_name(name: str) -> str:
        return " ".join(name.strip().upper().split())
