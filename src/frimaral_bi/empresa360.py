"""Motor de Inteligencia Comercial Empresa360."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import Row
from .repositories import BIRepository


@dataclass(frozen=True)
class Empresa360Ficha:
    """Ficha integral y reusable para cualquier empresa del país."""

    informacion_general: Row
    roles: Row
    indicadores: Row
    productores_relacionados: list[Row]
    certificadores_relacionados: list[Row]
    depositos_utilizados: list[Row]
    mercados: list[Row]
    productos: list[Row]
    cortes: list[Row]
    evolucion_mensual: list[Row]
    participacion: list[Row]
    competidores: list[Row]
    clientes: list[Row]
    alertas: list[Row]
    movimientos: list[Row]


class Empresa360:
    """Construye una vista 360° desde SQLite sin datos manuales ni SQL duplicado."""

    def __init__(self, database_path: Path) -> None:
        self.repository = BIRepository(database_path)

    def construir(self, nombre_empresa: str) -> Empresa360Ficha:
        empresa = self.repository.company_by_name(nombre_empresa)
        if not empresa:
            raise ValueError(f"Empresa no encontrada en SQLite: {nombre_empresa}")
        company_id = int(empresa["id_empresa"])
        movimientos = self.repository.company_movements(company_id)
        productores = self.repository.aggregate_relation(company_id, "prod.nombre", "productor")
        certificadores = self.repository.aggregate_relation(company_id, "cert.nombre", "certificador")
        depositos = self.repository.aggregate_relation(company_id, "dest.nombre", "deposito")
        mercados = self.repository.aggregate_relation(company_id, "pais.nombre_pais", "mercado")
        productos = self.repository.aggregate_relation(company_id, "producto.nombre_producto", "producto")
        cortes = self.repository.aggregate_relation(company_id, "corte.nombre_corte", "corte")
        clientes = self._clientes(company_id)
        competidores = self._competidores(company_id)
        evolucion = self.repository.monthly_evolution(company_id)
        return Empresa360Ficha(
            informacion_general=self._informacion_general(empresa),
            roles=self._roles(empresa, movimientos, competidores, clientes),
            indicadores=self._indicadores(company_id, productores, certificadores, mercados, productos, cortes, clientes, competidores, movimientos),
            productores_relacionados=productores,
            certificadores_relacionados=certificadores,
            depositos_utilizados=depositos,
            mercados=mercados,
            productos=productos,
            cortes=cortes,
            evolucion_mensual=evolucion,
            participacion=self._participacion(depositos),
            competidores=competidores,
            clientes=clientes,
            alertas=self._alertas(empresa, evolucion, mercados, clientes),
            movimientos=movimientos,
        )

    def responder(self, nombre_empresa: str, pregunta: str) -> Row | list[Row]:
        """Responde consultas comerciales frecuentes con funciones reutilizables."""
        ficha = self.construir(nombre_empresa)
        pregunta_normalizada = pregunta.upper()
        if "SIN PASAR POR CALIRAL" in pregunta_normalizada:
            return [m for m in ficha.movimientos if m.get("certificador") != "CALIRAL" and m.get("estado_comercial") == "Exportado"]
        if "MERCADOS" in pregunta_normalizada:
            return ficha.mercados
        if "PRODUCTORES" in pregunta_normalizada:
            return ficha.productores_relacionados
        if "COMPETIDORES" in pregunta_normalizada or "COMPETENCIA" in pregunta_normalizada:
            return ficha.competidores
        if "CLIENTES" in pregunta_normalizada:
            return ficha.clientes
        return ficha.indicadores

    def _informacion_general(self, empresa: Row) -> Row:
        return {
            "id_empresa": empresa["id_empresa"],
            "nombre": empresa["nombre"],
            "tipo_principal": empresa["tipo_principal"],
            "fecha_primera_aparicion": empresa["fecha_primera_aparicion"],
            "fecha_ultima_aparicion": empresa["fecha_ultima_aparicion"],
            "cantidad_total_movimientos": empresa["cantidad_movimientos"],
            "activo": bool(empresa["activo"]),
        }

    def _roles(self, empresa: Row, movimientos: list[Row], competidores: list[Row], clientes: list[Row]) -> Row:
        return {
            "productor": bool(empresa["es_productor"]),
            "certificador": bool(empresa["es_certificador"]),
            "deposito": bool(empresa["es_deposito"]),
            "puerto": bool(empresa["es_puerto"]),
            "cliente": bool(clientes),
            "competidor": bool(competidores),
            "roles_multiples": sum(bool(empresa[field]) for field in ["es_productor", "es_certificador", "es_deposito", "es_puerto"]) > 1,
            "movimientos_detectados": len(movimientos),
        }

    def _indicadores(self, company_id: int, productores: list[Row], certificadores: list[Row], mercados: list[Row], productos: list[Row], cortes: list[Row], clientes: list[Row], competidores: list[Row], movimientos: list[Row]) -> Row:
        return {
            "kg_totales": self.repository.total_kg(company_id),
            "cantidad_movimientos": len(movimientos),
            "cantidad_productores_relacionados": len(productores),
            "cantidad_certificadores_relacionados": len(certificadores),
            "cantidad_mercados": len(mercados),
            "cantidad_productos": len(productos),
            "cantidad_cortes": len(cortes),
            "cantidad_clientes": len(clientes),
            "cantidad_competidores": len(competidores),
        }

    def _clientes(self, company_id: int) -> list[Row]:
        return self.repository.aggregate_relation(company_id, "dest.nombre", "cliente")

    def _participacion(self, depositos: list[Row]) -> list[Row]:
        total = sum(float(row.get("kg") or 0) for row in depositos)
        output: list[Row] = []
        for row in depositos:
            nombre = str(row.get("nombre") or "")
            grupo = "CALIRAL" if "CALIRAL" in nombre else "ARBIZA" if "ARBIZA" in nombre else "OTROS"
            kg = float(row.get("kg") or 0)
            output.append({"grupo": grupo, "deposito": nombre, "kg": kg, "participacion_pct": round((kg * 100 / total), 2) if total else 0})
        return output

    def _competidores(self, company_id: int) -> list[Row]:
        target_sets = self._comparison_sets(company_id)
        competitors: list[Row] = []
        for company in self.repository.all_companies():
            other_id = int(company["id_empresa"])
            if other_id == company_id:
                continue
            other_sets = self._comparison_sets(other_id)
            score = self._similarity_score(target_sets, other_sets)
            if score > 0:
                competitors.append({
                    "id_empresa": other_id,
                    "nombre": company["nombre"],
                    "indice_similitud": score,
                    "productores_compartidos": len(target_sets["productores"] & other_sets["productores"]),
                    "mercados_compartidos": len(target_sets["mercados"] & other_sets["mercados"]),
                    "clientes_compartidos": len(target_sets["clientes"] & other_sets["clientes"]),
                })
        return sorted(competitors, key=lambda row: row["indice_similitud"], reverse=True)

    def _comparison_sets(self, company_id: int) -> dict[str, set[str]]:
        return {
            "productores": self.repository.distinct_set(company_id, "prod.nombre"),
            "mercados": self.repository.distinct_set(company_id, "pais.nombre_pais"),
            "clientes": self.repository.distinct_set(company_id, "dest.nombre"),
        }

    def _similarity_score(self, left: dict[str, set[str]], right: dict[str, set[str]]) -> float:
        scores = []
        for key in ["productores", "mercados", "clientes"]:
            union = left[key] | right[key]
            scores.append((len(left[key] & right[key]) / len(union)) if union else 0)
        return round(sum(scores) / len(scores) * 100, 2)

    def _alertas(self, empresa: Row, evolucion: list[Row], mercados: list[Row], clientes: list[Row]) -> list[Row]:
        alerts: list[Row] = []
        if empresa.get("fecha_primera_aparicion") == empresa.get("fecha_ultima_aparicion"):
            alerts.append({"tipo": "Nueva empresa detectada", "severidad": "info", "detalle": empresa["nombre"]})
        if len(evolucion) >= 2:
            previous = float(evolucion[-2].get("kg") or 0)
            current = float(evolucion[-1].get("kg") or 0)
            change = ((current - previous) * 100 / previous) if previous else 0
            if change < -20:
                alerts.append({"tipo": "Caída superior al 20%", "severidad": "alta", "detalle": round(change, 2)})
            if change > 30:
                alerts.append({"tipo": "Aumento superior al 30%", "severidad": "media", "detalle": round(change, 2)})
        if mercados:
            alerts.append({"tipo": "Mercados activos detectados", "severidad": "info", "detalle": len(mercados)})
        if clientes:
            alerts.append({"tipo": "Clientes vinculados detectados", "severidad": "info", "detalle": len(clientes)})
        return alerts
