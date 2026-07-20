from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from frimaral_bi.models import ImportConfig
from frimaral_bi.pipeline import MotorImportacionMGAP
from frimaral_bi.workbook import MASTER_WORKBOOK_SHEETS, build_master_workbook


def test_master_workbook_is_generated_from_sqlite(tmp_path):
    database_path = tmp_path / "frimaral_bi.db"
    MotorImportacionMGAP().run(
        ImportConfig(
            source_path=Path("tests/fixtures/mgap_sample.csv"),
            database_path=database_path,
            normalized_copy_path=tmp_path / "normalizado.csv",
            log_path=tmp_path / "log.md",
        )
    )
    workbook_path = tmp_path / "FRIMARAL_BI_Libro_Maestro.xlsx"
    build_master_workbook(database_path, workbook_path)

    assert workbook_path.exists()
    with ZipFile(workbook_path) as package:
        workbook = ET.fromstring(package.read("xl/workbook.xml"))
        namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        sheet_names = [sheet.attrib["name"] for sheet in workbook.find("m:sheets", namespace)]
        assert sheet_names == MASTER_WORKBOOK_SHEETS
        assert "xl/tables/table1.xml" in package.namelist()
        td_productores = package.read("xl/worksheets/sheet15.xml").decode("utf-8")
        assert "TD-001" in td_productores
