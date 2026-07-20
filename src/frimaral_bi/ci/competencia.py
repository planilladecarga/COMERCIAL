"""CompetenciaService — detecta automáticamente productores, mercados,
clientes y productos compartidos y exclusivos entre la empresa focal y
cualquier otra empresa de la base.

No contiene lógica específica para ninguna empresa: la empresa focal se
recibe por parámetro en cada llamada.
"""
from __future__ import annotations

from pathlib import Path

from ..repositories import BIRepository
from .models import ItemCompetencia


class CompetenciaService:
    """Detecta solapamientos y exclusividades entre la empresa focal y el resto."""

    DIMENSIONES = ("productor", "mercado", "cliente", "producto")

    def __init__(self, database_path: Path) -> None:
        self.repository = BIRepository(database_path)

    def comparar_todos(self, empresa_focal: str) -> list[ItemCompetencia]:
        """Recorre todas las empresas activas y devuelve un ItemCompetencia por cada una.

        Solo se incluyen competidores con al menos un solapamiento en alguna
        dimensión, para no inflar el ranking con empresas sin relación.
        """
        focal_id = self._require_company(empresa_focal)
        focals = self._dimension_sets(focal_id)
        output: list[ItemCompetencia] = []
        for company in self.repository.all_companies():
            other_id = int(company["id_empresa"])
            if other_id == focal_id:
                continue
            others = self._dimension_sets(other_id)
            shared_kg = self.repository.kg_between_companies(focal_id, other_id)
            shared_productores = len(focals["productor"] & others["productor"])
            shared_mercados = len(focals["mercado"] & others["mercado"])
            shared_clientes = len(focals["cliente"] & others["cliente"])
            shared_productos = len(focals["producto"] & others["producto"])
            if not any([shared_productores, shared_mercados, shared_clientes, shared_productos, shared_kg > 0]):
                continue
            indice = self._indice_similitud(focals, others)
            output.append(ItemCompetencia(
                empresa_focal=empresa_focal,
                competidor=company["nombre"],
                productores_compartidos=shared_productores,
                mercados_compartidos=shared_mercados,
                clientes_compartidos=shared_clientes,
                productos_compartidos=shared_productos,
                kg_compartidos=round(shared_kg, 2),
                indice_similitud=indice,
            ))
        return sorted(output, key=lambda item: item.indice_similitud, reverse=True)

    def comparar_con(self, empresa_focal: str, competidor: str) -> ItemCompetencia | None:
        """Comparativo puntual contra un competidor nombrado."""
        for item in self.comparar_todos(empresa_focal):
            if item.competidor.upper() == competidor.upper():
                return item
        return None

    def productores_compartidos(self, empresa_focal: str, competidor: str) -> list[str]:
        """Lista de productores que usan ambas empresas."""
        focal_id = self._require_company(empresa_focal)
        other_id = self._require_company(competidor)
        focals = self.repository.company_dimension_set(focal_id, "productor")
        others = self.repository.company_dimension_set(other_id, "productor")
        return sorted(focals & others)

    def productores_exclusivos(self, empresa_focal: str, competidor: str) -> dict[str, list[str]]:
        """Productores exclusivos de cada empresa."""
        focal_id = self._require_company(empresa_focal)
        other_id = self._require_company(competidor)
        focals = self.repository.company_dimension_set(focal_id, "productor")
        others = self.repository.company_dimension_set(other_id, "productor")
        return {
            "solo_focal": sorted(focals - others),
            "solo_competidor": sorted(others - focals),
        }

    def mercados_compartidos(self, empresa_focal: str, competidor: str) -> list[str]:
        focal_id = self._require_company(empresa_focal)
        other_id = self._require_company(competidor)
        return sorted(
            self.repository.company_dimension_set(focal_id, "mercado")
            & self.repository.company_dimension_set(other_id, "mercado")
        )

    def clientes_compartidos(self, empresa_focal: str, competidor: str) -> list[str]:
        focal_id = self._require_company(empresa_focal)
        other_id = self._require_company(competidor)
        return sorted(
            self.repository.company_dimension_set(focal_id, "cliente")
            & self.repository.company_dimension_set(other_id, "cliente")
        )

    def productos_compartidos(self, empresa_focal: str, competidor: str) -> list[str]:
        focal_id = self._require_company(empresa_focal)
        other_id = self._require_company(competidor)
        return sorted(
            self.repository.company_dimension_set(focal_id, "producto")
            & self.repository.company_dimension_set(other_id, "producto")
        )

    # ------------------- helpers internos -------------------

    def _dimension_sets(self, company_id: int) -> dict[str, set[str]]:
        return {
            dim: self.repository.company_dimension_set(company_id, dim)
            for dim in self.DIMENSIONES
        }

    @staticmethod
    def _indice_similitud(
        left: dict[str, set[str]],
        right: dict[str, set[str]],
    ) -> float:
        """Jaccard promedio sobre las 4 dimensiones. Devuelve 0-100."""
        scores: list[float] = []
        for key in CompetenciaService.DIMENSIONES:
            union = left[key] | right[key]
            scores.append((len(left[key] & right[key]) / len(union)) if union else 0.0)
        return round(sum(scores) / len(scores) * 100, 2)

    def _require_company(self, name: str) -> int:
        company = self.repository.company_by_name(name)
        if not company:
            raise ValueError(f"Empresa no encontrada en SQLite: {name}")
        return int(company["id_empresa"])
