"""CompetitiveIntelligenceEngine — orquestador del Sprint 5.

Ejecuta todos los servicios CI para una empresa focal, persiste los
resultados en tablas `ci_*` y devuelve un resumen agregado listo para
alimentar el Libro Maestro BI y los dashboards.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..config import ConfigCI, CONFIG_CI_DEFAULT
from ..models import Row
from .alertas import AlertasService
from .comparador import ComparadorEmpresasService
from .competencia import CompetenciaService
from .consultas import ConsultasComercialesService
from .indicadores import IndicadoresService
from .models import (
    Alerta,
    CambioRadar,
    ComparativoEmpresas,
    IndiceCI,
    ItemCompetencia,
    Oportunidad,
    ResumenCI,
)
from .oportunidades import OportunidadesService
from .persistencia import PersistenciaCI
from .radar import RadarComercialService


@dataclass
class ResultadoCI:
    """Resultado completo de una ejecución del motor CI."""

    empresa_focal: str
    competencia: list[ItemCompetencia]
    radar: list[CambioRadar]
    oportunidades: list[Oportunidad]
    alertas: list[Alerta]
    indices: IndiceCI
    comparativos: list[ComparativoEmpresas]
    resumen: ResumenCI

    def to_rows(self) -> dict[str, list[Row]]:
        """Devuelve todas las salidas como filas para integración con workbook."""
        return {
            "competencia": [i.to_row() for i in self.competencia],
            "radar": [c.to_row() for c in self.radar],
            "oportunidades": [o.to_row() for o in self.oportunidades],
            "alertas": [a.to_row() for a in self.alertas],
            "indices": [self.indices.to_row()],
            "comparativos": [c.to_row() for c in self.comparativos],
            "resumen": [self.resumen.to_row()],
        }


class CompetitiveIntelligenceEngine:
    """Orquesta todos los servicios CI para una empresa focal."""

    def __init__(
        self,
        database_path: Path,
        config: ConfigCI | None = None,
    ) -> None:
        self.database_path = database_path
        self.config = config or CONFIG_CI_DEFAULT
        self.umbrales = self.config.umbrales
        self._competencia = CompetenciaService(database_path)
        self._comparador = ComparadorEmpresasService(database_path)
        self._radar = RadarComercialService(database_path, self.umbrales)
        self._oportunidades = OportunidadesService(database_path, self.umbrales)
        self._alertas = AlertasService(database_path, self.umbrales)
        self._indicadores = IndicadoresService(database_path, self.umbrales)
        self._consultas = ConsultasComercialesService(database_path)
        self._persistencia = PersistenciaCI(database_path)

    def ejecutar(
        self,
        empresa_focal: str | None = None,
        *,
        persistir: bool = True,
        comparar_con: list[str] | None = None,
    ) -> ResultadoCI:
        """Ejecuta el motor completo y (opcionalmente) persiste resultados."""
        focal = empresa_focal or self.config.empresa_focal
        fecha = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

        competencia = self._competencia.comparar_todos(focal)
        radar = self._radar.escanear(focal)
        oportunidades = self._oportunidades.ranking(focal)
        alertas = self._alertas.escanear(focal)
        indices = self._indicadores.calcular(focal)
        comparativos = self._comparativos_seleccionados(focal, comparar_con)

        resumen = ResumenCI(
            empresa_focal=focal,
            total_competidores=len(competencia),
            total_oportunidades=len(oportunidades),
            total_alertas=len(alertas),
            total_cambios_radar=len(radar),
            indice_general=indices.indice_general,
        )

        resultado = ResultadoCI(
            empresa_focal=focal,
            competencia=competencia,
            radar=radar,
            oportunidades=oportunidades,
            alertas=alertas,
            indices=indices,
            comparativos=comparativos,
            resumen=resumen,
        )

        if persistir:
            self._persistir(resultado, fecha)

        return resultado

    def consultar(self, pregunta: str, empresa_focal: str | None = None) -> object:
        """Atajo para responder preguntas comerciales en lenguaje natural."""
        focal = empresa_focal or self.config.empresa_focal
        return self._consultas.preguntar(pregunta, focal)

    # ------------------- helpers internos -------------------

    def _comparativos_seleccionados(
        self,
        empresa_focal: str,
        comparar_con: list[str] | None,
    ) -> list[ComparativoEmpresas]:
        if not comparar_con:
            # Por defecto compara contra los top 3 competidores por similitud
            top = self._competencia.comparar_todos(empresa_focal)[:3]
            comparar_con = [t.competidor for t in top]
        output: list[ComparativoEmpresas] = []
        for other in comparar_con:
            try:
                output.append(self._comparador.comparar(empresa_focal, other))
            except ValueError:
                continue
        return output

    def _persistir(self, resultado: ResultadoCI, fecha: str) -> None:
        self._persistencia.initialize()
        self._persistencia.limpiar(resultado.empresa_focal)
        self._persistencia.guardar_competencia(resultado.competencia, fecha)
        self._persistencia.guardar_radar(resultado.radar, fecha)
        self._persistencia.guardar_oportunidades(resultado.oportunidades, fecha)
        self._persistencia.guardar_alertas(resultado.alertas, fecha)
        self._persistencia.guardar_indice(resultado.indices, fecha)
        for comparativo in resultado.comparativos:
            self._persistencia.guardar_comparador(comparativo, fecha)
