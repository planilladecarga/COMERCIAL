"""IndicadoresService — calcula índices comerciales agregados para una
empresa focal.

Índices (todos en escala 0-100 salvo donde se indique):

- DIVERSIFICACION: distribución de kg entre mercados (1 - HHI normalizado).
  100 = muy diversificado, 0 = un solo mercado.
- FIDELIDAD: % de productores que siguen activos en el último período
  respecto al histórico completo.
- COMPETENCIA: índice de solapamiento promedio con los top competidores
  (Jaccard sobre productores, mercados, clientes y productos).
- RIESGO: 100 - media ponderada de severidad de alertas activas
  (más alertas → más riesgo).
- OPORTUNIDAD: score medio del top 10 de oportunidades detectadas.
- GENERAL: media simple de los 5 índices anteriores.
"""
from __future__ import annotations

from pathlib import Path

from ..config import UmbralesCI
from ..repositories import BIRepository
from .alertas import AlertasService
from .competencia import CompetenciaService
from .models import IndiceCI
from .oportunidades import OportunidadesService


class IndicadoresService:
    """Calcula los 5 índices CI para una empresa focal."""

    def __init__(
        self,
        database_path: Path,
        umbrales: UmbralesCI | None = None,
    ) -> None:
        self.repository = BIRepository(database_path)
        self.umbrales = umbrales or UmbralesCI()
        self._competencia = CompetenciaService(database_path)
        self._alertas = AlertasService(database_path, umbrales)
        self._oportunidades = OportunidadesService(database_path, umbrales)

    def calcular(self, empresa_focal: str) -> IndiceCI:
        div = self.indice_diversificacion(empresa_focal)
        fid = self.indice_fidelidad(empresa_focal)
        comp = self.indice_competencia(empresa_focal)
        riesgo = self.indice_riesgo(empresa_focal)
        oport = self.indice_oportunidad(empresa_focal)
        general = round((div + fid + comp + riesgo + oport) / 5, 2)
        return IndiceCI(
            empresa=empresa_focal,
            indice_diversificacion=div,
            indice_fidelidad=fid,
            indice_competencia=comp,
            indice_riesgo=riesgo,
            indice_oportunidad=oport,
            indice_general=general,
        )

    def indice_diversificacion(self, empresa_focal: str) -> float:
        """Diversificación de mercados: 1 - HHI normalizado (0-100)."""
        company_id = self._require_company(empresa_focal)
        mercados = self.repository.aggregate_relation(company_id, "pais.nombre_pais", "mercado")
        total = sum(float(m.get("kg") or 0) for m in mercados)
        if total <= 0 or not mercados:
            return 0.0
        hhi = sum((float(m.get("kg") or 0) * 100 / total) ** 2 for m in mercados) / 10000
        n = len(mercados)
        if n <= 1:
            return 0.0
        hhi_norm = (hhi - 1 / n) / (1 - 1 / n)
        return round(max(0.0, min(100.0, (1 - hhi_norm) * 100)), 2)

    def indice_fidelidad(self, empresa_focal: str) -> float:
        """% de productores históricos que siguen activos en el último período."""
        company_id = self._require_company(empresa_focal)
        historic = self.repository.company_dimension_set(company_id, "productor")
        if not historic:
            return 0.0
        first_date, last_date = self.repository.first_and_last_date(company_id)
        if not first_date or not last_date:
            return 0.0
        # Considera "último período" = último 25% del rango activo
        from datetime import datetime, timedelta
        start = datetime.fromisoformat(first_date[:10]).date()
        end = datetime.fromisoformat(last_date[:10]).date()
        span = (end - start).days
        if span <= 0:
            return 100.0
        recent_start = (end - timedelta(days=max(1, span // 4))).isoformat()
        rows = self.repository.fetch_all(
            f"""
                SELECT DISTINCT UPPER(prod.nombre) AS value
                {self.repository.DIMENSION_JOINS}
                WHERE (m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?)
                  AND m.fecha >= ?
            """,
            (company_id, company_id, company_id, recent_start),
        )
        recent = {str(r["value"]).upper() for r in rows if r.get("value")}
        return round(len(historic & recent) * 100 / len(historic), 2)

    def indice_competencia(self, empresa_focal: str) -> float:
        """Solapamiento promedio con los top competidores."""
        items = self._competencia.comparar_todos(empresa_focal)
        if not items:
            return 0.0
        top = items[:10]
        return round(sum(i.indice_similitud for i in top) / len(top), 2)

    def indice_riesgo(self, empresa_focal: str) -> float:
        """100 - severidad promedio de alertas activas (más alertas, menor índice)."""
        alertas = self._alertas.escanear(empresa_focal)
        if not alertas:
            return 100.0
        severity_score = {"alta": 50, "media": 25, "info": 5}
        total_penalty = sum(severity_score.get(a.severidad, 0) for a in alertas)
        # Penaliza también por cantidad de alertas
        count_penalty = min(50.0, len(alertas) * 5)
        return round(max(0.0, 100.0 - total_penalty - count_penalty), 2)

    def indice_oportunidad(self, empresa_focal: str) -> float:
        """Score medio del top 10 de oportunidades detectadas."""
        oportunidades = self._oportunidades.ranking(empresa_focal, limite=10)
        if not oportunidades:
            return 0.0
        return round(sum(o.score for o in oportunidades) / len(oportunidades), 2)

    # ------------------- helpers internos -------------------

    def _require_company(self, name: str) -> int:
        company = self.repository.company_by_name(name)
        if not company:
            raise ValueError(f"Empresa no encontrada en SQLite: {name}")
        return int(company["id_empresa"])
