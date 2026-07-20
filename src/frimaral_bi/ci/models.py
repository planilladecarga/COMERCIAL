"""Modelos del Motor de Inteligencia Competitiva (Sprint 5).

Dataclasses tipadas para cada salida de servicio. Todos implementan
`to_row()` para integrarse con el Libro Maestro BI y la persistencia
SQLite sin acoplamiento a dict.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from ..models import Row


def _row_from(obj: Any) -> Row:
    """Convierte una dataclass a Row (dict plano)."""
    return {k: v for k, v in asdict(obj).items()}


@dataclass(frozen=True)
class ComparativoEmpresas:
    """Resultado de comparar dos empresas cualesquiera."""

    empresa_izquierda: str
    empresa_derecha: str
    kg_izquierda: float
    kg_derecha: float
    kg_compartidos: float
    productores_compartidos: int
    productores_solo_izquierda: int
    productores_solo_derecha: int
    mercados_compartidos: int
    mercados_solo_izquierda: int
    mercados_solo_derecha: int
    clientes_compartidos: int
    clientes_solo_izquierda: int
    clientes_solo_derecha: int
    productos_compartidos: int
    productos_solo_izquierda: int
    productos_solo_derecha: int
    indice_solapamiento: float

    def to_row(self) -> Row:
        return _row_from(self)


@dataclass(frozen=True)
class ItemCompetencia:
    """Comparativo de la empresa focal contra un competidor concreto."""

    empresa_focal: str
    competidor: str
    productores_compartidos: int
    mercados_compartidos: int
    clientes_compartidos: int
    productos_compartidos: int
    kg_compartidos: float
    indice_similitud: float

    def to_row(self) -> Row:
        return _row_from(self)


@dataclass(frozen=True)
class CambioRadar:
    """Cambio detectado por el radar comercial (nuevo/perdido, caída/crecimiento)."""

    tipo: str
    dimension: str
    valor: str
    empresa_focal: str
    detalle: str
    magnitud: float
    severidad: str

    _RANK = {"alta": 0, "media": 1, "info": 2}

    def severity_rank(self) -> int:
        return self._RANK.get(self.severidad, 3)

    def to_row(self) -> Row:
        return _row_from(self)


@dataclass(frozen=True)
class Oportunidad:
    """Oportunidad comercial detectada con score y motivo."""

    tipo: str
    entidad: str
    empresa_focal: str
    motivo: str
    kg_potenciales: float
    score: float

    def to_row(self) -> Row:
        return _row_from(self)


@dataclass(frozen=True)
class Alerta:
    """Alerta de riesgo comercial detectada."""

    tipo: str
    entidad: str
    empresa_focal: str
    detalle: str
    magnitud: float
    severidad: str

    _RANK = {"alta": 0, "media": 1, "info": 2}

    def severity_rank(self) -> int:
        return self._RANK.get(self.severidad, 3)

    def to_row(self) -> Row:
        return _row_from(self)


@dataclass(frozen=True)
class IndiceCI:
    """Índices calculados para una empresa focal."""

    empresa: str
    indice_diversificacion: float
    indice_fidelidad: float
    indice_competencia: float
    indice_riesgo: float
    indice_oportunidad: float
    indice_general: float

    def to_row(self) -> Row:
        return _row_from(self)


@dataclass(frozen=True)
class RespuestaComercial:
    """Respuesta a una consulta comercial en lenguaje natural."""

    pregunta: str
    respuesta: str
    datos: list[Row] = field(default_factory=list)

    def to_row(self) -> Row:
        return {
            "pregunta": self.pregunta,
            "respuesta": self.respuesta,
            "cantidad_registros": len(self.datos),
        }


@dataclass(frozen=True)
class ResumenCI:
    """Resumen agregado del motor CI para una empresa focal."""

    empresa_focal: str
    total_competidores: int
    total_oportunidades: int
    total_alertas: int
    total_cambios_radar: int
    indice_general: float

    def to_row(self) -> Row:
        return _row_from(self)
