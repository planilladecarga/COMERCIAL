# FRIMARAL BI

Este repositorio contiene el desarrollo progresivo del proyecto **FRIMARAL BI**.
Cada sprint añade un motor nuevo sobre la base SQLite normalizada del MGAP.

## Sprints

| Sprint | Motor | Descripción |
|--------|-------|-------------|
| 1 | Importador MGAP | Lectura no destructiva del XLSB / CSV del MGAP. |
| 2 | Libro Maestro BI | Generación del XLSX profesional con tablas estructuradas. |
| 3 | Base SQLite normalizada | Modelo estrella con empresas, países, productos, cortes, calendario y movimientos. |
| 4 | Empresa360 | Ficha integral reutilizable para cualquier empresa. |
| 5 | **Motor de Inteligencia Competitiva** | Detección automática de oportunidades, riesgos y ventajas competitivas. |

## Sprint 5 — Motor de Inteligencia Competitiva

Construye el módulo `COMPETITIVE_INTELLIGENCE_ENGINE` que analiza toda la base
SQLite y descubre relaciones comerciales automáticamente. No utiliza reglas
manuales: todo se calcula a partir de los movimientos.

### Servicios incluidos

- `CompetenciaService` — detecta productores, mercados, clientes y productos
  compartidos y exclusivos entre la empresa focal y cualquier otra.
- `ComparadorEmpresasService` — compara dos empresas cualesquiera (CALIRAL vs
  ARBIZA, CALIRAL vs FRIGORIFICO TACUAREMBO, etc.) devolviendo kg compartidos,
  %, mercados compartidos y un índice de solapamiento.
- `RadarComercialService` — detecta nuevos/perdidos y caídas/crecimientos en
  períodos configurables (default: últimos 90 días vs 90 días anteriores).
- `OportunidadesService` — genera un ranking de oportunidades: productores que
  nunca usaron la empresa focal, multi-depósito, mercados sin focal, etc.
- `AlertasService` — detecta riesgos: dependencia de cliente, caída de
  participación, concentración de mercados, clientes inactivos.
- `IndicadoresService` — calcula 5 índices en escala 0-100: Diversificación,
  Fidelidad, Competencia, Riesgo, Oportunidad.
- `ConsultasComercialesService` — responde preguntas comerciales en lenguaje
  natural (¿Cuánto exportó SAN JACINTO sin pasar por CALIRAL?, etc.).
- `CompetitiveIntelligenceEngine` — orquestador que ejecuta todos los
  servicios y persiste resultados en tablas `ci_*` de SQLite.

### Uso

```bash
# 1) Importar MGAP a SQLite (si no se hizo)
python scripts/import_mgap.py

# 2) Ejecutar motor CI
python scripts/run_ci_engine.py --empresa CALIRAL --consultas

# 3) Regenerar Libro Maestro (incluye hojas CI)
python scripts/build_master_workbook.py
```

### Tablas SQLite `ci_*`

El motor materializa sus resultados para que el workbook y los dashboards
las lean con un simple `SELECT *`:

- `ci_competencia` — comparativos focal vs cada competidor.
- `ci_radar` — cambios detectados en el período actual vs anterior.
- `ci_oportunidades` — ranking de oportunidades con score.
- `ci_alertas` — alertas activas con severidad.
- `ci_indices` — los 5 índices + índice general por empresa.
- `ci_comparador` — historial de comparativos entre dos empresas.

### Hojas nuevas del Libro Maestro

Las hojas `40_CI_Competencia`, `41_CI_Radar`, `42_CI_Oportunidades`,
`43_CI_Alertas`, `44_CI_Comparador` y `45_CI_Indices` se añaden
automáticamente al workbook con los datos de la última ejecución CI.

### Tests

```bash
python -m pytest
```

Cobertura:

- Tests unitarios por servicio (competencia, comparador, radar,
  oportunidades, alertas, índices, consultas).
- Test de integración end-to-end: pipeline → Empresa360 → CI Engine → workbook.
- Tests del comparador genérico: CALIRAL vs ARBIZA, CALIRAL vs
  FRIGORIFICO TACUAREMBO, CALIRAL vs SAN JACINTO, empresa inexistente.

## Generar el libro maestro

```bash
python scripts/build_master_workbook.py
```

El comando crea localmente el archivo de Excel generado, que no se versiona
en Git para evitar archivos binarios en los pull requests:

```text
output/FRIMARAL_BI_Libro_Maestro.xlsx
```

## Alcance actual

- Estructura completa de hojas solicitadas (incluye Sprint 5 CI).
- Hoja `00_Inicio` con navegación interna.
- Formato profesional y consistente.
- Tablas estructuradas de Excel preparadas para crecer.
- Motor CI con detección automática de oportunidades y riesgos.
- Persistencia en tablas `ci_*` para dashboards.

## Fuera de alcance en esta etapa

- No se desarrolla la aplicación web.
- No se crean tablas dinámicas.
- No se crean gráficos.
