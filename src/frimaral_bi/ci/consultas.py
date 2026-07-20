"""ConsultasComercialesService — responde preguntas comerciales en
lenguaje natural del enunciado del Sprint 5.

Las preguntas se matchean por keywords (case-insensitive). Si no hay
match, devuelve una respuesta indicando que la pregunta no está soportada.
Cada respuesta incluye los datos tabulares subyacentes.
"""
from __future__ import annotations

from pathlib import Path

from ..repositories import BIRepository
from .comparador import ComparadorEmpresasService
from .competencia import CompetenciaService
from .models import RespuestaComercial
from .oportunidades import OportunidadesService


class ConsultasComercialesService:
    """Responde consultas comerciales frecuentes con datos calculados."""

    def __init__(self, database_path: Path) -> None:
        self.repository = BIRepository(database_path)
        self.comparador = ComparadorEmpresasService(database_path)
        self.competencia = CompetenciaService(database_path)
        self.oportunidades = OportunidadesService(database_path)

    def preguntar(self, pregunta: str, empresa_focal: str = "CALIRAL") -> RespuestaComercial:
        """Interpreta una pregunta en lenguaje natural y devuelve la respuesta."""
        p = pregunta.upper()

        if "SIN PASAR POR" in p or "SIN CALIRAL" in p:
            return self._exporto_sin_pasar_por(pregunta, empresa_focal)

        if "PORCENTAJE" in p and "PASA POR" in p:
            return self._porcentaje_pasa_por(pregunta, empresa_focal)

        if "PORCENTAJE" in p and ("UTILIZA" in p or "USA" in p):
            return self._porcentaje_utiliza(pregunta, empresa_focal)

        if "20 PRODUCTORES" in p or "PRODUCTORES MAS IMPORTANTES" in p or "TOP" in p:
            return self._top_productores(pregunta, empresa_focal)

        if "COMPARTEN" in p and "Y" in p:
            return self._productores_comparten(pregunta, empresa_focal)

        if "PODRIA CAPTAR" in p or "CAPTAR" in p:
            return self._productores_captar(pregunta, empresa_focal)

        if "NUNCA UTILIZARON" in p or "NUNCA USARON" in p:
            return self._nunca_utilizaron(pregunta, empresa_focal)

        if "MERCADOS" in p and "COMPETENCIA" in p:
            return self._mercados_competencia(pregunta, empresa_focal)

        if "CERTIFICADORES" in p and "COMPETENCIA" in p:
            return self._certificadores_competencia(pregunta, empresa_focal)

        return RespuestaComercial(
            pregunta=pregunta,
            respuesta="Pregunta no reconocida. Consulte el catálogo de preguntas soportadas.",
            datos=[],
        )

    # ------------------- consultas específicas -------------------

    def _exporto_sin_pasar_por(self, pregunta: str, empresa_focal: str) -> RespuestaComercial:
        """¿Cuánto exportó X sin pasar por CALIRAL?"""
        empresa_analizada = self._extraer_empresa_analizada(pregunta, empresa_focal)
        if not empresa_analizada:
            return RespuestaComercial(pregunta, "No se pudo identificar la empresa a analizar.", [])
        eid = self._require_company(empresa_analizada)
        focal_id = self._require_company(empresa_focal)
        # Movimientos de empresa_analizada donde NO participa la empresa focal
        rows = self.repository.fetch_all(
            f"""
                SELECT m.fecha, prod.nombre AS productor, cert.nombre AS certificador,
                       dest.nombre AS deposito, pais.nombre_pais AS mercado,
                       producto.nombre_producto AS producto, m.peso, m.solo_deposito
                {self.repository.DIMENSION_JOINS}
                WHERE (m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?)
                  AND NOT (m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?)
                ORDER BY m.fecha DESC
            """,
            (eid, eid, eid, focal_id, focal_id, focal_id),
        )
        total_kg = sum(float(r.get("peso") or 0) for r in rows)
        return RespuestaComercial(
            pregunta=pregunta,
            respuesta=f"{empresa_analizada} exportó {round(total_kg, 2)} kg sin pasar por {empresa_focal}.",
            datos=rows,
        )

    def _porcentaje_pasa_por(self, pregunta: str, empresa_focal: str) -> RespuestaComercial:
        """¿Qué porcentaje de X pasa por CALIRAL?"""
        empresa_analizada = self._extraer_empresa_analizada(pregunta, empresa_focal)
        if not empresa_analizada:
            return RespuestaComercial(pregunta, "No se pudo identificar la empresa a analizar.", [])
        comparativo = self.comparador.comparar(empresa_analizada, empresa_focal)
        pct = self.comparador.porcentaje_compartido(empresa_analizada, empresa_focal)
        return RespuestaComercial(
            pregunta=pregunta,
            respuesta=(
                f"{empresa_analizada}: {round(comparativo.kg_compartidos, 2)} kg "
                f"({pct['pct_sobre_izquierda']}%) pasan por {empresa_focal}."
            ),
            datos=[{
                "empresa_analizada": empresa_analizada,
                "empresa_focal": empresa_focal,
                "kg_compartidos": comparativo.kg_compartidos,
                "kg_totales": comparativo.kg_izquierda,
                "pct_sobre_total": pct["pct_sobre_izquierda"],
            }],
        )

    def _porcentaje_utiliza(self, pregunta: str, empresa_focal: str) -> RespuestaComercial:
        """¿Qué porcentaje utiliza ARBIZA? (u otra empresa nombrada)"""
        empresa_analizada = self._extraer_empresa_analizada(pregunta, empresa_focal)
        if not empresa_analizada:
            return RespuestaComercial(pregunta, "No se pudo identificar la empresa a analizar.", [])
        otra = self._extraer_otra_empresa(pregunta, exclude=empresa_focal)
        if not otra:
            return RespuestaComercial(pregunta, "No se pudo identificar la empresa a comparar.", [])
        comparativo = self.comparador.comparar(empresa_analizada, otra)
        pct = self.comparador.porcentaje_compartido(empresa_analizada, otra)
        return RespuestaComercial(
            pregunta=pregunta,
            respuesta=(
                f"{empresa_analizada}: {round(comparativo.kg_compartidos, 2)} kg "
                f"({pct['pct_sobre_izquierda']}%) utilizan {otra}."
            ),
            datos=[{
                "empresa_analizada": empresa_analizada,
                "empresa_comparada": otra,
                "kg_compartidos": comparativo.kg_compartidos,
                "kg_totales": comparativo.kg_izquierda,
                "pct_sobre_total": pct["pct_sobre_izquierda"],
            }],
        )

    def _top_productores(self, pregunta: str, empresa_focal: str) -> RespuestaComercial:
        """¿Cuáles son los 20 productores más importantes para CALIRAL?"""
        company_id = self._require_company(empresa_focal)
        rows = self.repository.fetch_all(
            f"""
                SELECT prod.nombre AS productor,
                       COALESCE(SUM(m.peso), 0) AS kg,
                       COUNT(*) AS movimientos,
                       MIN(m.fecha) AS primera_fecha,
                       MAX(m.fecha) AS ultima_fecha
                {self.repository.DIMENSION_JOINS}
                WHERE (m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?)
                  AND prod.nombre IS NOT NULL
                GROUP BY prod.nombre
                ORDER BY kg DESC
                LIMIT 20
            """,
            (company_id, company_id, company_id),
        )
        return RespuestaComercial(
            pregunta=pregunta,
            respuesta=f"Top {len(rows)} productores para {empresa_focal} por kg.",
            datos=rows,
        )

    def _productores_comparten(self, pregunta: str, empresa_focal: str) -> RespuestaComercial:
        """¿Qué productores comparten CALIRAL y ARBIZA?"""
        otra = self._extraer_otra_empresa(pregunta, exclude=empresa_focal)
        if not otra:
            return RespuestaComercial(pregunta, "No se pudo identificar la segunda empresa.", [])
        compartidos = self.competencia.productores_compartidos(empresa_focal, otra)
        return RespuestaComercial(
            pregunta=pregunta,
            respuesta=f"{len(compartidos)} productores comparten {empresa_focal} y {otra}.",
            datos=[{"productor": p} for p in compartidos],
        )

    def _productores_captar(self, pregunta: str, empresa_focal: str) -> RespuestaComercial:
        """¿Qué productores podría captar CALIRAL?"""
        oportunidades = self.oportunidades.ranking(empresa_focal, limite=50)
        captables = [o for o in oportunidades if o.tipo in ("NUNCA_USARON_FOCAL", "USA_COMPETIDOR", "MULTI_DEPOSITO")]
        return RespuestaComercial(
            pregunta=pregunta,
            respuesta=f"{len(captables)} oportunidades de captación para {empresa_focal}.",
            datos=[o.to_row() for o in captables],
        )

    def _nunca_utilizaron(self, pregunta: str, empresa_focal: str) -> RespuestaComercial:
        """¿Qué productores nunca utilizaron CALIRAL?"""
        oportunidades = self.oportunidades.productores_nunca_usaron_focal(empresa_focal)
        return RespuestaComercial(
            pregunta=pregunta,
            respuesta=f"{len(oportunidades)} productores nunca utilizaron {empresa_focal}.",
            datos=[o.to_row() for o in oportunidades],
        )

    def _mercados_competencia(self, pregunta: str, empresa_focal: str) -> RespuestaComercial:
        """¿Qué mercados trabaja la competencia donde CALIRAL no participa?"""
        focal_id = self._require_company(empresa_focal)
        focal_mercados = self.repository.company_dimension_set(focal_id, "mercado")
        rows = self.repository.fetch_all(
            f"""
                SELECT DISTINCT pais.nombre_pais AS mercado,
                       COUNT(DISTINCT m.id_movimiento) AS movimientos_competencia
                {self.repository.DIMENSION_JOINS}
                WHERE (m.id_productor = ? OR m.id_certificador = ? OR m.id_destino = ?)
                GROUP BY pais.nombre_pais
                ORDER BY movimientos_competencia DESC
            """,
            (focal_id, focal_id, focal_id),
        )
        # Mercados donde la competencia participa pero la empresa focal NO
        externos = [r for r in rows if str(r.get("mercado", "")).upper() not in focal_mercados]
        return RespuestaComercial(
            pregunta=pregunta,
            respuesta=f"{len(externos)} mercados sin participación de {empresa_focal}.",
            datos=externos,
        )

    def _certificadores_competencia(self, pregunta: str, empresa_focal: str) -> RespuestaComercial:
        """¿Qué certificadores trabajan con la competencia?"""
        focal_id = self._require_company(empresa_focal)
        rows = self.repository.fetch_all(
            f"""
                SELECT DISTINCT cert.nombre AS certificador,
                       COUNT(DISTINCT m.id_movimiento) AS movimientos,
                       COALESCE(SUM(m.peso), 0) AS kg
                {self.repository.DIMENSION_JOINS}
                WHERE m.id_certificador IS NOT NULL
                  AND m.id_certificador <> ?
                GROUP BY cert.nombre
                ORDER BY kg DESC
            """,
            (focal_id,),
        )
        return RespuestaComercial(
            pregunta=pregunta,
            respuesta=f"{len(rows)} certificadores trabajando con competencia de {empresa_focal}.",
            datos=rows,
        )

    # ------------------- helpers internos -------------------

    def _extraer_empresa_analizada(self, pregunta: str, exclude: str) -> str | None:
        """Heurística simple: encuentra un nombre de empresa en la pregunta."""
        words = pregunta.upper().replace("?", "").split()
        for company in self.repository.all_companies():
            nombre = company["nombre"].upper()
            if nombre == exclude.upper():
                continue
            # Match por palabras clave del nombre
            nombre_words = nombre.split()
            if len(nombre_words) >= 2 and all(w in words for w in nombre_words):
                return company["nombre"]
            if len(nombre_words) == 1 and nombre in words:
                return company["nombre"]
        return None

    def _extraer_otra_empresa(self, pregunta: str, exclude: str) -> str | None:
        """Igual que _extraer_empresa_analizada pero busca un segundo match."""
        return self._extraer_empresa_analizada(pregunta, exclude)

    def _require_company(self, name: str) -> int:
        company = self.repository.company_by_name(name)
        if not company:
            raise ValueError(f"Empresa no encontrada en SQLite: {name}")
        return int(company["id_empresa"])
