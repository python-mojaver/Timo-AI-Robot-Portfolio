"""Initialize synthetic catalog data only; never overwrite an existing database."""
import json
from contextlib import closing
from pathlib import Path
from database import DB_PATH, create_tables, get_connection

ROOT = Path(__file__).resolve().parent

def main():
    if DB_PATH.exists():
        print("Catalog already exists; no data changed:", DB_PATH)
        return
    create_tables()
    rows = json.loads((ROOT / "examples/products.json").read_text(encoding="utf-8"))
    fields = ("category", "product_code", "product_name", "color", "size",
              "description", "price_rial", "price_toman", "available")
    with closing(get_connection()) as db:
        with db:
            db.executemany(
                "INSERT INTO products (" + ",".join(fields) + ") VALUES (" + ",".join("?" for _ in fields) + ")",
                [[row[field] for field in fields] for row in rows],
            )
    print("Created synthetic catalog with", len(rows), "products:", DB_PATH)

if __name__ == "__main__":
    main()
