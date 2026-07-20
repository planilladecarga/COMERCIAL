"""OportunidadesService — construye un ranking de oportunidades comerciales
detectadas automáticamente para la empresa focal.

Tipos de oportunidad detectados:

- NUNCA_USARON_FOCAL: productores que nunca usaron la empresa focal
  pero sí algún competidor.
- MULTI_DEPOSITO: productores que usan más de un depósito.
- USA_COMPETIDOR: productores que usan un competidor específico.
- MERCADO_SIN_FOCAL: productores que exportan a mercados donde la
  empresa focal no participa.
- CRECIMIENTO_FUERTE: productores con crecimiento superior al umbral.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from ..config import UmbralesCI
from ..repositories import BIRepository
from .models import Oportunidad


class OportunidadesService:
    """Construye el ranking de oportunidades de captación/comercial."""

    def __init__(
        self,
        database_path: Path,
        umbrales: UmbralesCI | None = None,
    ) -> None:
        self.repository = BIRepository(database_path)
        self.umbrales = umbrales or UmbralesCI()

    def ranking(self, empresa_focal: str, limite: int = 50) -> list[Oportunidad]:
        """Devuelve el ranking completo ordenado por score descendente."""
        oportunidades: list[Oportunidad] = []
        oportunidades.extend(self.productores_nunca_usaron_focal(empresa_focal))
        oportunidades.extend(self.productores_multi_deposito(empresa_focal))
        oportunidades.extend(self.productores_usa_competidor(empresa_focal))
        oportunidades.extend(self.productores_mercado_sin_focal(empresa_focal))
        oportunidades.extend(self.productores_crecimiento_fuerte(empresa_focal))
        # Deduplicar por (tipo, entidad) conservando el de mayor score
        unique: dict[tuple[str, str], Oportunidad] = {}
        for op in oportunidades:
            key = (op.tipo, op.entidad)
            if key not in unique or op.score > unique[key].score:
                unique[key] = op
        return sorted(unique.values(), key=lambda o: o.score, reverse=True)[:limite]

    def productores_nunca_usaron_focal(self, empresa_focal: str) -> list[Oportunidad]:
        """Productores que nunca usaron la empresa focal pero sí algún competidor."""
        focal_id = self._require_company(empresa_focal)
        focal_productores = self.repository.company_dimension_set(focal_id, "productor")
        todos_productores = self._todos_los_productores()
        oportunidades: list[Oportunidad] = []
        for productor in todos_productores:
            if productor in focal_productores:
                continue
            kg_potenciales = self._kg_productor_total(productor)
            if kg_potenciales < self.umbrales.min_kg_oportunidad:
                continue
            score = min(100.0, kg_potenciales / 100.0)
            oportunidades.append(Oportunidad(
                tipo="NUNCA_USARON_FOCAL",
                entidad=productor,
                empresa_focal=empresa_focal,
                motivo="Productor con volumen relevante que nunca utilizó la empresa focal",
                kg_potenciales=round(kg_potenciales, 2),
                score=round(score, 2),
            ))
        return oportunidades

    def productores_multi_deposito(self, empresa_focal: str) -> list[Oportunidad]:
        """Productores que utilizan más de un depósito (oportunidad de captación)."""
        focal_id = self._require_company(empresa_focal)
        todos_productores = self._todos_los_productores()
        oportunidades: list[Oportunidad] = []
        for productor in todos_productores:
            depositos = self._depositos_por_productor(productor)
            if len(depositos) < 2:
                continue
            kg_potenciales = self._kg_productor_total(productor)
            usa_focal = any(d in self.repository.company_dimension_set(focal_id, "deposito") for d in depositos)
            score = min(100.0, kg_potenciales / 100.0 + len(depositos) * 5)
            oportunidades.append(Oportunidad(
                tipo="MULTI_DEPOSITO",
                entidad=productor,
                empresa_focal=empresa_focal,
                motivo=f"Productor con {len(depositos)} depósitos"
                       + (", ya usa la empresa focal" if usa_focal else ", no usa la empresa focal"),
                kg_potenciales=round(kg_potenciales, 2),
                score=round(score, 2),
            ))
        return oportunidades

    def productores_usa_competidor(
        self,
        empresa_focal: str,
        competidor: str | None = None,
    ) -> list[Oportunidad]:
        """Productores que usan un competidor (específico o cualquiera)."""
        focal_id = self._require_company(empresa_focal)
        focal_productores = self.repository.company_dimension_set(focal_id, "productor")
        if competidor:
            competitors_ids = [self._require_company(competidor)]
        else:
            competitors_ids = [
                int(c["id_empresa"])
                for c in self.repository.companies_by_role("es_certificador")
                if int(c["id_empresa"]) != focal_id
            ]
        oportunidades: list[Oportunidad] = []
        for cid in competitors_ids:
            competitor_name = self._company_name(cid)
            for productor in self.repository.company_dimension_set(cid, "productor"):
                if productor in focal_productores:
                    continue
                kg_potenciales = self._kg_productor_total(productor)
                score = min(100.0, kg_potenciales / 100.0 + 10)
                oportunidades.append(Oportunidad(
                    tipo="USA_COMPETIDOR",
                    entidad=productor,
                    empresa_focal=empresa_focal,
                    motivo=f"Utiliza {competitor_name}",
                    kg_potenciales=round(kg_potenciales, 2),
                    score=round(score, 2),
                ))
        return oportunidades

    def productores_mercado_sin_focal(self, empresa_focal: str) -> list[Oportunidad]:
        """Productores que exportan a mercados donde la empresa focal no participa."""
        focal_id = self._require_company(empresa_focal)
        focal_mercados = self.repository.company_dimension_set(focal_id, "mercado", export_only=True)
        todos_productores = self._todos_los_productores()
        oportunidades: list[Oportunidad] = []
        for productor in todos_productores:
            mercados_productor = self._mercados_por_productor(productor, export_only=True)
            mercados_no_focal = mercados_productor - focal_mercados
            if not mercados_no_focal:
                continue
            kg_potenciales = self._kg_productor_total(productor)
            score = min(100.0, kg_potenciales / 100.0 + len(mercados_no_focal) * 5)
            oportunidades.append(Oportunidad(
                tipo="MERCADO_SIN_FOCAL",
                entidad=productor,
                empresa_focal=empresa_focal,
                motivo=f"Exporta a mercados sin la empresa focal: {', '.join(sorted(mercados_no_focal))}",
                kg_potenciales=round(kg_potenciales, 2),
                score=round(score, 2),
            ))
        return oportunidades

    def productores_crecimiento_fuerte(self, empresa_focal: str) -> list[Oportunidad]:
        """Productores (clientes potenciales) con fuerte crecimiento en el último período."""
        today = datetime.now().date()
        current_start = (today - timedelta(days=self.umbrales.dias_periodo_actual)).isoformat()
        previous_start = (today - timedelta(
            days=self.umbrales.dias_periodo_actual + self.umbrales.dias_periodo_previo
        )).isoformat()
        previous_end = current_start
        oportunidades: list[Oportunidad] = []
        for productor in self._todos_los_productores():
            kg_curr = self._kg_productor_in_period(productor, current_start, today.isoformat())
            kg_prev = self._kg_productor_in_period(productor, previous_start, previous_end)
            if kg_prev <= 0:
                continue
            cambio_pct = (kg_curr - kg_prev) * 100 / kg_prev
            if cambio_pct < self.umbrales.crecimiento_fuerte_pct:
                continue
            score = min(100.0, cambio_pct)
            oportunidades.append(Oportunidad(
                tipo="CRECIMIENTO_FUERTE",
                entidad=productor,
                empresa_focal=empresa_focal,
                motivo=f"Crecimiento de {round(cambio_pct, 2)}% vs período anterior",
                kg_potenciales=round(kg_curr, 2),
                score=round(score, 2),
            ))
        return oportunidades

    # ------------------- helpers internos -------------------

    def _todos_los_productores(self) -> list[str]:
        rows = self.repository.fetch_all(
            "SELECT DISTINCT UPPER(nombre) AS nombre FROM empresas WHERE es_productor = 1 ORDER BY nombre"
        )
        return [str(r["nombre"]) for r in rows if r.get("nombre")]

    def _depositos_por_productor(self, productor: str) -> list[str]:
        rows = self.repository.fetch_all(
            """
            SELECT DISTINCT UPPER(dest.nombre) AS nombre
            FROM movimientos m
            LEFT JOIN empresas prod ON prod.id_empresa = m.id_productor
            LEFT JOIN empresas dest ON dest.id_empresa = m.id_destino
            WHERE UPPER(prod.nombre) = ? AND dest.nombre IS NOT NULL
            """,
            (productor,),
        )
        return [str(r["nombre"]) for r in rows if r.get("nombre")]

    def _mercados_por_productor(self, productor: str, *, export_only: bool = False) -> set[str]:
        export_clause = "AND m.solo_deposito = 0" if export_only else ""
        rows = self.repository.fetch_all(
            f"""
            SELECT DISTINCT UPPER(pais.nombre_pais) AS nombre
            FROM movimientos m
            LEFT JOIN empresas prod ON prod.id_empresa = m.id_productor
            LEFT JOIN paises pais ON pais.id_pais = m.id_pais
            WHERE UPPER(prod.nombre) = ? {export_clause}
            """,
            (productor,),
        )
        return {str(r["nombre"]) for r in rows if r.get("nombre")}

    def _kg_productor_total(self, productor: str) -> float:
        row = self.repository.fetch_one(
            """
            SELECT COALESCE(SUM(m.peso), 0) AS kg
            FROM movimientos m
            LEFT JOIN empresas prod ON prod.id_empresa = m.id_productor
            WHERE UPPER(prod.nombre) = ?
            """,
            (productor,),
        )
        return float(row["kg"] if row else 0)

    def _kg_productor_in_period(self, productor: str, start: str, end: str) -> float:
        row = self.repository.fetch_one(
            """
            SELECT COALESCE(SUM(m.peso), 0) AS kg
            FROM movimientos m
            LEFT JOIN empresas prod ON prod.id_empresa = m.id_productor
            WHERE UPPER(prod.nombre) = ? AND m.fecha >= ? AND m.fecha < ?
            """,
            (productor, start, end),
        )
        return float(row["kg"] if row else 0)

    def _company_name(self, company_id: int) -> str:
        row = self.repository.fetch_one(
            "SELECT nombre FROM empresas WHERE id_empresa = ?", (company_id,)
        )
        return str(row["nombre"]) if row else f"#{company_id}"

    def _require_company(self, name: str) -> int:
        company = self.repository.company_by_name(name)
        if not company:
            raise ValueError(f"Empresa no encontrada en SQLite: {name}")
        return int(company["id_empresa"])
