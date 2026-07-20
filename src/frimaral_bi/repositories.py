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

    # ------------------------------------------------------------------
    # Extensiones Sprint 5 — Motor de Inteligencia Competitiva (CI)
    # ------------------------------------------------------------------
    # Todas las consultas CI usan la dimensión "rol" para no duplicar SQL.
    # Un movimiento vincula una empresa por productor / certificador / destino,
    # por eso cada consulta recibe la columna de rol como parámetro.
    # ------------------------------------------------------------------

    DIMENSION_EXPRESSIONS: dict[str, str] = {
        "productor": "prod.nombre",
        "certificador": "cert.nombre",
        "deposito": "dest.nombre",
        "cliente": "dest.nombre",
        "mercado": "pais.nombre_pais",
        "producto": "producto.nombre_producto",
        "corte": "corte.nombre_corte",
    }

    def company_dimension_set(
        self,
        company_id: int,
        dimension: str,
        *,
        export_only: bool = False,
    ) -> set[str]:
        """Conjunto distintivo de valores de una dimensión para una empresa.

        Reemplaza el uso directo de `distinct_set` con expresiones SQL sueltas:
        el caller pasa un nombre de dimensión ("productor", "mercado", ...)
        y el repositorio resuelve la expresión SQL segura. Si `export_only`
        es True, filtra solo movimientos exportados (solo_deposito = 0).
        """
        expression = self._dimension_expression(dimension)
        export_clause = "AND m.solo_deposito = 0" if export_only else ""
        sql = f"""
            SELECT DISTINCT {expression} AS value
            {self.DIMENSION_JOINS}
            WHERE (m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?)
            {export_clause}
        """
        return {
            str(row["value"]).upper()
            for row in self.fetch_all(sql, (company_id, company_id, company_id))
            if row.get("value")
        }

    def companies_by_dimension(
        self,
        dimension: str,
        dimension_value: str,
    ) -> list[Row]:
        """Empresas que participan en movimientos con un valor de dimensión dado.

        Útil para responder "¿qué certificadores trabajan con productores que
        también usan CALIRAL?" sin duplicar la lógica del comparador.
        """
        expression = self._dimension_expression(dimension)
        sql = f"""
            SELECT DISTINCT emp.id_empresa, emp.nombre, emp.nombre_normalizado,
                   emp.es_productor, emp.es_certificador, emp.es_deposito, emp.es_puerto
            FROM movimientos m
            {self.DIMENSION_JOINS}
            LEFT JOIN empresas emp ON emp.id_empresa = m.id_productor
                                  OR emp.id_empresa = m.id_certificador
                                  OR emp.id_empresa = m.id_destino
            WHERE {expression} = ?
            ORDER BY emp.nombre
        """
        return self.fetch_all(sql, (dimension_value,))

    def kg_between_companies(
        self,
        left_id: int,
        right_id: int,
        *,
        role_left: str = "any",
        role_right: str = "any",
    ) -> float:
        """Kilos compartidos entre dos empresas en roles específicos.

        Por defecto cuenta cualquier movimiento donde ambas empresas participen
        (en cualquier rol). Si se pasa `role_left`/`role_right` se restringe:
        por ejemplo, role_left="certificador" + role_right="productor"
        responde "kg exportados por productores vía CALIRAL como certificador".
        """
        # Si ambos roles son "any", intersección por cualquier combinación.
        if role_left == "any" and role_right == "any":
            sql = """
                SELECT COALESCE(SUM(m.peso), 0) AS kg
                FROM movimientos m
                WHERE (m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?)
                  AND (m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?)
            """
            return float(self.fetch_one(sql, (left_id, left_id, left_id, right_id, right_id, right_id))["kg"] or 0)
        left_col = self._role_column(role_left)
        right_col = self._role_column(role_right)
        sql = f"SELECT COALESCE(SUM(m.peso), 0) AS kg FROM movimientos m WHERE {left_col} = ? AND {right_col} = ?"
        return float(self.fetch_one(sql, (left_id, right_id))["kg"] or 0)

    def shared_movements(
        self,
        left_id: int,
        right_id: int,
        *,
        role_left: str = "any",
        role_right: str = "any",
    ) -> list[Row]:
        """Lista de movimientos compartidos entre dos empresas."""
        if role_left == "any" and role_right == "any":
            sql = f"""
                SELECT m.id_movimiento, m.fecha, m.peso, m.solo_deposito,
                       prod.nombre AS productor, cert.nombre AS certificador,
                       dest.nombre AS deposito, pais.nombre_pais AS mercado,
                       producto.nombre_producto AS producto
                {self.DIMENSION_JOINS}
                WHERE (m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?)
                  AND (m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?)
                ORDER BY m.fecha DESC, m.id_movimiento DESC
            """
            return self.fetch_all(sql, (left_id, left_id, left_id, right_id, right_id, right_id))
        left_col = self._role_column(role_left)
        right_col = self._role_column(role_right)
        sql = f"""
            SELECT m.id_movimiento, m.fecha, m.peso, m.solo_deposito,
                   prod.nombre AS productor, cert.nombre AS certificador,
                   dest.nombre AS deposito, pais.nombre_pais AS mercado,
                   producto.nombre_producto AS producto
            {self.DIMENSION_JOINS}
            WHERE {left_col} = ? AND {right_col} = ?
            ORDER BY m.fecha DESC, m.id_movimiento DESC
        """
        return self.fetch_all(sql, (left_id, right_id))

    def monthly_kg_by_company(self, company_id: int) -> list[Row]:
        """Serie mensual de kg para una empresa (cualquier rol)."""
        sql = """
            SELECT SUBSTR(m.fecha, 1, 7) AS periodo,
                   COALESCE(SUM(m.peso), 0) AS kg,
                   COUNT(*) AS movimientos
            FROM movimientos m
            WHERE m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?
            GROUP BY SUBSTR(m.fecha, 1, 7)
            ORDER BY periodo
        """
        return self.fetch_all(sql, (company_id, company_id, company_id))

    def monthly_kg_by_dimension(
        self,
        dimension: str,
        dimension_value: str,
    ) -> list[Row]:
        """Serie mensual de kg para un valor de dimensión (productor, mercado...)."""
        expression = self._dimension_expression(dimension)
        sql = f"""
            SELECT SUBSTR(m.fecha, 1, 7) AS periodo,
                   COALESCE(SUM(m.peso), 0) AS kg,
                   COUNT(*) AS movimientos
            {self.DIMENSION_JOINS}
            WHERE {expression} = ?
            GROUP BY SUBSTR(m.fecha, 1, 7)
            ORDER BY periodo
        """
        return self.fetch_all(sql, (dimension_value,))

    def company_period_kg(
        self,
        company_id: int,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> float:
        """Kg totales de una empresa en un intervalo opcional [start, end)."""
        clauses = ["(m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?)"]
        params: list[object] = [company_id, company_id, company_id]
        if start_date:
            clauses.append("m.fecha >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("m.fecha < ?")
            params.append(end_date)
        sql = f"SELECT COALESCE(SUM(m.peso), 0) AS kg FROM movimientos m WHERE {' AND '.join(clauses)}"
        return float(self.fetch_one(sql, tuple(params))["kg"] or 0)

    def companies_by_role(self, role_flag: str) -> list[Row]:
        """Lista empresas que tienen un flag de rol activo.

        `role_flag` debe ser uno de: es_productor, es_certificador,
        es_deposito, es_puerto, es_competidor.
        """
        valid = {"es_productor", "es_certificador", "es_deposito", "es_puerto", "es_competidor"}
        if role_flag not in valid:
            raise ValueError(f"Flag de rol inválido: {role_flag}. Válidos: {sorted(valid)}")
        return self.fetch_all(
            f"SELECT * FROM empresas WHERE {role_flag} = 1 AND activo = 1 ORDER BY nombre"
        )

    def first_and_last_date(self, company_id: int) -> tuple[str | None, str | None]:
        """Primera y última fecha de actividad de una empresa."""
        row = self.fetch_one(
            """
            SELECT MIN(m.fecha) AS first_date, MAX(m.fecha) AS last_date
            FROM movimientos m
            WHERE m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?
            """,
            (company_id, company_id, company_id),
        )
        if not row:
            return None, None
        return row.get("first_date"), row.get("last_date")

    def _dimension_expression(self, dimension: str) -> str:
        try:
            return self.DIMENSION_EXPRESSIONS[dimension]
        except KeyError as exc:
            raise ValueError(
                f"Dimensión no soportada: {dimension}. "
                f"Válidas: {sorted(self.DIMENSION_EXPRESSIONS)}"
            ) from exc

    def _role_column(self, role: str) -> str:
        try:
            return self.ROLE_COLUMNS[role]
        except KeyError as exc:
            raise ValueError(
                f"Rol no soportado: {role}. Válidos: {sorted(self.ROLE_COLUMNS)}"
            ) from exc

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def normalize_name(name: str) -> str:
        return " ".join(name.strip().upper().split())
