"""AlertasService — detecta riesgos comerciales para la empresa focal.

Riesgos detectados:

- DEPENDENCIA_CLIENTE: un solo cliente concentra más del umbral % de los kg.
- CAIDA_PARTICIPACION: la empresa focal cae fuertemente en un mercado o cliente.
- CONCENTRACION_MERCADO: un solo mercado concentra más del umbral % de los kg.
- CLIENTE_INACTIVO: cliente sin movimientos en los últimos N meses.
- MERCADO_DESCENSO: mercado con caída importante de volumen.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from ..config import UmbralesCI
from ..repositories import BIRepository
from .models import Alerta


class AlertasService:
    """Detecta automáticamente riesgos comerciales para la empresa focal."""

    def __init__(
        self,
        database_path: Path,
        umbrales: UmbralesCI | None = None,
    ) -> None:
        self.repository = BIRepository(database_path)
        self.umbrales = umbrales or UmbralesCI()

    def escanear(self, empresa_focal: str) -> list[Alerta]:
        alertas: list[Alerta] = []
        alertas.extend(self.dependencia_cliente(empresa_focal))
        alertas.extend(self.caida_participacion(empresa_focal))
        alertas.extend(self.concentracion_mercado(empresa_focal))
        alertas.extend(self.clientes_inactivos(empresa_focal))
        alertas.extend(self.mercados_descenso(empresa_focal))
        return sorted(alertas, key=lambda a: (a.severity_rank(), -a.magnitud))

    def dependencia_cliente(self, empresa_focal: str) -> list[Alerta]:
        company_id = self._require_company(empresa_focal)
        clientes = self.repository.aggregate_relation(company_id, "dest.nombre", "cliente")
        total_kg = sum(float(c.get("kg") or 0) for c in clientes)
        if total_kg <= 0:
            return []
        alertas: list[Alerta] = []
        for c in clientes:
            kg = float(c.get("kg") or 0)
            pct = kg * 100 / total_kg
            if pct >= self.umbrales.dependencia_cliente_pct:
                alertas.append(Alerta(
                    tipo="DEPENDENCIA_CLIENTE",
                    entidad=str(c.get("nombre")),
                    empresa_focal=empresa_focal,
                    detalle=f"Cliente concentra {round(pct, 2)}% de los kg",
                    magnitud=round(pct, 2),
                    severidad="alta" if pct >= 75 else "media",
                ))
        return alertas

    def caida_participacion(self, empresa_focal: str) -> list[Alerta]:
        company_id = self._require_company(empresa_focal)
        today = datetime.now().date()
        current_start = (today - timedelta(days=self.umbrales.dias_periodo_actual)).isoformat()
        previous_start = (today - timedelta(
            days=self.umbrales.dias_periodo_actual + self.umbrales.dias_periodo_previo
        )).isoformat()
        previous_end = current_start
        current_kg = self.repository.company_period_kg(company_id, current_start, today.isoformat())
        previous_kg = self.repository.company_period_kg(company_id, previous_start, previous_end)
        if previous_kg <= 0:
            return []
        cambio_pct = (current_kg - previous_kg) * 100 / previous_kg
        if cambio_pct > -self.umbrales.caida_participacion_pct:
            return []
        return [Alerta(
            tipo="CAIDA_PARTICIPACION",
            entidad=empresa_focal,
            empresa_focal=empresa_focal,
            detalle=f"Caída de {round(cambio_pct, 2)}% vs período anterior",
            magnitud=round(abs(cambio_pct), 2),
            severidad="alta" if cambio_pct <= -50 else "media",
        )]

    def concentracion_mercado(self, empresa_focal: str) -> list[Alerta]:
        company_id = self._require_company(empresa_focal)
        mercados = self.repository.aggregate_relation(company_id, "pais.nombre_pais", "mercado")
        total_kg = sum(float(m.get("kg") or 0) for m in mercados)
        if total_kg <= 0:
            return []
        alertas: list[Alerta] = []
        for m in mercados:
            kg = float(m.get("kg") or 0)
            pct = kg * 100 / total_kg
            if pct >= self.umbrales.concentracion_mercado_pct:
                alertas.append(Alerta(
                    tipo="CONCENTRACION_MERCADO",
                    entidad=str(m.get("nombre")),
                    empresa_focal=empresa_focal,
                    detalle=f"Mercado concentra {round(pct, 2)}% de los kg",
                    magnitud=round(pct, 2),
                    severidad="alta" if pct >= 80 else "media",
                ))
        return alertas

    def clientes_inactivos(self, empresa_focal: str) -> list[Alerta]:
        company_id = self._require_company(empresa_focal)
        cutoff = (datetime.now().date() - timedelta(days=self.umbrales.meses_inactividad_cliente * 30)).isoformat()
        rows = self.repository.fetch_all(
            """
            SELECT dest.nombre AS cliente, MAX(m.fecha) AS ultima_fecha
            FROM movimientos m
            LEFT JOIN empresas dest ON dest.id_empresa = m.id_destino
            WHERE (m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?)
              AND dest.nombre IS NOT NULL
            GROUP BY dest.nombre
            HAVING MAX(m.fecha) < ?
            """,
            (company_id, company_id, company_id, cutoff),
        )
        alertas: list[Alerta] = []
        for r in rows:
            alertas.append(Alerta(
                tipo="CLIENTE_INACTIVO",
                entidad=str(r["cliente"]),
                empresa_focal=empresa_focal,
                detalle=f"Sin movimientos desde {r['ultima_fecha']}",
                magnitud=0.0,
                severidad="media",
            ))
        return alertas

    def mercados_descenso(self, empresa_focal: str) -> list[Alerta]:
        company_id = self._require_company(empresa_focal)
        today = datetime.now().date()
        current_start = (today - timedelta(days=self.umbrales.dias_periodo_actual)).isoformat()
        previous_start = (today - timedelta(
            days=self.umbrales.dias_periodo_actual + self.umbrales.dias_periodo_previo
        )).isoformat()
        previous_end = current_start
        mercados = self.repository.aggregate_relation(company_id, "pais.nombre_pais", "mercado")
        alertas: list[Alerta] = []
        for m in mercados:
            mercado = str(m.get("nombre"))
            kg_curr = self._kg_mercado_in_period(mercado, current_start, today.isoformat())
            kg_prev = self._kg_mercado_in_period(mercado, previous_start, previous_end)
            if kg_prev <= 0:
                continue
            cambio = (kg_curr - kg_prev) * 100 / kg_prev
            if cambio <= -self.umbrales.caida_participacion_pct:
                alertas.append(Alerta(
                    tipo="MERCADO_DESCENSO",
                    entidad=mercado,
                    empresa_focal=empresa_focal,
                    detalle=f"Caída de {round(cambio, 2)}% en mercado vs período anterior",
                    magnitud=round(abs(cambio), 2),
                    severidad="alta" if cambio <= -50 else "media",
                ))
        return alertas

    # ------------------- helpers internos -------------------

    def _kg_mercado_in_period(self, mercado: str, start: str, end: str) -> float:
        row = self.repository.fetch_one(
            """
            SELECT COALESCE(SUM(m.peso), 0) AS kg
            FROM movimientos m
            LEFT JOIN paises pais ON pais.id_pais = m.id_pais
            WHERE UPPER(pais.nombre_pais) = ? AND m.fecha >= ? AND m.fecha < ?
            """,
            (mercado, start, end),
        )
        return float(row["kg"] if row else 0)

    def _require_company(self, name: str) -> int:
        company = self.repository.company_by_name(name)
        if not company:
            raise ValueError(f"Empresa no encontrada en SQLite: {name}")
        return int(company["id_empresa"])
