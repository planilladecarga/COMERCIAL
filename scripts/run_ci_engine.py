"""Ejecuta el Motor de Inteligencia Competitiva (Sprint 5) sobre la BD SQLite.

Uso:
    python scripts/run_ci_engine.py [--empresa CALIRAL] [--persistir] [--consultas]

Sin argumentos, ejecuta el motor completo sobre la BD por defecto
(output/frimaral_bi.db) usando CALIRAL como empresa focal y persistiendo
resultados en las tablas ci_*.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frimaral_bi.ci import CompetitiveIntelligenceEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Motor de Inteligencia Competitiva FRIMARAL BI.")
    parser.add_argument("--database", default="output/frimaral_bi.db", help="Ruta a la BD SQLite.")
    parser.add_argument("--empresa", default="CALIRAL", help="Empresa focal para el análisis.")
    parser.add_argument("--no-persistir", action="store_true", help="No escribir en tablas ci_*.")
    parser.add_argument("--consultas", action="store_true", help="Ejecutar consultas comerciales demo.")
    args = parser.parse_args()

    database_path = Path(args.database)
    if not database_path.exists():
        print(f"ERROR: No existe la base de datos: {database_path}")
        print("Ejecute primero `python scripts/import_mgap.py` para crearla.")
        return 1

    engine = CompetitiveIntelligenceEngine(database_path)
    resultado = engine.ejecutar(args.empresa, persistir=not args.no_persistir)

    print("=" * 70)
    print(f"Motor de Inteligencia Competitiva — {resultado.empresa_focal}")
    print("=" * 70)
    print(f"Competidores detectados:     {resultado.resumen.total_competidores}")
    print(f"Cambios de radar:            {resultado.resumen.total_cambios_radar}")
    print(f"Oportunidades:               {resultado.resumen.total_oportunidades}")
    print(f"Alertas activas:             {resultado.resumen.total_alertas}")
    print(f"Índice general CI:           {resultado.resumen.indice_general}")
    print()
    print("Top 5 competidores:")
    for c in resultado.competencia[:5]:
        print(f"  - {c.competidor:30s} similitud={c.indice_similitud:6.2f}  "
              f"kg_comp={c.kg_compartidos:>12.2f}  "
              f"prod_comp={c.productores_compartidos}")
    print()
    print("Top 5 oportunidades:")
    for o in resultado.oportunidades[:5]:
        print(f"  - [{o.tipo:20s}] {o.entidad:25s} score={o.score:6.2f}  kg={o.kg_potenciales:>12.2f}")
    print()
    print("Alertas activas:")
    for a in resultado.alertas[:10]:
        sev_pad = (a.severidad + "      ")[:6]
        tipo_pad = (a.tipo + "                         ")[:25]
        entidad_pad = (a.entidad + "                              ")[:30]
        print(f"  - [{sev_pad}] {tipo_pad} {entidad_pad} {a.detalle}")
    print()
    print(f"Índices: diversificación={resultado.indices.indice_diversificacion} "
          f"fidelidad={resultado.indices.indice_fidelidad} "
          f"competencia={resultado.indices.indice_competencia} "
          f"riesgo={resultado.indices.indice_riesgo} "
          f"oportunidad={resultado.indices.indice_oportunidad}")

    if args.consultas:
        print()
        print("=" * 70)
        print("Consultas comerciales demo")
        print("=" * 70)
        for pregunta in [
            "¿Cuánto exportó SAN JACINTO sin pasar por CALIRAL?",
            "¿Qué porcentaje de SAN JACINTO pasa por CALIRAL?",
            "¿Cuáles son los 20 productores más importantes para CALIRAL?",
            "¿Qué productores comparten CALIRAL y ARBIZA?",
            "¿Qué productores podría captar CALIRAL?",
        ]:
            r = engine.consultar(pregunta, args.empresa)
            print(f"\n• {pregunta}")
            print(f"  → {r.respuesta}")

    if not args.no_persistir:
        print()
        print("Resultados persistidos en tablas ci_* de la base SQLite.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
