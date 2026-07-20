"""RadarComercialService — detecta automáticamente nuevos / perdidos,
caídas y crecimientos comparando dos períodos.

Los períodos son configurables (`periodo_actual_dias`,
`periodo_previo_dias` en UmbralesCI). Por defecto compara los últimos
90 días contra los 90 días anteriores, lo que da estabilidad enough para
volúmenes comerciales sin perder reactividad ante fugas de clientes.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from ..config import UmbralesCI
from ..repositories import BIRepository
from .models import CambioRadar


class RadarComercialService:
    """Detecta cambios temporales en productores, mercados y clientes."""

    DIMENSIONES = ("productor", "mercado", "cliente")

    def __init__(
        self,
        database_path: Path,
        umbrales: UmbralesCI | None = None,
    ) -> None:
        self.repository = BIRepository(database_path)
        self.umbrales = umbrales or UmbralesCI()

    def escanear(self, empresa_focal: str) -> list[CambioRadar]:
        """Ejecuta el radar completo sobre la empresa focal."""
        cambios: list[CambioRadar] = []
        cambios.extend(self._nuevos_y_perdidos(empresa_focal))
        cambios.extend(self._caidas_y_crecimientos(empresa_focal))
        return sorted(
            cambios,
            key=lambda c: (c.severity_rank(), -c.magnitud),
        )

    def nuevos_productores(self, empresa_focal: str) -> list[CambioRadar]:
        return [c for c in self._nuevos_y_perdidos(empresa_focal)
                if c.tipo == "Nuevo productor"]

    def productores_perdidos(self, empresa_focal: str) -> list[CambioRadar]:
        return [c for c in self._nuevos_y_perdidos(empresa_focal)
                if c.tipo == "Productor perdido"]

    def caidas_importantes(self, empresa_focal: str) -> list[CambioRadar]:
        return [c for c in self._caidas_y_crecimientos(empresa_focal)
                if c.tipo == "Caída importante"]

    def crecimientos_importantes(self, empresa_focal: str) -> list[CambioRadar]:
        return [c for c in self._caidas_y_crecimientos(empresa_focal)
                if c.tipo == "Crecimiento importante"]

    # ------------------- helpers internos -------------------

    def _nuevos_y_perdidos(self, empresa_focal: str) -> list[CambioRadar]:
        company_id = self._require_company(empresa_focal)
        current_start, current_end, previous_start, previous_end = self._period_bounds()
        cambios: list[CambioRadar] = []
        for dimension in self.DIMENSIONES:
            current = self._dimension_set_in_period(company_id, dimension, current_start, current_end)
            previous = self._dimension_set_in_period(company_id, dimension, previous_start, previous_end)
            nuevos = current - previous
            perdidos = previous - current
            for valor in nuevos:
                cambios.append(CambioRadar(
                    tipo=f"Nuevo {dimension}",
                    dimension=dimension,
                    valor=valor,
                    empresa_focal=empresa_focal,
                    detalle=f"{dimension.capitalize()} nuevo en el último período",
                    magnitud=1.0,
                    severidad="info",
                ))
            for valor in perdidos:
                cambios.append(CambioRadar(
                    tipo=f"{dimension.capitalize()} perdido",
                    dimension=dimension,
                    valor=valor,
                    empresa_focal=empresa_focal,
                    detalle=f"{dimension.capitalize()} no aparece en el último período",
                    magnitud=1.0,
                    severidad="alta" if dimension == "productor" else "media",
                ))
        return cambios

    def _caidas_y_crecimientos(self, empresa_focal: str) -> list[CambioRadar]:
        company_id = self._require_company(empresa_focal)
        current_start, current_end, previous_start, previous_end = self._period_bounds()
        cambios: list[CambioRadar] = []
        for dimension in self.DIMENSIONES:
            current = self._dimension_set_in_period(company_id, dimension, current_start, current_end)
            for valor in current:
                kg_prev = self._kg_in_period_by_dimension(
                    dimension, valor, previous_start, previous_end
                )
                kg_curr = self._kg_in_period_by_dimension(
                    dimension, valor, current_start, current_end
                )
                if kg_prev <= 0 and kg_curr > 0:
                    # ya está reportado como "Nuevo"
                    continue
                if kg_prev <= 0:
                    continue
                cambio_pct = (kg_curr - kg_prev) * 100 / kg_prev
                if cambio_pct <= -self.umbrales.caida_participacion_pct:
                    cambios.append(CambioRadar(
                        tipo="Caída importante",
                        dimension=dimension,
                        valor=valor,
                        empresa_focal=empresa_focal,
                        detalle=f"Caída de {round(cambio_pct, 2)}% vs período anterior",
                        magnitud=round(abs(cambio_pct), 2),
                        severidad="alta" if cambio_pct <= -50 else "media",
                    ))
                elif cambio_pct >= self.umbrales.crecimiento_fuerte_pct:
                    cambios.append(CambioRadar(
                        tipo="Crecimiento importante",
                        dimension=dimension,
                        valor=valor,
                        empresa_focal=empresa_focal,
                        detalle=f"Crecimiento de {round(cambio_pct, 2)}% vs período anterior",
                        magnitud=round(cambio_pct, 2),
                        severidad="media",
                    ))
        return cambios

    def _period_bounds(self) -> tuple[str, str, str, str]:
        """Devuelve (current_start, current_end, previous_start, previous_end) en ISO."""
        today = datetime.now().date()
        current_end = today.isoformat()
        current_start = (today - timedelta(days=self.umbrales.dias_periodo_actual)).isoformat()
        previous_end = current_start
        previous_start = (today - timedelta(
            days=self.umbrales.dias_periodo_actual + self.umbrales.dias_periodo_previo
        )).isoformat()
        return current_start, current_end, previous_start, previous_end

    def _dimension_set_in_period(
        self,
        company_id: int,
        dimension: str,
        start: str,
        end: str,
    ) -> set[str]:
        expression = self.repository._dimension_expression(dimension)  # noqa: SLF001
        sql = f"""
            SELECT DISTINCT {expression} AS value
            {self.repository.DIMENSION_JOINS}
            WHERE (m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?)
              AND m.fecha >= ? AND m.fecha < ?
        """
        return {
            str(row["value"]).upper()
            for row in self.repository.fetch_all(
                sql, (company_id, company_id, company_id, start, end)
            )
            if row.get("value")
        }

    def _kg_in_period_by_dimension(
        self,
        dimension: str,
        value: str,
        start: str,
        end: str,
    ) -> float:
        expression = self.repository._dimension_expression(dimension)  # noqa: SLF001
        sql = f"""
            SELECT COALESCE(SUM(m.peso), 0) AS kg
            {self.repository.DIMENSION_JOINS}
            WHERE {expression} = ? AND m.fecha >= ? AND m.fecha < ?
        """
        row = self.repository.fetch_one(sql, (value, start, end))
        return float(row["kg"] if row else 0)

    def _require_company(self, name: str) -> int:
        company = self.repository.company_by_name(name)
        if not company:
            raise ValueError(f"Empresa no encontrada en SQLite: {name}")
        return int(company["id_empresa"])
