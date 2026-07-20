"""PersistenciaCI — materializa los resultados del motor CI en tablas
SQLite `ci_*` para que el Libro Maestro BI y los dashboards las lean
con un SELECT * sin recalcular.

Tablas creadas:

- ci_competencia
- ci_comparador (histórico de comparativos)
- ci_radar
- ci_oportunidades
- ci_alertas
- ci_indices
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..models import Row
from .models import (
    Alerta,
    CambioRadar,
    ComparativoEmpresas,
    IndiceCI,
    ItemCompetencia,
    Oportunidad,
)


CI_SCHEMA = """
CREATE TABLE IF NOT EXISTS ci_competencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_focal TEXT,
    competidor TEXT,
    productores_compartidos INTEGER,
    mercados_compartidos INTEGER,
    clientes_compartidos INTEGER,
    productos_compartidos INTEGER,
    kg_compartidos REAL,
    indice_similitud REAL,
    fecha_generacion TEXT
);
CREATE TABLE IF NOT EXISTS ci_comparador (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_izquierda TEXT,
    empresa_derecha TEXT,
    kg_izquierda REAL,
    kg_derecha REAL,
    kg_compartidos REAL,
    productores_compartidos INTEGER,
    productores_solo_izquierda INTEGER,
    productores_solo_derecha INTEGER,
    mercados_compartidos INTEGER,
    mercados_solo_izquierda INTEGER,
    mercados_solo_derecha INTEGER,
    clientes_compartidos INTEGER,
    clientes_solo_izquierda INTEGER,
    clientes_solo_derecha INTEGER,
    productos_compartidos INTEGER,
    productos_solo_izquierda INTEGER,
    productos_solo_derecha INTEGER,
    indice_solapamiento REAL,
    fecha_generacion TEXT
);
CREATE TABLE IF NOT EXISTS ci_radar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_focal TEXT,
    tipo TEXT,
    dimension TEXT,
    valor TEXT,
    detalle TEXT,
    magnitud REAL,
    severidad TEXT,
    fecha_generacion TEXT
);
CREATE TABLE IF NOT EXISTS ci_oportunidades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_focal TEXT,
    tipo TEXT,
    entidad TEXT,
    motivo TEXT,
    kg_potenciales REAL,
    score REAL,
    fecha_generacion TEXT
);
CREATE TABLE IF NOT EXISTS ci_alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_focal TEXT,
    tipo TEXT,
    entidad TEXT,
    detalle TEXT,
    magnitud REAL,
    severidad TEXT,
    fecha_generacion TEXT
);
CREATE TABLE IF NOT EXISTS ci_indices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa TEXT,
    indice_diversificacion REAL,
    indice_fidelidad REAL,
    indice_competencia REAL,
    indice_riesgo REAL,
    indice_oportunidad REAL,
    indice_general REAL,
    fecha_generacion TEXT
);
"""


class PersistenciaCI:
    """Persiste los resultados del motor CI en SQLite."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        with sqlite3.connect(self.database_path) as conn:
            conn.executescript(CI_SCHEMA)

    def limpiar(self, empresa_focal: str | None = None) -> None:
        """Limpia tablas CI (opcionalmente solo para una empresa focal)."""
        with sqlite3.connect(self.database_path) as conn:
            for table in ["ci_competencia", "ci_radar", "ci_oportunidades", "ci_alertas", "ci_indices"]:
                if empresa_focal:
                    col = "empresa" if table == "ci_indices" else "empresa_focal"
                    conn.execute(f"DELETE FROM {table} WHERE {col} = ?", (empresa_focal,))
                else:
                    conn.execute(f"DELETE FROM {table}")
            # ci_comparador es multi-empresa; solo se limpia por completo
            if not empresa_focal:
                conn.execute("DELETE FROM ci_comparador")

    def guardar_competencia(self, items: list[ItemCompetencia], fecha: str) -> None:
        rows = [(i.empresa_focal, i.competidor, i.productores_compartidos, i.mercados_compartidos,
                 i.clientes_compartidos, i.productos_compartidos, i.kg_compartidos,
                 i.indice_similitud, fecha) for i in items]
        self._insert_many("ci_competencia",
                          ["empresa_focal", "competidor", "productores_compartidos",
                           "mercados_compartidos", "clientes_compartidos", "productos_compartidos",
                           "kg_compartidos", "indice_similitud", "fecha_generacion"],
                          rows)

    def guardar_comparador(self, comparativo: ComparativoEmpresas, fecha: str) -> None:
        row = (comparativo.empresa_izquierda, comparativo.empresa_derecha,
               comparativo.kg_izquierda, comparativo.kg_derecha, comparativo.kg_compartidos,
               comparativo.productores_compartidos, comparativo.productores_solo_izquierda,
               comparativo.productores_solo_derecha, comparativo.mercados_compartidos,
               comparativo.mercados_solo_izquierda, comparativo.mercados_solo_derecha,
               comparativo.clientes_compartidos, comparativo.clientes_solo_izquierda,
               comparativo.clientes_solo_derecha, comparativo.productos_compartidos,
               comparativo.productos_solo_izquierda, comparativo.productos_solo_derecha,
               comparativo.indice_solapamiento, fecha)
        self._insert_many("ci_comparador",
                          ["empresa_izquierda", "empresa_derecha", "kg_izquierda", "kg_derecha",
                           "kg_compartidos", "productores_compartidos", "productores_solo_izquierda",
                           "productores_solo_derecha", "mercados_compartidos", "mercados_solo_izquierda",
                           "mercados_solo_derecha", "clientes_compartidos", "clientes_solo_izquierda",
                           "clientes_solo_derecha", "productos_compartidos", "productos_solo_izquierda",
                           "productos_solo_derecha", "indice_solapamiento", "fecha_generacion"],
                          [row])

    def guardar_radar(self, cambios: list[CambioRadar], fecha: str) -> None:
        rows = [(c.empresa_focal, c.tipo, c.dimension, c.valor, c.detalle, c.magnitud,
                 c.severidad, fecha) for c in cambios]
        self._insert_many("ci_radar",
                          ["empresa_focal", "tipo", "dimension", "valor", "detalle",
                           "magnitud", "severidad", "fecha_generacion"],
                          rows)

    def guardar_oportunidades(self, oportunidades: list[Oportunidad], fecha: str) -> None:
        rows = [(o.empresa_focal, o.tipo, o.entidad, o.motivo, o.kg_potenciales, o.score, fecha)
                for o in oportunidades]
        self._insert_many("ci_oportunidades",
                          ["empresa_focal", "tipo", "entidad", "motivo", "kg_potenciales",
                           "score", "fecha_generacion"],
                          rows)

    def guardar_alertas(self, alertas: list[Alerta], fecha: str) -> None:
        rows = [(a.empresa_focal, a.tipo, a.entidad, a.detalle, a.magnitud, a.severidad, fecha)
                for a in alertas]
        self._insert_many("ci_alertas",
                          ["empresa_focal", "tipo", "entidad", "detalle", "magnitud",
                           "severidad", "fecha_generacion"],
                          rows)

    def guardar_indice(self, indice: IndiceCI, fecha: str) -> None:
        row = (indice.empresa, indice.indice_diversificacion, indice.indice_fidelidad,
               indice.indice_competencia, indice.indice_riesgo, indice.indice_oportunidad,
               indice.indice_general, fecha)
        self._insert_many("ci_indices",
                          ["empresa", "indice_diversificacion", "indice_fidelidad",
                           "indice_competencia", "indice_riesgo", "indice_oportunidad",
                           "indice_general", "fecha_generacion"],
                          [row])

    def leer_tabla(self, tabla: str) -> list[Row]:
        with sqlite3.connect(self.database_path) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(f"SELECT * FROM {tabla}").fetchall()]

    # ------------------- helpers internos -------------------

    def _insert_many(self, table: str, columns: list[str], rows: list[tuple]) -> None:
        if not rows:
            return
        placeholders = ",".join("?" for _ in columns)
        sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
        with sqlite3.connect(self.database_path) as conn:
            conn.executemany(sql, rows)
