from pathlib import Path
from openpyxl import load_workbook

BASE_DIR = Path(__file__).resolve().parent
EXCEL_PATH = BASE_DIR / "data" / "NEW-PRICE LIST.xlsx"

wb = load_workbook(EXCEL_PATH, data_only=True)

for sheet in wb.worksheets:
    print("\n" + "=" * 80)
    print("SHEET:", sheet.title)
    print("=" * 80)

    # فقط 5 ردیف اول برای تشخیص ساختار
    for row_number, row in enumerate(
        sheet.iter_rows(min_row=1, max_row=5, values_only=True),
        start=1
    ):
        print(f"ROW {row_number}:")
        
        for column_number, value in enumerate(row, start=1):
            if value is not None:
                print(f"  COL {column_number}: {repr(value)}")

        print("-" * 50)