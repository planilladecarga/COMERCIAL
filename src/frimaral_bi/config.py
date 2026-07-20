"""Configuración declarativa del Motor de Inteligencia Competitiva.

Centraliza la empresa focal por defecto y los umbrales comerciales para que
los servicios no contengan constantes mágicas. Todos los servicios reciben
estos valores por inyección, lo que permite ejecutar el motor con cualquier
empresa focal (no solamente CALIRAL) sin tocar código.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class UmbralesCI:
    """Umbrales comerciales configurables para Alertas y Oportunidades.

    Todos los valores son porcentajes en escala 0-100 o conteos absolutos.
    Un servicio nunca debe comparar contra un número suelto: si surge un nuevo
    umbral, añádelo aquí para mantener una única fuente de verdad.
    """

    caida_participacion_pct: float = 20.0
    crecimiento_fuerte_pct: float = 30.0
    dependencia_cliente_pct: float = 50.0
    concentracion_mercado_pct: float = 60.0
    meses_inactividad_cliente: int = 3
    dias_periodo_actual: int = 90
    dias_periodo_previo: int = 90
    min_kg_oportunidad: float = 100.0
    top_productores_ranking: int = 20


@dataclass(frozen=True)
class ConfigCI:
    """Configuración global del motor de inteligencia competitiva.

    `empresa_focal` se mantiene como default para que el dashboard ejecutivo
    pueda invocarse sin parámetros, pero todos los servicios aceptan una
    empresa distinta por llamada, cumpliendo el requisito de no codificar
    lógica específica para una empresa.
    """

    empresa_focal: str = "CALIRAL"
    umbrales: UmbralesCI = field(default_factory=UmbralesCI)


# Instancia por defecto reutilizable por el CLI y los dashboards.
CONFIG_CI_DEFAULT = ConfigCI()
