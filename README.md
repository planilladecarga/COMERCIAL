# FRIMARAL BI

Este repositorio contiene el punto de partida del proyecto **FRIMARAL BI**.

## Sprint 1: estructura base

El primer sprint dejó preparada la estructura inicial y el concepto del **Libro Maestro de Business Intelligence** como referencia oficial para validar la futura aplicación.

## Sprint 2: motor de importación MGAP

El segundo sprint incorporó un motor de datos modular para ejecutar el flujo:

```text
Archivo XLSB → Lectura → Validación → Normalización → Catálogos → Base SQLite
```

El archivo original del MGAP nunca se modifica. El motor genera una copia normalizada, una base SQLite en modelo estrella y un reporte de importación.

```bash
python scripts/import_mgap.py ruta/al/archivo_mgap.xlsb
```

Para pruebas técnicas también se acepta CSV:

```bash
python scripts/import_mgap.py tests/fixtures/mgap_sample.csv
```

## Sprint 3: Libro Maestro BI desde SQLite

El tercer sprint genera automáticamente `FRIMARAL_BI_Libro_Maestro.xlsx` usando únicamente la base SQLite normalizada del Sprint 2. No vuelve a leer el XLSB.

```bash
python scripts/build_master_workbook.py --db output/frimaral_bi.db --output output/FRIMARAL_BI_Libro_Maestro.xlsx
```

El libro incluye:

- `00_Inicio` con fecha de actualización, movimientos, empresas, productores, depósitos, certificadores, países, productos y versión.
- `01_KPIs` con kg totales, movimientos, exportaciones, movimientos a depósitos y conteos de dimensiones.
- Catálogos generados desde SQLite: empresas, productores, depósitos, certificadores, mercados, productos, cortes y calendario.
- Diccionario técnico generado desde el esquema SQLite.
- Reglas de negocio aplicadas o preparadas.
- Hojas TD con tablas analíticas estructuradas y no vacías para validar consultas comerciales.
- Hojas de dashboard reservadas, no interactivas y sin gráficos.

## Sprint 4: Motor de Inteligencia Comercial Empresa360

El cuarto sprint incorpora `Empresa360`, un motor reusable para construir una ficha inteligente de cualquier empresa usando exclusivamente SQLite. No existe una pantalla especial para CALIRAL: la misma lógica sirve para CALIRAL, SAN JACINTO, ARBIZA, PUL, BREEDERS, BPU, FRIGORIFICO TACUAREMBO o cualquier empresa detectada.

La ficha incluye información general, roles simultáneos, indicadores, productores relacionados, certificadores relacionados, depósitos utilizados, mercados, productos, cortes, evolución mensual, participación, competidores, clientes, alertas y movimientos con trazabilidad al `id_movimiento`.

Ejemplo técnico:

```python
from pathlib import Path
from frimaral_bi.empresa360 import Empresa360

ficha = Empresa360(Path("output/frimaral_bi.db")).construir("CALIRAL")
print(ficha.indicadores)
```

## Arquitectura

- `frimaral_bi.importador`: lectura no destructiva, detección de hoja, columnas, filas y tiempos.
- `frimaral_bi.validador`: columnas obligatorias, nulos, fechas inválidas, pesos negativos y duplicados.
- `frimaral_bi.normalizador`: limpieza de texto, mayúsculas, caracteres invisibles, país y `solo_deposito`.
- `frimaral_bi.catalogos`: dimensiones de empresas, países, productos, cortes y calendario.
- `frimaral_bi.database`: persistencia SQLite con modelo estrella.
- `frimaral_bi.workbook`: generación profesional del Libro Maestro BI desde SQLite.
- `frimaral_bi.repositories`: repositorios SQLite reutilizables para consultas comerciales.
- `frimaral_bi.empresa360`: motor genérico de inteligencia comercial para cualquier empresa.
- `frimaral_bi.reporter`: log automático de importación, errores, advertencias y nuevos catálogos.

## Salidas generadas localmente

Los artefactos en `output/` no se versionan para evitar binarios en los pull requests:

```text
output/frimaral_bi.db
output/mgap_normalizado.csv
output/importacion_mgap_log.md
output/FRIMARAL_BI_Libro_Maestro.xlsx
```

## Fuera de alcance en esta etapa

- No se desarrolla la aplicación web.
- No se desarrollan dashboards interactivos.
- No se crean gráficos.
- No se vuelve a leer el XLSB para construir el Libro Maestro.
- No se crea una pantalla especial por empresa: `Empresa360` es genérico.
