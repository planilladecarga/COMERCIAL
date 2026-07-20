# FRIMARAL BI

Este repositorio contiene el punto de partida del proyecto **FRIMARAL BI**.

El entregable inicial es el **Libro Maestro de Business Intelligence**, una plantilla profesional de Excel que servirá como referencia oficial para validar la futura aplicación. La plantilla está preparada para recibir el archivo XLSB del MGAP con movimientos desde el 01/01/2025, normalizar datos, documentar reglas de negocio y escalar hacia dashboards, análisis 360 y radar comercial.

## Generar el libro maestro

```bash
python scripts/build_master_workbook.py
```

El comando crea localmente el archivo de Excel generado, que no se versiona en Git para evitar archivos binarios en los pull requests:

```text
output/FRIMARAL_BI_Libro_Maestro.xlsx
```

## Alcance actual

- Estructura completa de hojas solicitadas.
- Hoja `00_Inicio` con navegación interna.
- Formato profesional y consistente.
- Tablas estructuradas de Excel preparadas para crecer.
- Hojas reservadas para futuras tablas dinámicas y gráficos.

## Fuera de alcance en esta etapa

- No se desarrolla la aplicación.
- No se cargan datos reales del XLSB del MGAP.
- No se crean tablas dinámicas.
- No se crean gráficos.
