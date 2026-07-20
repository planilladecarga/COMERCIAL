"""Generación del Libro Maestro BI desde la base SQLite normalizada."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape

from .ci.engine import CompetitiveIntelligenceEngine
from .models import Row

MASTER_WORKBOOK_SHEETS = [
    "00_Inicio", "01_KPIs", "02_Diccionario_MGAP", "03_Reglas_Negocio",
    "04_Empresas", "05_Productores", "06_Depositos", "07_Certificadores",
    "08_Mercados", "09_Productos", "10_Cortes", "11_Calendario",
    "12_Catalogo_Consultas", "20_TD_Depositos", "21_TD_Productores",
    "22_TD_Certificadores", "23_TD_Mercados", "24_TD_Productos",
    "25_TD_CALIRAL", "26_TD_SAN_JACINTO", "27_TD_COMPETENCIA",
    "30_Dashboard_Ejecutivo", "31_Dashboard_CALIRAL", "32_Dashboard_SAN_JACINTO",
    "33_Dashboard_COMPETENCIA",
    "40_CI_Competencia", "41_CI_Radar", "42_CI_Oportunidades",
    "43_CI_Alertas", "44_CI_Comparador", "45_CI_Indices",
]

VERSION = "4.0.0"


def column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


@dataclass(frozen=True)
class SheetPayload:
    name: str
    title: str
    purpose: str
    headers: list[str]
    rows: list[Row]


class SQLiteBIReader:
    """Consulta la base SQLite creada por el Sprint 2."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def build_payloads(self) -> list[SheetPayload]:
        if not self.database_path.exists():
            raise FileNotFoundError(f"No existe la base SQLite: {self.database_path}")
        with sqlite3.connect(self.database_path) as conn:
            conn.row_factory = sqlite3.Row
            return [self._payload_for(name, conn) for name in MASTER_WORKBOOK_SHEETS]

    def _payload_for(self, name: str, conn: sqlite3.Connection) -> SheetPayload:
        builders = {
            "00_Inicio": self._inicio, "01_KPIs": self._kpis,
            "02_Diccionario_MGAP": self._diccionario, "03_Reglas_Negocio": self._reglas,
            "04_Empresas": lambda c: self._table(c, "empresas"),
            "05_Productores": lambda c: self._empresas_por_rol(c, "es_productor"),
            "06_Depositos": lambda c: self._empresas_por_rol(c, "es_deposito"),
            "07_Certificadores": lambda c: self._empresas_por_rol(c, "es_certificador"),
            "08_Mercados": lambda c: self._table(c, "paises"),
            "09_Productos": lambda c: self._table(c, "productos"),
            "10_Cortes": lambda c: self._table(c, "cortes"),
            "11_Calendario": lambda c: self._table(c, "calendario"),
            "12_Catalogo_Consultas": self._catalogo_consultas,
            "20_TD_Depositos": lambda c: self._td(c, "TD-002", "Ranking Depósitos", "Ranking de depósitos por kilos y movimientos.", "destino"),
            "21_TD_Productores": lambda c: self._td(c, "TD-001", "Ranking Productores", "Ranking de productores por kilos y movimientos.", "productor"),
            "22_TD_Certificadores": lambda c: self._td(c, "TD-003", "Ranking Certificadores", "Ranking de certificadores por kilos y movimientos.", "certificador"),
            "23_TD_Mercados": lambda c: self._td(c, "TD-005", "Productor x Mercado", "Kilos y movimientos por productor y mercado.", "productor", "pais"),
            "24_TD_Productos": lambda c: self._td(c, "TD-008", "Depósito x Producto", "Kilos y movimientos por depósito y producto.", "destino", "producto"),
            "25_TD_CALIRAL": lambda c: self._td_filtered(c, "TD-009/010/011", "CALIRAL", "Análisis CALIRAL por productores, mercados y productos.", "certificador", "CALIRAL"),
            "26_TD_SAN_JACINTO": lambda c: self._td_filtered(c, "TD-012/013/014", "SAN JACINTO", "Análisis San Jacinto por depósitos y exportación CALIRAL.", "destino", "SAN JACINTO"),
            "27_TD_COMPETENCIA": self._competencia,
            "30_Dashboard_Ejecutivo": lambda c: self._placeholder_dashboard(c, "Ejecutivo"),
            "31_Dashboard_CALIRAL": lambda c: self._placeholder_dashboard(c, "CALIRAL"),
            "32_Dashboard_SAN_JACINTO": lambda c: self._placeholder_dashboard(c, "SAN JACINTO"),
            "33_Dashboard_COMPETENCIA": lambda c: self._placeholder_dashboard(c, "COMPETENCIA"),
            "40_CI_Competencia": lambda c: self._ci_table(c, "ci_competencia", "Competencia — empresas con solapamiento vs empresa focal.", self._last_ci()),
            "41_CI_Radar": lambda c: self._ci_table(c, "ci_radar", "Radar comercial — nuevos, perdidos, caídas y crecimientos.", self._last_ci()),
            "42_CI_Oportunidades": lambda c: self._ci_table(c, "ci_oportunidades", "Ranking de oportunidades comerciales detectadas.", self._last_ci()),
            "43_CI_Alertas": lambda c: self._ci_table(c, "ci_alertas", "Alertas de riesgo comercial detectadas.", self._last_ci()),
            "44_CI_Comparador": lambda c: self._ci_table(c, "ci_comparador", "Comparativos CALIRAL vs competidores principales.", self._last_ci()),
            "45_CI_Indices": lambda c: self._ci_table(c, "ci_indices", "Índices CI: Diversificación, Fidelidad, Competencia, Riesgo, Oportunidad.", self._last_ci()),
        }
        headers, rows, purpose = builders[name](conn)
        return SheetPayload(name, name.split("_", 1)[1], purpose, headers, rows)

    def _rows(self, conn: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()) -> list[Row]:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]

    def _count(self, conn: sqlite3.Connection, table: str, where: str = "1=1") -> int:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0])

    def _inicio(self, conn: sqlite3.Connection) -> tuple[list[str], list[Row], str]:
        generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        rows = [
            {"indicador": "Fecha de actualización", "valor": generated},
            {"indicador": "Cantidad de movimientos", "valor": self._count(conn, "movimientos")},
            {"indicador": "Cantidad de empresas", "valor": self._count(conn, "empresas")},
            {"indicador": "Cantidad de productores", "valor": self._count(conn, "empresas", "es_productor = 1")},
            {"indicador": "Cantidad de depósitos", "valor": self._count(conn, "empresas", "es_deposito = 1")},
            {"indicador": "Cantidad de certificadores", "valor": self._count(conn, "empresas", "es_certificador = 1")},
            {"indicador": "Cantidad de países", "valor": self._count(conn, "paises")},
            {"indicador": "Cantidad de productos", "valor": self._count(conn, "productos")},
            {"indicador": "Versión del Libro Maestro", "valor": VERSION},
        ]
        return ["indicador", "valor"], rows, "Portada técnica con métricas generales y navegación."

    def _kpis(self, conn: sqlite3.Connection) -> tuple[list[str], list[Row], str]:
        rows = [
            {"kpi": "Kg Totales", "valor": conn.execute("SELECT COALESCE(SUM(peso),0) FROM movimientos").fetchone()[0]},
            {"kpi": "Movimientos", "valor": self._count(conn, "movimientos")},
            {"kpi": "Exportaciones", "valor": self._count(conn, "movimientos", "solo_deposito = 0")},
            {"kpi": "Movimientos a Depósitos", "valor": self._count(conn, "movimientos", "solo_deposito = 1")},
            {"kpi": "Cantidad Empresas", "valor": self._count(conn, "empresas")},
            {"kpi": "Cantidad Productores", "valor": self._count(conn, "empresas", "es_productor = 1")},
            {"kpi": "Cantidad Depósitos", "valor": self._count(conn, "empresas", "es_deposito = 1")},
            {"kpi": "Cantidad Certificadores", "valor": self._count(conn, "empresas", "es_certificador = 1")},
            {"kpi": "Cantidad Mercados", "valor": self._count(conn, "paises")},
        ]
        return ["kpi", "valor"], rows, "Indicadores ejecutivos calculados automáticamente desde SQLite."

    def _table(self, conn: sqlite3.Connection, table: str) -> tuple[list[str], list[Row], str]:
        rows = self._rows(conn, f"SELECT * FROM {table}")
        headers = list(rows[0].keys()) if rows else ["sin_registros"]
        return headers, rows or [{"sin_registros": "Sin datos en SQLite"}], f"Catálogo `{table}` generado desde la base normalizada."

    def _empresas_por_rol(self, conn: sqlite3.Connection, role: str) -> tuple[list[str], list[Row], str]:
        rows = self._rows(conn, f"SELECT * FROM empresas WHERE {role} = 1 ORDER BY cantidad_movimientos DESC")
        headers = list(rows[0].keys()) if rows else ["sin_registros"]
        return headers, rows or [{"sin_registros": "Sin datos para el rol"}], f"Empresas filtradas por `{role}` desde SQLite."

    def _td(self, conn: sqlite3.Connection, code: str, question: str, purpose: str, *dimensions: str) -> tuple[list[str], list[Row], str]:
        aliases = {"productor": "prod.nombre", "certificador": "cert.nombre", "destino": "dest.nombre", "pais": "p.nombre_pais", "producto": "pr.nombre_producto"}
        select_dims = ", ".join(f"{aliases[d]} AS {d}" for d in dimensions)
        group_dims = ", ".join(aliases[d] for d in dimensions)
        sql = f"""
            SELECT '{code}' AS codigo, '{question}' AS pregunta_comercial,
                   'movimientos + dimensiones SQLite' AS origen_datos,
                   COUNT(*) AS registros_utilizados, DATE('now') AS fecha_generacion,
                   {select_dims}, SUM(m.peso) AS kg_totales, COUNT(*) AS movimientos
            FROM movimientos m
            LEFT JOIN empresas prod ON prod.id_empresa = m.id_productor
            LEFT JOIN empresas cert ON cert.id_empresa = m.id_certificador
            LEFT JOIN empresas dest ON dest.id_empresa = m.id_destino
            LEFT JOIN paises p ON p.id_pais = m.id_pais
            LEFT JOIN productos pr ON pr.id_producto = m.id_producto
            GROUP BY {group_dims}
            ORDER BY kg_totales DESC
        """
        rows = self._rows(conn, sql)
        headers = list(rows[0].keys()) if rows else ["codigo", "pregunta_comercial", "origen_datos", "registros_utilizados", "fecha_generacion"]
        return headers, rows or [{"codigo": code, "pregunta_comercial": question, "origen_datos": "movimientos + dimensiones SQLite", "registros_utilizados": 0, "fecha_generacion": datetime.now(UTC).date().isoformat()}], purpose

    def _td_filtered(self, conn: sqlite3.Connection, code: str, question: str, purpose: str, field: str, contains: str) -> tuple[list[str], list[Row], str]:
        column = "cert.nombre" if field == "certificador" else "dest.nombre"
        sql = f"""
            SELECT '{code}' AS codigo, '{question}' AS pregunta_comercial,
                   'movimientos + dimensiones SQLite' AS origen_datos,
                   COUNT(*) AS registros_utilizados, DATE('now') AS fecha_generacion,
                   prod.nombre AS productor, dest.nombre AS deposito, p.nombre_pais AS mercado,
                   pr.nombre_producto AS producto, SUM(m.peso) AS kg_totales, COUNT(*) AS movimientos
            FROM movimientos m
            LEFT JOIN empresas prod ON prod.id_empresa = m.id_productor
            LEFT JOIN empresas cert ON cert.id_empresa = m.id_certificador
            LEFT JOIN empresas dest ON dest.id_empresa = m.id_destino
            LEFT JOIN paises p ON p.id_pais = m.id_pais
            LEFT JOIN productos pr ON pr.id_producto = m.id_producto
            WHERE UPPER(COALESCE({column}, '')) LIKE ?
            GROUP BY prod.nombre, dest.nombre, p.nombre_pais, pr.nombre_producto
            ORDER BY kg_totales DESC
        """
        rows = self._rows(conn, sql, (f"%{contains}%",))
        headers = list(rows[0].keys()) if rows else ["codigo", "pregunta_comercial", "origen_datos", "registros_utilizados", "fecha_generacion"]
        return headers, rows or [{"codigo": code, "pregunta_comercial": question, "origen_datos": "movimientos + dimensiones SQLite", "registros_utilizados": 0, "fecha_generacion": datetime.now(UTC).date().isoformat()}], purpose

    def _competencia(self, conn: sqlite3.Connection) -> tuple[list[str], list[Row], str]:
        rows = self._rows(conn, """
            SELECT 'TD-015/016' AS codigo, 'Competencia CALIRAL vs Arbiza y otros depósitos' AS pregunta_comercial,
                   'movimientos + dimensiones SQLite' AS origen_datos, COUNT(*) AS registros_utilizados,
                   DATE('now') AS fecha_generacion,
                   CASE WHEN UPPER(COALESCE(cert.nombre,'')) LIKE '%CALIRAL%' THEN 'CALIRAL'
                        WHEN UPPER(COALESCE(cert.nombre,'')) LIKE '%ARBIZA%' THEN 'ARBIZA'
                        ELSE 'OTROS' END AS grupo_competencia,
                   SUM(m.peso) AS kg_totales, COUNT(*) AS movimientos
            FROM movimientos m
            LEFT JOIN empresas cert ON cert.id_empresa = m.id_certificador
            GROUP BY grupo_competencia
            ORDER BY kg_totales DESC
        """)
        return list(rows[0].keys()) if rows else ["codigo"], rows or [{"codigo": "TD-015/016"}], "Comparativo competitivo CALIRAL, Arbiza y otros."

    def _diccionario(self, conn: sqlite3.Connection) -> tuple[list[str], list[Row], str]:
        rows = []
        for table in ["movimientos", "empresas", "paises", "productos", "cortes", "calendario"]:
            for column in conn.execute(f"PRAGMA table_info({table})"):
                rows.append({"tabla": table, "campo": column[1], "tipo_dato": column[2], "obligatorio": bool(column[3]), "descripcion": "Generado desde SQLite"})
        return ["tabla", "campo", "tipo_dato", "obligatorio", "descripcion"], rows, "Diccionario técnico generado desde el esquema SQLite."

    def _reglas(self, conn: sqlite3.Connection) -> tuple[list[str], list[Row], str]:
        rows = [
            {"codigo": "RN-001", "regla": "Destino Puerto = Exportado", "aplicacion": "solo_deposito = 0", "estado": "Aplicada"},
            {"codigo": "RN-002", "regla": "País con '(Solo a Depósitos)' = No Exportado", "aplicacion": "solo_deposito = 1", "estado": "Aplicada"},
            {"codigo": "RN-003", "regla": "Temperaturas normalizadas", "aplicacion": "Preparada para campo futuro", "estado": "Preparada"},
        ]
        return ["codigo", "regla", "aplicacion", "estado"], rows, "Reglas de negocio aplicadas o preparadas para validar FRIMARAL BI."

    def _catalogo_consultas(self, conn: sqlite3.Connection) -> tuple[list[str], list[Row], str]:
        rows = [{"codigo": f"TD-{i:03d}", "pregunta_comercial": question, "origen_datos": "SQLite normalizado", "estado": "Generada"} for i, question in enumerate([
            "Ranking Productores", "Ranking Depósitos", "Ranking Certificadores", "Productor x Depósito", "Productor x Mercado", "Productor x Certificador", "Depósito x Mercado", "Depósito x Producto", "CALIRAL x Productores", "CALIRAL x Mercados", "CALIRAL x Productos", "SAN JACINTO x Depósitos", "SAN JACINTO Exportado por CALIRAL", "SAN JACINTO Exportado sin CALIRAL", "Competencia CALIRAL vs Arbiza", "Competencia CALIRAL vs Otros Depósitos"], start=1)]
        return ["codigo", "pregunta_comercial", "origen_datos", "estado"], rows, "Catálogo oficial de consultas de validación comercial."

    def _placeholder_dashboard(self, conn: sqlite3.Connection, name: str) -> tuple[list[str], list[Row], str]:
        rows = [{"seccion": name, "estado": "Reservado", "nota": "No se desarrollan dashboards interactivos en este sprint."}]
        return ["seccion", "estado", "nota"], rows, "Hoja reservada y no vacía para trazabilidad futura."

    # ------------------------------------------------------------------
    # Sprint 5 — Motor de Inteligencia Competitiva
    # ------------------------------------------------------------------

    def _last_ci(self) -> str:
        """Cache de la última ejecución CI; la inicializa perezosamente."""
        if not hasattr(self, "_ci_cache"):
            self._ci_cache = CompetitiveIntelligenceEngine(self.database_path).ejecutar(persistir=True)
        return self._ci_cache

    def _ci_table(
        self,
        conn: sqlite3.Connection,
        table: str,
        purpose: str,
        ci_result: object,
    ) -> tuple[list[str], list[Row], str]:
        """Lee una tabla `ci_*` materializada por el motor CI.

        Si la tabla no existe todavía (la BD se generó antes del Sprint 5),
        ejecuta el motor CI para crearla. Así el workbook nunca queda vacío.
        """
        try:
            rows = self._rows(conn, f"SELECT * FROM {table} ORDER BY 1 DESC")
        except sqlite3.Error:
            rows = []
        if not rows:
            # Tabla vacía o inexistente: ejecute el motor CI y reintente.
            CompetitiveIntelligenceEngine(self.database_path).ejecutar(persistir=True)
            try:
                rows = self._rows(conn, f"SELECT * FROM {table} ORDER BY 1 DESC")
            except sqlite3.Error:
                rows = []
        headers = list(rows[0].keys()) if rows else ["empresa_focal", "detalle"]
        return headers, rows or [{"empresa_focal": "CALIRAL", "detalle": "Sin datos CI"}], purpose


class MasterWorkbookWriter:
    """Escribe un XLSX profesional con hojas y tablas estructuradas."""

    def save(self, path: Path, payloads: list[SheetPayload]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(path, "w", ZIP_DEFLATED) as zip_file:
            self._write_package(zip_file, payloads)

    def _write_package(self, zip_file: ZipFile, payloads: list[SheetPayload]) -> None:
        count = len(payloads)
        zip_file.writestr("[Content_Types].xml", self._content_types(count))
        zip_file.writestr("_rels/.rels", self._root_rels())
        zip_file.writestr("xl/workbook.xml", self._workbook_xml(payloads))
        zip_file.writestr("xl/_rels/workbook.xml.rels", self._workbook_rels(count))
        zip_file.writestr("xl/styles.xml", self._styles_xml())
        for index, payload in enumerate(payloads, start=1):
            zip_file.writestr(f"xl/worksheets/sheet{index}.xml", self._sheet_xml(payload, index))
            zip_file.writestr(f"xl/worksheets/_rels/sheet{index}.xml.rels", self._sheet_rels(index))
            zip_file.writestr(f"xl/tables/table{index}.xml", self._table_xml(payload, index))

    def _sheet_xml(self, payload: SheetPayload, index: int) -> str:
        title_row = [f"FRIMARAL BI | {payload.title}"]
        if payload.name != "00_Inicio":
            title_row = [f"FRIMARAL BI | {payload.title}", "", "", "", "", "", "", "", "", "Volver al inicio"]
        rows_xml = [self._row(1, title_row, style=1), self._row(2, [payload.purpose], style=2)]
        if payload.name == "00_Inicio":
            nav = [[sheet] for sheet in MASTER_WORKBOOK_SHEETS]
            rows_xml.extend(self._rows_from_values(4, ["Navegación"], nav, link_to_sheet=True))
            start_row = len(nav) + 7
        else:
            start_row = 5
        rows_xml.extend(self._rows_from_values(start_row, payload.headers, [[row.get(header, "") for header in payload.headers] for row in payload.rows]))
        max_columns = max(len(payload.headers), 10)
        cols = "".join(f'<col min="{i}" max="{i}" width="{28 if i < 4 else 18}" customWidth="1"/>' for i in range(1, max_columns + 1))
        table_ref = self._table_ref(payload)
        hyperlinks = self._hyperlinks(payload)
        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView showGridLines="0" workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>{cols}</cols><sheetData>{''.join(rows_xml)}</sheetData><mergeCells count="2"><mergeCell ref="A1:H1"/><mergeCell ref="A2:H2"/></mergeCells>{hyperlinks}<tableParts count="1"><tablePart r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></tableParts></worksheet>'''

    def _rows_from_values(self, start_row: int, headers: list[str], values: list[list[object]], link_to_sheet: bool = False) -> list[str]:
        output = [self._row(start_row, headers, style=3)]
        for offset, row in enumerate(values, start=start_row + 1):
            output.append(self._row(offset, row, style=0, link_to_sheet=link_to_sheet))
        return output

    def _row(self, row_number: int, values: list[object], start_col: int = 1, style: int = 0, hyperlink: str | None = None, link_to_sheet: bool = False) -> str:
        cells = []
        for offset, value in enumerate(values):
            col = start_col + offset
            ref = f"{column_name(col)}{row_number}"
            cell_style = style or (4 if link_to_sheet and col == 1 else 0)
            attrs = f' r="{ref}" s="{cell_style}"' if cell_style else f' r="{ref}"'
            cells.append(f'<c{attrs} t="inlineStr"><is><t>{escape(str(value))}</t></is></c>')
        return f'<row r="{row_number}">{''.join(cells)}</row>'

    def _table_ref(self, payload: SheetPayload) -> str:
        start = 4 if payload.name == "00_Inicio" else 5
        end = start + max(len(payload.rows), 1)
        return f"A{start}:{column_name(len(payload.headers))}{end}"

    def _hyperlinks(self, payload: SheetPayload) -> str:
        links = []
        if payload.name == "00_Inicio":
            for offset, sheet in enumerate(MASTER_WORKBOOK_SHEETS, start=5):
                links.append(f'<hyperlink ref="A{offset}" location="{escape("#\'" + sheet + "\'!A1")}"/>')
        else:
            links.append('<hyperlink ref="J1" location="#\'00_Inicio\'!A1"/>')
        return f"<hyperlinks>{''.join(links)}</hyperlinks>"

    def _table_xml(self, payload: SheetPayload, index: int) -> str:
        table_name = "tbl_" + "".join(ch if ch.isalnum() else "_" for ch in payload.name.lower())
        columns = "".join(f'<tableColumn id="{i}" name="{escape(header)}"/>' for i, header in enumerate(payload.headers, start=1))
        ref = self._table_ref(payload)
        return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><table xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" id="{index}" name="{table_name}" displayName="{table_name}" ref="{ref}" totalsRowShown="0"><autoFilter ref="{ref}"/><tableColumns count="{len(payload.headers)}">{columns}</tableColumns><tableStyleInfo name="TableStyleMedium2" showFirstColumn="0" showLastColumn="0" showRowStripes="1" showColumnStripes="0"/></table>'''

    def _content_types(self, count: int) -> str:
        overrides = "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/tables/table{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"/>' for i in range(1, count + 1))
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>{overrides}</Types>'

    def _root_rels(self) -> str:
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'

    def _workbook_xml(self, payloads: list[SheetPayload]) -> str:
        sheets = "".join(f'<sheet name="{escape(payload.name)}" sheetId="{i}" r:id="rId{i}"/>' for i, payload in enumerate(payloads, start=1))
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{sheets}</sheets></workbook>'

    def _workbook_rels(self, count: int) -> str:
        rels = "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, count + 1))
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{rels}<Relationship Id="rId99" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>'

    def _sheet_rels(self, index: int) -> str:
        return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/table" Target="../tables/table{index}.xml"/></Relationships>'

    def _styles_xml(self) -> str:
        return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="4"><font/><font><b/><color rgb="FFFFFFFF"/><sz val="16"/></font><font><i/><color rgb="FF666666"/></font><font><u/><color rgb="FF0563C1"/></font></fonts><fills count="5"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF7FBFE"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FF0B1F33"/></patternFill></fill></fills><borders count="1"><border/></borders><cellXfs count="5"><xf/><xf fontId="1" fillId="2" applyFont="1" applyFill="1"/><xf fontId="2" fillId="3" applyFont="1" applyFill="1"/><xf fontId="1" fillId="4" applyFont="1" applyFill="1"/><xf fontId="3" applyFont="1"/></cellXfs></styleSheet>'


def build_master_workbook(database_path: Path, output_path: Path) -> None:
    payloads = SQLiteBIReader(database_path).build_payloads()
    MasterWorkbookWriter().save(output_path, payloads)
