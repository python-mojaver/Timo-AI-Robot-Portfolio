from pathlib import Path
from openpyxl import load_workbook

from database import get_connection, create_tables

BASE_DIR = Path(__file__).resolve().parent
EXCEL_PATH = BASE_DIR / "data" / "NEW-PRICE LIST.xlsx"


def clean_value(value):
    if value is None:
        return ""
    return str(value).strip()


def to_number(value):
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).replace(",", "").strip()

    try:
        return float(text)
    except ValueError:
        return None


def normalize_header(value):
    if value is None:
        return ""

    return str(value).strip().replace("\u200c", " ")


def import_products():
    create_tables()

    if not EXCEL_PATH.exists():
        print(f"Excel file not found: {EXCEL_PATH}")
        return

    workbook = load_workbook(EXCEL_PATH, data_only=True)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM products")

    total = 0

    for sheet in workbook.worksheets:
        category = sheet.title

        print(f"\nReading sheet: {category}")

        # خواندن هدرهای هر شیت
        header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True))

        headers = {}

        for index, header in enumerate(header_row):
            header_name = normalize_header(header)

            if header_name:
                headers[header_name] = index

        for row in sheet.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue

            def get_column(name):
                index = headers.get(name)

                if index is None:
                    return ""

                if index >= len(row):
                    return ""

                return row[index]

            product_code = clean_value(
                get_column("کد کالا")
            )

            product_name = clean_value(
                get_column("نام کالا")
            )

            description = clean_value(
                get_column("توضیحات")
            )

            size = clean_value(
                get_column("سایز")
            )

            color = clean_value(
                get_column("رنگ")
            )

            price_value = get_column("فی فروش")

            available = 1
            price_rial = None

            # بررسی موجود / ناموجود
            if isinstance(price_value, str):
                if "ناموجود" in price_value.strip():
                    available = 0
                else:
                    price_rial = to_number(price_value)
            else:
                price_rial = to_number(price_value)

            price_toman = (
                price_rial / 10
                if price_rial is not None
                else None
            )

            # اگر نام کالا وجود نداشت، توضیحات را به عنوان نام نمایشی بگیر
            if not product_name:
                product_name = description

            if not product_code and not product_name:
                continue

            cursor.execute("""
                INSERT INTO products (
                    category,
                    product_code,
                    product_name,
                    color,
                    size,
                    description,
                    price_rial,
                    price_toman,
                    available
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                category,
                product_code,
                product_name,
                color,
                size,
                description,
                price_rial,
                price_toman,
                available
            ))

            total += 1

    conn.commit()
    conn.close()

    print("\n-------------------------")
    print(f"Imported products: {total}")
    print("-------------------------")


if __name__ == "__main__":
    import_products()