"""Genera el Libro Maestro FRIMARAL BI como XLSX sin dependencias externas."""
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from xml.sax.saxutils import escape

OUTPUT_PATH = Path("output/FRIMARAL_BI_Libro_Maestro.xlsx")
SHEETS = ["00_Inicio","01_Datos_MGAP","02_Datos_Normalizados","03_Diccionario_MGAP","04_Reglas_Negocio","05_Empresas","06_Productores","07_Depositos","08_Certificadores","09_Mercados","10_Productos","11_Cortes","12_Calendario","13_Catalogo_Consultas","20_Tablas_Dinamicas","30_Dashboard","40_Empresas360","50_Competencia","60_Radar_Comercial"]
DEFS = {
"01_Datos_MGAP": ("Datos MGAP","Zona de aterrizaje para importar los movimientos originales del XLSB del MGAP.",["id_registro","fecha_movimiento","empresa","productor","certificador","deposito","mercado","producto","corte","cantidad","unidad","origen_archivo","fecha_carga"],["PENDIENTE","2025-01-01","","","","","","","","","","MGAP_XLSB",""]),
"02_Datos_Normalizados": ("Datos Normalizados","Modelo limpio y validado para análisis, reglas de negocio y futuras visualizaciones.",["id_movimiento","fecha","id_empresa","id_productor","id_deposito","id_certificador","id_mercado","id_producto","id_corte","cantidad_normalizada","unidad_normalizada","estado_validacion"],["PENDIENTE","2025-01-01","","","","","","","","","","Pendiente"]),
"03_Diccionario_MGAP": ("Diccionario MGAP","Definición oficial de campos, tipos de datos y equivalencias del origen MGAP.",["campo_origen","descripcion","tipo_dato","obligatorio","regla_normalizacion","campo_destino","observaciones"],["","","Texto","Sí/No","","",""]),
"04_Reglas_Negocio": ("Reglas de Negocio","Catálogo trazable de criterios funcionales para validar la futura aplicación BI.",["id_regla","dominio","descripcion","criterio_validacion","prioridad","estado","responsable"],["RN-001","Datos","","","Alta","Borrador","FRIMARAL"]),
"05_Empresas": ("Empresas","Maestro de empresas participantes.",["id_empresa","nombre_empresa","rut","tipo_empresa","estado","fecha_alta","observaciones"],["EMP-0001","","","","Activo","",""]),
"06_Productores": ("Productores","Maestro de establecimientos productores.",["id_productor","nombre_productor","departamento","localidad","estado","id_empresa","observaciones"],["PRO-0001","","","","Activo","",""]),
"07_Depositos": ("Depósitos","Maestro de depósitos y puntos logísticos.",["id_deposito","nombre_deposito","departamento","tipo_deposito","estado","observaciones"],["DEP-0001","","","","Activo",""]),
"08_Certificadores": ("Certificadores","Maestro de certificadores vinculados a movimientos.",["id_certificador","nombre_certificador","tipo_certificacion","estado","observaciones"],["CER-0001","","","Activo",""]),
"09_Mercados": ("Mercados","Dimensión de mercados destino y clasificación comercial.",["id_mercado","mercado","region","pais","estado","observaciones"],["MER-0001","","","","Activo",""]),
"10_Productos": ("Productos","Maestro de productos para análisis comercial.",["id_producto","producto","familia","categoria","estado","observaciones"],["PRD-0001","","","","Activo",""]),
"11_Cortes": ("Cortes","Catálogo de cortes o presentaciones comerciales.",["id_corte","corte","id_producto","familia","estado","observaciones"],["COR-0001","","","","Activo",""]),
"12_Calendario": ("Calendario","Dimensión calendario desde el 01/01/2025 para series temporales.",["fecha","anio","trimestre","mes","nombre_mes","semana","dia","dia_semana"],["2025-01-01","2025","T1","1","Enero","1","1","Miércoles"]),
"13_Catalogo_Consultas": ("Catálogo de Consultas","Inventario de consultas, métricas y validaciones esperadas.",["id_consulta","nombre","objetivo","fuente","frecuencia","salida_esperada","estado"],["Q-001","","","","","","Borrador"]),
}
PLACEHOLDER = (["seccion","objetivo","estado","responsable","proxima_accion"],["Reservado","Pendiente de definición","Reservado","FRIMARAL","Diseñar en fase futura"])

def col(n:int)->str:
    s=""
    while n:
        n,r=divmod(n-1,26); s=chr(65+r)+s
    return s

def cell(c,r,v,style=0,hyper=None):
    ref=f"{col(c)}{r}"; attrs=f' r="{ref}" s="{style}"' if style else f' r="{ref}"'
    if hyper:
        return f'<c{attrs} t="inlineStr"><is><t>{escape(str(v))}</t></is></c>', (ref, hyper)
    return f'<c{attrs} t="inlineStr"><is><t>{escape(str(v))}</t></is></c>', None

def sheet_xml(name, idx):
    rows=[]; links=[]
    title,purpose,headers,data = DEFS.get(name,(name.split('_',1)[-1].replace('_',' '),"Hoja reservada para una fase posterior; no contiene tablas dinámicas ni gráficos.",*PLACEHOLDER))
    if name=="00_Inicio":
        title="Inicio"; purpose="Navegación principal del Libro Maestro de Business Intelligence."; headers=["hoja","proposito","estado"]
        desc={n:DEFS[n][1] for n in DEFS}; desc.update({"00_Inicio":"Portada y mapa de navegación del libro.","20_Tablas_Dinamicas":"Reservada para futuras tablas dinámicas; sin desarrollo en esta etapa.","30_Dashboard":"Reservada para futuros dashboards; sin gráficos en esta etapa.","40_Empresas360":"Reservada para vista integral por empresa.","50_Competencia":"Reservada para análisis competitivo.","60_Radar_Comercial":"Reservada para señales y oportunidades comerciales."})
        body=[[n,desc[n],"Estructura creada"] for n in SHEETS]
    else:
        body=[data]
    for r,vals,sty in [(1,[f"FRIMARAL BI | {title}"],1),(2,[purpose],2),(5,headers,3)]:
        cs=[]
        for c,v in enumerate(vals,1):
            x,h=cell(c,r,v,sty); cs.append(x)
        if r == 1 and name != "00_Inicio":
            x,ln=cell(10,1,"Volver al inicio",4,"#'00_Inicio'!A1"); cs.append(x); links.append(ln)
        rows.append(f'<row r="{r}">'+''.join(cs)+'</row>')
    for off,vals in enumerate(body,6):
        cs=[]
        for c,v in enumerate(vals,1):
            h=f"#'{v}'!A1" if name=="00_Inicio" and c==1 else None
            x,ln=cell(c,off,v,4 if c==1 and h else 0,h); cs.append(x)
            if ln: links.append(ln)
        rows.append(f'<row r="{off}">'+''.join(cs)+'</row>')
    maxc=max(len(headers), len(body[0]) if body else 1); maxr=5+len(body)
    hxml=''.join(f'<hyperlink ref="{r}" location="{escape(loc)}" display="{escape(loc)}"/>' for r,loc in links)
    cols=''.join(f'<col min="{i}" max="{i}" width="{28 if i<3 else 18}" customWidth="1"/>' for i in range(1,max(maxc,10)+1))
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView showGridLines="0" workbookViewId="0"><pane ySplit="5" topLeftCell="A6" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>{cols}</cols><sheetData>{''.join(rows)}</sheetData><mergeCells count="2"><mergeCell ref="A1:H1"/><mergeCell ref="A2:H2"/></mergeCells><hyperlinks>{hxml}</hyperlinks><tableParts count="1"><tablePart r:id="rId1" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></tableParts></worksheet>''', maxc, maxr, headers

def table_xml(idx,name,maxc,maxr,headers):
    safe='tbl_'+''.join(ch if ch.isalnum() else '_' for ch in name.lower())
    cols=''.join(f'<tableColumn id="{i}" name="{escape(h)}"/>' for i,h in enumerate(headers,1))
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><table xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" id="{idx}" name="{safe}" displayName="{safe}" ref="A5:{col(maxc)}{maxr}" totalsRowShown="0"><autoFilter ref="A5:{col(maxc)}{maxr}"/><tableColumns count="{len(headers)}">{cols}</tableColumns><tableStyleInfo name="TableStyleMedium2" showFirstColumn="0" showLastColumn="0" showRowStripes="1" showColumnStripes="0"/></table>'''

def build():
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    with ZipFile(OUTPUT_PATH,'w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/tables/table{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"/>' for i in range(1,len(SHEETS)+1))+'</Types>')
        z.writestr('_rels/.rels','<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml','<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{escape(n)}" sheetId="{i}" r:id="rId{i}"/>' for i,n in enumerate(SHEETS,1))+'</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(SHEETS)+1))+'<Relationship Id="rId99" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/styles.xml','<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="4"><font/><font><b/><color rgb="FFFFFFFF"/><sz val="16"/></font><font><i/><color rgb="FF666666"/></font><font><u/><color rgb="FF0563C1"/></font></fonts><fills count="5"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF7FBFE"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FF0B1F33"/></patternFill></fill></fills><borders count="1"><border/></borders><cellXfs count="5"><xf/><xf fontId="1" fillId="2" applyFont="1" applyFill="1"/><xf fontId="2" fillId="3" applyFont="1" applyFill="1"/><xf fontId="1" fillId="4" applyFont="1" applyFill="1"/><xf fontId="3" applyFont="1"/></cellXfs></styleSheet>')
        for i,n in enumerate(SHEETS,1):
            xml,maxc,maxr,headers=sheet_xml(n,i); z.writestr(f'xl/worksheets/sheet{i}.xml',xml); z.writestr(f'xl/worksheets/_rels/sheet{i}.xml.rels',f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/table" Target="../tables/table{i}.xml"/></Relationships>'); z.writestr(f'xl/tables/table{i}.xml',table_xml(i,n,maxc,maxr,headers))
    print(f"Libro creado: {OUTPUT_PATH}")
if __name__ == '__main__': build()
