"""Persistencia SQLite en modelo estrella para FRIMARAL BI."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .models import Row


class BaseDatosBI:
    """Crea y carga una base SQLite limpia para Business Intelligence."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path) as conn:
            conn.executescript(SCHEMA)

    def load(self, rows: list[Row], catalogs: dict[str, list[Row]]) -> None:
        self.initialize()
        with sqlite3.connect(self.database_path) as conn:
            self._clear_existing_data(conn)
            self._insert_many(conn, "empresas", catalogs["empresas"])
            self._insert_many(conn, "paises", catalogs["paises"])
            self._insert_many(conn, "productos", catalogs["productos"])
            self._insert_many(conn, "cortes", catalogs["cortes"])
            self._insert_many(conn, "calendario", catalogs["calendario"])
            movimientos = [self._movement(row, catalogs) for row in rows]
            self._insert_many(conn, "movimientos", movimientos)

    def _clear_existing_data(self, conn: sqlite3.Connection) -> None:
        for table in ["movimientos", "calendario", "cortes", "productos", "paises", "empresas"]:
            conn.execute(f"DELETE FROM {table}")

    def _insert_many(self, conn: sqlite3.Connection, table: str, rows: list[Row]) -> None:
        if not rows:
            return
        columns = list(rows[0].keys())
        placeholders = ",".join("?" for _ in columns)
        sql = f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({placeholders})"
        conn.executemany(sql, [[row.get(column) for column in columns] for row in rows])

    def _movement(self, row: Row, catalogs: dict[str, list[Row]]) -> Row:
        return {
            "fecha": row.get("Fecha"),
            "id_productor": self._lookup(catalogs["empresas"], "nombre_normalizado", row.get("Establecimiento Productor"), "id_empresa"),
            "id_certificador": self._lookup(catalogs["empresas"], "nombre_normalizado", row.get("Establecimiento Certificador"), "id_empresa"),
            "id_destino": self._lookup(catalogs["empresas"], "nombre_normalizado", row.get("Destino"), "id_empresa"),
            "id_pais": self._lookup(catalogs["paises"], "nombre_pais", row.get("Pais"), "id_pais"),
            "id_producto": self._lookup(catalogs["productos"], "nombre_producto", row.get("Producto"), "id_producto"),
            "id_corte": self._lookup(catalogs["cortes"], "nombre_corte", row.get("Corte"), "id_corte"),
            "peso": row.get("Peso"),
            "solo_deposito": int(bool(row.get("solo_deposito"))),
        }

    def _lookup(self, rows: Iterable[Row], field: str, value: object, id_field: str) -> object | None:
        expected = str(value or "").strip().upper()
        for row in rows:
            if str(row.get(field) or "").strip().upper() == expected:
                return row.get(id_field)
        return None


SCHEMA = """
CREATE TABLE IF NOT EXISTS empresas (
    id_empresa INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    nombre_normalizado TEXT NOT NULL UNIQUE,
    tipo_principal TEXT,
    es_productor INTEGER NOT NULL,
    es_certificador INTEGER NOT NULL,
    es_deposito INTEGER NOT NULL,
    es_puerto INTEGER NOT NULL,
    es_competidor INTEGER NOT NULL,
    activo INTEGER NOT NULL,
    fecha_primera_aparicion TEXT,
    fecha_ultima_aparicion TEXT,
    cantidad_movimientos INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS paises (
    id_pais INTEGER PRIMARY KEY,
    nombre_pais TEXT NOT NULL UNIQUE,
    solo_deposito INTEGER NOT NULL,
    region TEXT,
    continente TEXT
);
CREATE TABLE IF NOT EXISTS productos (
    id_producto INTEGER PRIMARY KEY,
    nombre_producto TEXT NOT NULL UNIQUE,
    activo INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cortes (
    id_corte INTEGER PRIMARY KEY,
    nombre_corte TEXT NOT NULL UNIQUE,
    activo INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS calendario (
    fecha TEXT PRIMARY KEY,
    anio INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    semana INTEGER NOT NULL,
    trimestre INTEGER NOT NULL,
    nombre_mes TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS movimientos (
    id_movimiento INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT,
    id_productor INTEGER,
    id_certificador INTEGER,
    id_destino INTEGER,
    id_pais INTEGER,
    id_producto INTEGER,
    id_corte INTEGER,
    peso REAL,
    solo_deposito INTEGER NOT NULL,
    FOREIGN KEY(fecha) REFERENCES calendario(fecha),
    FOREIGN KEY(id_productor) REFERENCES empresas(id_empresa),
    FOREIGN KEY(id_certificador) REFERENCES empresas(id_empresa),
    FOREIGN KEY(id_destino) REFERENCES empresas(id_empresa),
    FOREIGN KEY(id_pais) REFERENCES paises(id_pais),
    FOREIGN KEY(id_producto) REFERENCES productos(id_producto),
    FOREIGN KEY(id_corte) REFERENCES cortes(id_corte)
);
"""
