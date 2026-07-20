# FRIMARAL BI

Este repositorio contiene el punto de partida del proyecto **FRIMARAL BI**.

El entregable inicial es el **Libro Maestro de Business Intelligence**, una plantilla profesional de Excel que servirá como referencia oficial para validar la futura aplicación. La plantilla está preparada para recibir el archivo XLSB del MGAP con movimientos desde el 01/01/2025, normalizar datos, documentar reglas de negocio y escalar hacia dashboards, análisis 360 y radar comercial.

## Sprint 1: Libro Maestro BI

```bash
python scripts/build_master_workbook.py
```

El comando crea localmente el archivo de Excel generado, que no se versiona en Git para evitar archivos binarios en los pull requests:

```text
output/FRIMARAL_BI_Libro_Maestro.xlsx
```

## Sprint 2: Motor de importación MGAP

El segundo sprint incorpora un motor de datos modular para ejecutar el flujo:

```text
Archivo XLSB → Lectura → Validación → Normalización → Catálogos → Base SQLite → Libro Maestro BI → FRIMARAL BI
```

El archivo original del MGAP nunca se modifica. El motor genera una copia normalizada, una base SQLite en modelo estrella y un reporte de importación.

### Ejecutar importación

```bash
python scripts/import_mgap.py ruta/al/archivo_mgap.xlsb
```

Para pruebas técnicas también se acepta CSV:

```bash
python scripts/import_mgap.py tests/fixtures/mgap_sample.csv
```

### Salidas generadas localmente

```text
output/frimaral_bi.db
output/mgap_normalizado.csv
output/importacion_mgap_log.md
```

## Arquitectura

- `frimaral_bi.importador`: lectura no destructiva, detección de hoja, columnas, filas y tiempos.
- `frimaral_bi.validador`: columnas obligatorias, nulos, fechas inválidas, pesos negativos y duplicados.
- `frimaral_bi.normalizador`: limpieza de texto, mayúsculas, caracteres invisibles, país y `solo_deposito`.
- `frimaral_bi.catalogos`: dimensiones de empresas, países, productos, cortes y calendario.
- `frimaral_bi.database`: persistencia SQLite con modelo estrella.
- `frimaral_bi.reporter`: log automático de importación, errores, advertencias y nuevos catálogos.

## Fuera de alcance en esta etapa

- No se desarrolla la aplicación.
- No se crean dashboards.
- No se crean gráficos.
- No se crean tablas dinámicas.
