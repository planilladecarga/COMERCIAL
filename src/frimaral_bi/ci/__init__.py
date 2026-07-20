"""Paquete del Motor de Inteligencia Competitiva (COMPETITIVE_INTELLIGENCE_ENGINE).

Sprint 5 — FRIMARAL BI.

Servicios:

- CompetenciaService
- ComparadorEmpresasService
- RadarComercialService
- OportunidadesService
- AlertasService
- IndicadoresService
- ConsultasComercialesService
- CompetitiveIntelligenceEngine (orquestador)
"""
from __future__ import annotations

from .alertas import AlertasService
from .comparador import ComparadorEmpresasService
from .competencia import CompetenciaService
from .consultas import ConsultasComercialesService
from .engine import CompetitiveIntelligenceEngine
from .indicadores import IndicadoresService
from .models import (
    Alerta,
    CambioRadar,
    ComparativoEmpresas,
    IndiceCI,
    ItemCompetencia,
    Oportunidad,
    ResumenCI,
    RespuestaComercial,
)
from .oportunidades import OportunidadesService
from .persistencia import PersistenciaCI
from .radar import RadarComercialService

__all__ = [
    "AlertasService",
    "ComparadorEmpresasService",
    "CompetenciaService",
    "CompetitiveIntelligenceEngine",
    "ConsultasComercialesService",
    "IndicadoresService",
    "OportunidadesService",
    "RadarComercialService",
    "PersistenciaCI",
    "Alerta",
    "CambioRadar",
    "ComparativoEmpresas",
    "IndiceCI",
    "ItemCompetencia",
    "Oportunidad",
    "ResumenCI",
    "RespuestaComercial",
]
