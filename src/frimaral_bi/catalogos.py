"""Construcción de dimensiones maestras para el modelo BI."""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .models import Row


def key(value: object) -> str:
    return str(value or "").strip().upper()


class ConstructorCatalogos:
    """Genera dimensiones de empresas, países, productos, cortes y calendario."""

    def build(self, rows: list[Row]) -> dict[str, list[Row]]:
        return {
            "empresas": self.empresas(rows),
            "paises": self.paises(rows),
            "productos": self.productos(rows),
            "cortes": self.cortes(rows),
            "calendario": self.calendario(rows),
        }

    def empresas(self, rows: list[Row]) -> list[Row]:
        roles = {
            "Establecimiento Productor": "es_productor",
            "Establecimiento Certificador": "es_certificador",
            "Destino": "es_deposito",
        }
        catalog: dict[str, Row] = {}
        for row in rows:
            fecha = row.get("Fecha")
            for column, flag in roles.items():
                name = key(row.get(column))
                if not name:
                    continue
                item = catalog.setdefault(name, self._empresa_base(len(catalog) + 1, name, flag, fecha))
                item[flag] = True
                item["cantidad_movimientos"] += 1
                self._update_dates(item, fecha)
        return list(catalog.values())

    def paises(self, rows: list[Row]) -> list[Row]:
        catalog: dict[str, Row] = {}
        for row in rows:
            name = key(row.get("Pais"))
            if name and name not in catalog:
                catalog[name] = {"id_pais": len(catalog) + 1, "nombre_pais": name, "solo_deposito": bool(row.get("solo_deposito")), "region": "PENDIENTE", "continente": "PENDIENTE"}
        return list(catalog.values())

    def productos(self, rows: list[Row]) -> list[Row]:
        return self._simple_dimension(rows, "Producto", "id_producto", "nombre_producto")

    def cortes(self, rows: list[Row]) -> list[Row]:
        return self._simple_dimension(rows, "Corte", "id_corte", "nombre_corte")

    def calendario(self, rows: list[Row]) -> list[Row]:
        dates = sorted({str(row.get("Fecha")) for row in rows if row.get("Fecha")})
        output: list[Row] = []
        for value in dates:
            try:
                parsed = datetime.strptime(value[:10], "%Y-%m-%d").date()
            except ValueError:
                continue
            output.append({"fecha": parsed.isoformat(), "anio": parsed.year, "mes": parsed.month, "semana": parsed.isocalendar().week, "trimestre": (parsed.month - 1) // 3 + 1, "nombre_mes": parsed.strftime("%B")})
        return output

    def _simple_dimension(self, rows: Iterable[Row], source: str, id_name: str, name_field: str) -> list[Row]:
        catalog: dict[str, Row] = {}
        for row in rows:
            name = key(row.get(source))
            if name and name not in catalog:
                catalog[name] = {id_name: len(catalog) + 1, name_field: name, "activo": True}
        return list(catalog.values())

    def _empresa_base(self, index: int, name: str, flag: str, fecha: object) -> Row:
        return {"id_empresa": index, "nombre": name, "nombre_normalizado": name, "tipo_principal": flag.removeprefix("es_"), "es_productor": False, "es_certificador": False, "es_deposito": False, "es_puerto": False, "es_competidor": False, "activo": True, "fecha_primera_aparicion": fecha, "fecha_ultima_aparicion": fecha, "cantidad_movimientos": 0}

    def _update_dates(self, item: Row, fecha: object) -> None:
        if not fecha:
            return
        current_first = item.get("fecha_primera_aparicion") or fecha
        current_last = item.get("fecha_ultima_aparicion") or fecha
        item["fecha_primera_aparicion"] = min(str(current_first), str(fecha))
        item["fecha_ultima_aparicion"] = max(str(current_last), str(fecha))
