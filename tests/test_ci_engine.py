"""Tests del Motor de Inteligencia Competitiva (Sprint 5)."""
from __future__ import annotations

from pathlib import Path

import pytest

from frimaral_bi.ci import (
    AlertasService,
    ComparadorEmpresasService,
    CompetenciaService,
    CompetitiveIntelligenceEngine,
    ConsultasComercialesService,
    IndicadoresService,
    OportunidadesService,
    RadarComercialService,
)
from frimaral_bi.models import ImportConfig
from frimaral_bi.pipeline import MotorImportacionMGAP


@pytest.fixture()
def database_path(tmp_path: Path) -> Path:
    """Construye una BD SQLite de prueba con el fixture ampliado."""
    database_path = tmp_path / "frimaral_bi.db"
    MotorImportacionMGAP().run(
        ImportConfig(
            source_path=Path("tests/fixtures/mgap_sample.csv"),
            database_path=database_path,
            normalized_copy_path=tmp_path / "normalizado.csv",
            log_path=tmp_path / "log.md",
        )
    )
    return database_path


# ----------------------------------------------------------------------
# CompetenciaService
# ----------------------------------------------------------------------


def test_competencia_detecta_solapamientos_caliral_arbiza(database_path: Path) -> None:
    service = CompetenciaService(database_path)
    items = service.comparar_todos("CALIRAL")
    assert items, "Debe detectar al menos un competidor"
    arbiza = next((i for i in items if i.competidor == "ARBIZA"), None)
    assert arbiza is not None
    assert arbiza.productores_compartidos >= 3  # Alfa, Beta, San Jacinto
    assert arbiza.mercados_compartidos >= 1
    assert 0 <= arbiza.indice_similitud <= 100
    # Kg compartidos puede ser 0 cuando ambas son certificadores (no
    # co-aparecen en el mismo movimiento), pero el solapamiento estructural
    # (productores, mercados) debe ser > 0.
    assert arbiza.indice_similitud > 0


def test_competencia_comparar_con_empresa_inexistente_raises(database_path: Path) -> None:
    service = CompetenciaService(database_path)
    with pytest.raises(ValueError):
        service.comparar_todos("Empresa Inexistente")


def test_competencia_productores_compartidos_caliral_arbiza(database_path: Path) -> None:
    service = CompetenciaService(database_path)
    compartidos = service.productores_compartidos("CALIRAL", "ARBIZA")
    assert "PRODUCTOR ALFA" in compartidos
    assert "PRODUCTOR BETA" in compartidos
    assert "SAN JACINTO" in compartidos


def test_competencia_productores_exclusivos_caliral_arbiza(database_path: Path) -> None:
    service = CompetenciaService(database_path)
    exclusivos = service.productores_exclusivos("CALIRAL", "ARBIZA")
    assert "solo_focal" in exclusivos
    assert "solo_competidor" in exclusivos
    # Productores que usan CALIRAL pero no ARBIZA: Delta, Zeta
    assert "PRODUCTOR DELTA" in exclusivos["solo_focal"]
    # Productores que usan ARBIZA pero no CALIRAL: Gamma, Epsilon, Eta
    assert "PRODUCTOR GAMMA" in exclusivos["solo_competidor"]


# ----------------------------------------------------------------------
# ComparadorEmpresasService
# ----------------------------------------------------------------------


def test_comparador_caliral_vs_arbiza_calcula_kg_compartidos(database_path: Path) -> None:
    service = ComparadorEmpresasService(database_path)
    comparativo = service.comparar("CALIRAL", "ARBIZA")
    assert comparativo.empresa_izquierda == "CALIRAL"
    assert comparativo.empresa_derecha == "ARBIZA"
    assert comparativo.kg_izquierda > 0
    assert comparativo.kg_derecha > 0
    # CALIRAL y ARBIZA son certificadores: no co-aparecen en el mismo
    # movimiento, por lo que kg_compartidos puede ser 0. Lo importante es
    # que el comparador calcula correctamente el solapamiento estructural.
    assert comparativo.productores_compartidos >= 3
    assert comparativo.mercados_compartidos >= 1
    assert 0 <= comparativo.indice_solapamiento <= 100


def test_comparador_caliral_vs_san_jacinto_tiene_kg_compartidos(database_path: Path) -> None:
    """Cuando una empresa es productor y la otra certificador, sí hay kg compartidos."""
    service = ComparadorEmpresasService(database_path)
    comparativo = service.comparar("CALIRAL", "SAN JACINTO")
    assert comparativo.kg_compartidos > 0  # SAN JACINTO usa CALIRAL como certificador


def test_comparador_caliral_vs_frigorifico_tacuarembo_funciona(database_path: Path) -> None:
    service = ComparadorEmpresasService(database_path)
    comparativo = service.comparar("CALIRAL", "FRIGORIFICO TACUAREMBO")
    assert comparativo.empresa_derecha == "FRIGORIFICO TACUAREMBO"


def test_comparador_porcentaje_compartido_esta_en_rango(database_path: Path) -> None:
    service = ComparadorEmpresasService(database_path)
    pct = service.porcentaje_compartido("CALIRAL", "ARBIZA")
    assert 0 <= pct["pct_sobre_izquierda"] <= 100
    assert 0 <= pct["pct_sobre_derecha"] <= 100
    assert 0 <= pct["pct_sobre_conjunto"] <= 100


def test_comparador_misma_empresa_raises(database_path: Path) -> None:
    service = ComparadorEmpresasService(database_path)
    with pytest.raises(ValueError):
        service.comparar("CALIRAL", "CALIRAL")


def test_comparador_empresa_inexistente_raises(database_path: Path) -> None:
    service = ComparadorEmpresasService(database_path)
    with pytest.raises(ValueError):
        service.comparar("CALIRAL", "Empresa Inexistente")


# ----------------------------------------------------------------------
# RadarComercialService
# ----------------------------------------------------------------------


def test_radar_escanea_empresa_focal_sin_error(database_path: Path) -> None:
    service = RadarComercialService(database_path)
    cambios = service.escanear("CALIRAL")
    assert isinstance(cambios, list)
    # En el fixture las fechas son 2025-01 a 2025-03; el radar con período
    # default de 90 días puede no detectar cambios. Lo importante es que no
    # falle y devuelva una lista tipada.
    for c in cambios:
        assert c.empresa_focal == "CALIRAL"
        assert c.severidad in ("alta", "media", "info")


def test_radar_funciona_con_empresa_no_focal(database_path: Path) -> None:
    service = RadarComercialService(database_path)
    cambios = service.escanear("ARBIZA")
    assert isinstance(cambios, list)


# ----------------------------------------------------------------------
# OportunidadesService
# ----------------------------------------------------------------------


def test_oportunidades_nunca_usaron_focal(database_path: Path) -> None:
    service = OportunidadesService(database_path)
    oportunidades = service.productores_nunca_usaron_focal("CALIRAL")
    entidades = {o.entidad for o in oportunidades}
    # Gamma, Epsilon, Eta nunca usaron CALIRAL
    assert "PRODUCTOR GAMMA" in entidades
    assert "PRODUCTOR EPSILON" in entidades
    assert "PRODUCTOR ETA" in entidades
    # Alfa, Beta, Delta, Zeta, San Jacinto sí usaron CALIRAL
    assert "PRODUCTOR ALFA" not in entidades


def test_oportunidades_multi_deposito(database_path: Path) -> None:
    service = OportunidadesService(database_path)
    oportunidades = service.productores_multi_deposito("CALIRAL")
    entidades = {o.entidad for o in oportunidades}
    # San Jacinto usa Deposito CALIRAL y Deposito ARBIZA
    assert "SAN JACINTO" in entidades


def test_oportunidades_ranking_esta_ordenado_por_score(database_path: Path) -> None:
    service = OportunidadesService(database_path)
    ranking = service.ranking("CALIRAL", limite=10)
    scores = [o.score for o in ranking]
    assert scores == sorted(scores, reverse=True)


# ----------------------------------------------------------------------
# AlertasService
# ----------------------------------------------------------------------


def test_alertas_dependencia_cliente(database_path: Path) -> None:
    service = AlertasService(database_path)
    alertas = service.dependencia_cliente("CALIRAL")
    assert isinstance(alertas, list)
    # CALIRAL concentra movimientos en Puerto Montevideo y Deposito CALIRAL
    assert any(a.tipo == "DEPENDENCIA_CLIENTE" for a in alertas) or len(alertas) == 0


def test_alertas_escanear_devuelve_lista_tipada(database_path: Path) -> None:
    service = AlertasService(database_path)
    alertas = service.escanear("CALIRAL")
    assert isinstance(alertas, list)
    for a in alertas:
        assert a.empresa_focal == "CALIRAL"
        assert a.severidad in ("alta", "media", "info")


# ----------------------------------------------------------------------
# IndicadoresService
# ----------------------------------------------------------------------


def test_indices_calcula_5_indices_en_rango(database_path: Path) -> None:
    service = IndicadoresService(database_path)
    indices = service.calcular("CALIRAL")
    assert indices.empresa == "CALIRAL"
    for valor in [
        indices.indice_diversificacion,
        indices.indice_fidelidad,
        indices.indice_competencia,
        indices.indice_riesgo,
        indices.indice_oportunidad,
        indices.indice_general,
    ]:
        assert 0 <= valor <= 100


def test_indices_empresa_inexistente_raises(database_path: Path) -> None:
    service = IndicadoresService(database_path)
    with pytest.raises(ValueError):
        service.calcular("Empresa Inexistente")


# ----------------------------------------------------------------------
# ConsultasComercialesService
# ----------------------------------------------------------------------


def test_consultas_exporto_san_jacinto_sin_caliral(database_path: Path) -> None:
    service = ConsultasComercialesService(database_path)
    respuesta = service.preguntar("¿Cuánto exportó SAN JACINTO sin pasar por CALIRAL?")
    assert "SAN JACINTO" in respuesta.respuesta
    assert respuesta.datos  # Debe haber al menos un movimiento (con ARBIZA)


def test_consultas_porcentaje_san_jacinto_pasa_por_caliral(database_path: Path) -> None:
    service = ConsultasComercialesService(database_path)
    respuesta = service.preguntar("¿Qué porcentaje de SAN JACINTO pasa por CALIRAL?")
    assert "%" in respuesta.respuesta or "porcentaje" in respuesta.respuesta.lower()
    assert respuesta.datos
    assert "pct_sobre_total" in respuesta.datos[0]


def test_consultas_top_20_productores_para_caliral(database_path: Path) -> None:
    service = ConsultasComercialesService(database_path)
    respuesta = service.preguntar("¿Cuáles son los 20 productores más importantes para CALIRAL?")
    assert "productores" in respuesta.respuesta.lower()
    assert respuesta.datos
    assert "productor" in respuesta.datos[0]
    assert "kg" in respuesta.datos[0]


def test_consultas_productores_comparten_caliral_arbiza(database_path: Path) -> None:
    service = ConsultasComercialesService(database_path)
    respuesta = service.preguntar("¿Qué productores comparten CALIRAL y ARBIZA?")
    assert "comparten" in respuesta.respuesta.lower()
    entidades = {d["productor"] for d in respuesta.datos}
    assert "PRODUCTOR ALFA" in entidades
    assert "PRODUCTOR BETA" in entidades
    assert "SAN JACINTO" in entidades


def test_consultas_productores_podria_captar_caliral(database_path: Path) -> None:
    service = ConsultasComercialesService(database_path)
    respuesta = service.preguntar("¿Qué productores podría captar CALIRAL?")
    assert "oportunidades" in respuesta.respuesta.lower()
    # Debe incluir a los productores que nunca usaron CALIRAL
    tipos = {d["tipo"] for d in respuesta.datos}
    assert "NUNCA_USARON_FOCAL" in tipos


def test_consultas_pregunta_no_reconocida_devuelve_mensaje(database_path: Path) -> None:
    service = ConsultasComercialesService(database_path)
    respuesta = service.preguntar("¿Cuál es el sentido de la vida?")
    assert "no reconocida" in respuesta.respuesta.lower()


# ----------------------------------------------------------------------
# CompetitiveIntelligenceEngine (orquestador)
# ----------------------------------------------------------------------


def test_engine_ejecuta_motor_completo(database_path: Path) -> None:
    engine = CompetitiveIntelligenceEngine(database_path)
    resultado = engine.ejecutar("CALIRAL", persistir=False)
    assert resultado.empresa_focal == "CALIRAL"
    assert resultado.resumen.total_competidores > 0
    assert resultado.resumen.indice_general > 0
    assert 0 <= resultado.indices.indice_general <= 100
    assert len(resultado.comparativos) <= 3  # Top 3 por defecto


def test_engine_persiste_en_tablas_ci(database_path: Path) -> None:
    import sqlite3
    engine = CompetitiveIntelligenceEngine(database_path)
    engine.ejecutar("CALIRAL", persistir=True)
    with sqlite3.connect(database_path) as conn:
        for tabla in ["ci_competencia", "ci_radar", "ci_oportunidades",
                       "ci_alertas", "ci_indices", "ci_comparador"]:
            n = conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
            # Tablas creadas (pueden tener 0 filas en algunos casos)
            assert n >= 0
        # Al menos competencia e indices deben tener datos
        assert conn.execute("SELECT COUNT(*) FROM ci_competencia").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM ci_indices").fetchone()[0] > 0


def test_engine_funciona_con_otra_empresa_focal(database_path: Path) -> None:
    """El motor NO debe tener lógica específica para CALIRAL."""
    engine = CompetitiveIntelligenceEngine(database_path)
    resultado = engine.ejecutar("ARBIZA", persistir=False)
    assert resultado.empresa_focal == "ARBIZA"
    assert resultado.resumen.total_competidores > 0
