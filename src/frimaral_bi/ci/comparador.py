"""ComparadorEmpresasService — compara dos empresas cualesquiera y entrega
un comparativo completo (kg compartidos, %, mercados compartidos, etc.).

Diseñado para responder a la pregunta comercial "CALIRAL vs ARBIZA",
"CALIRAL vs FRIGORIFICO TACUAREMBO" o cualquier otra combinación sin
codificar lógica específica para una empresa.
"""
from __future__ import annotations

from pathlib import Path

from ..repositories import BIRepository
from .models import ComparativoEmpresas


class ComparadorEmpresasService:
    """Comparador genérico de dos empresas."""

    def __init__(self, database_path: Path) -> None:
        self.repository = BIRepository(database_path)

    def comparar(self, izquierda: str, derecha: str) -> ComparativoEmpresas:
        """Genera el comparativo completo entre dos empresas."""
        if izquierda.upper() == derecha.upper():
            raise ValueError("Las dos empresas deben ser distintas para comparar.")
        left_id = self._require_company(izquierda)
        right_id = self._require_company(derecha)

        kg_left = self.repository.total_kg(left_id)
        kg_right = self.repository.total_kg(right_id)
        kg_shared = self.repository.kg_between_companies(left_id, right_id)

        left_sets = self._dimension_sets(left_id)
        right_sets = self._dimension_sets(right_id)

        return ComparativoEmpresas(
            empresa_izquierda=izquierda,
            empresa_derecha=derecha,
            kg_izquierda=round(kg_left, 2),
            kg_derecha=round(kg_right, 2),
            kg_compartidos=round(kg_shared, 2),
            productores_compartidos=len(left_sets["productor"] & right_sets["productor"]),
            productores_solo_izquierda=len(left_sets["productor"] - right_sets["productor"]),
            productores_solo_derecha=len(right_sets["productor"] - left_sets["productor"]),
            mercados_compartidos=len(left_sets["mercado"] & right_sets["mercado"]),
            mercados_solo_izquierda=len(left_sets["mercado"] - right_sets["mercado"]),
            mercados_solo_derecha=len(right_sets["mercado"] - left_sets["mercado"]),
            clientes_compartidos=len(left_sets["cliente"] & right_sets["cliente"]),
            clientes_solo_izquierda=len(left_sets["cliente"] - right_sets["cliente"]),
            clientes_solo_derecha=len(right_sets["cliente"] - left_sets["cliente"]),
            productos_compartidos=len(left_sets["producto"] & right_sets["producto"]),
            productos_solo_izquierda=len(left_sets["producto"] - right_sets["producto"]),
            productos_solo_derecha=len(right_sets["producto"] - left_sets["producto"]),
            indice_solapamiento=self._indice_solapamiento(kg_left, kg_right, kg_shared),
        )

    def porcentaje_compartido(self, izquierda: str, derecha: str) -> dict[str, float]:
        """Devuelve los % de solapamiento sobre el total de cada empresa."""
        comparativo = self.comparar(izquierda, derecha)
        base_left = comparativo.kg_izquierda or 0.0
        base_right = comparativo.kg_derecha or 0.0
        shared = comparativo.kg_compartidos or 0.0
        return {
            "pct_sobre_izquierda": round(shared * 100 / base_left, 2) if base_left else 0.0,
            "pct_sobre_derecha": round(shared * 100 / base_right, 2) if base_right else 0.0,
            "pct_sobre_conjunto": round(
                shared * 100 / (base_left + base_right - shared), 2
            ) if (base_left + base_right - shared) else 0.0,
        }

    # ------------------- helpers internos -------------------

    def _dimension_sets(self, company_id: int) -> dict[str, set[str]]:
        return {
            dim: self.repository.company_dimension_set(company_id, dim)
            for dim in ("productor", "mercado", "cliente", "producto")
        }

    @staticmethod
    def _indice_solapamiento(kg_left: float, kg_right: float, kg_shared: float) -> float:
        """% de solapamiento ponderado por kg. Devuelve 0-100."""
        total = kg_left + kg_right - kg_shared
        if total <= 0:
            return 0.0
        return round(kg_shared * 100 / total, 2)

    def _require_company(self, name: str) -> int:
        company = self.repository.company_by_name(name)
        if not company:
            raise ValueError(f"Empresa no encontrada en SQLite: {name}")
        return int(company["id_empresa"])
