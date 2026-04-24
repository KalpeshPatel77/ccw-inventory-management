"""
SQLite database layer for the Factory Inventory Management System.
Seeds from JSON files on first startup, then reads/writes from SQLite.
"""

import json
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(BASE_DIR, "inventory.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _load_json(filename):
    with open(os.path.join(DATA_DIR, filename)) as f:
        return json.load(f)


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS inventory (
                id TEXT PRIMARY KEY,
                sku TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                warehouse TEXT NOT NULL,
                quantity_on_hand INTEGER NOT NULL,
                reorder_point INTEGER NOT NULL,
                unit_cost REAL NOT NULL,
                location TEXT NOT NULL,
                last_updated TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                order_number TEXT NOT NULL,
                customer TEXT NOT NULL,
                status TEXT NOT NULL,
                warehouse TEXT,
                category TEXT,
                order_date TEXT NOT NULL,
                expected_delivery TEXT NOT NULL,
                actual_delivery TEXT,
                total_value REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL REFERENCES orders(id),
                sku TEXT NOT NULL,
                name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS demand_forecasts (
                id TEXT PRIMARY KEY,
                item_sku TEXT NOT NULL,
                item_name TEXT NOT NULL,
                current_demand INTEGER NOT NULL,
                forecasted_demand INTEGER NOT NULL,
                trend TEXT NOT NULL,
                period TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS backlog_items (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                item_sku TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity_needed INTEGER NOT NULL,
                quantity_available INTEGER NOT NULL,
                days_delayed INTEGER NOT NULL,
                priority TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS purchase_orders (
                id TEXT PRIMARY KEY,
                backlog_item_id TEXT NOT NULL REFERENCES backlog_items(id),
                supplier_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_cost REAL NOT NULL,
                expected_delivery_date TEXT NOT NULL,
                status TEXT NOT NULL,
                created_date TEXT NOT NULL,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                warehouse TEXT NOT NULL,
                amount REAL NOT NULL,
                vendor TEXT NOT NULL,
                type TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS spending_summary (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                total_procurement_cost REAL NOT NULL,
                total_operational_cost REAL NOT NULL,
                total_labor_cost REAL NOT NULL,
                total_overhead REAL NOT NULL,
                procurement_change REAL NOT NULL,
                operational_change REAL NOT NULL,
                labor_change REAL NOT NULL,
                overhead_change REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS monthly_spending (
                month TEXT PRIMARY KEY,
                procurement INTEGER NOT NULL,
                operational INTEGER NOT NULL,
                labor INTEGER NOT NULL,
                overhead INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS category_spending (
                category TEXT PRIMARY KEY,
                amount INTEGER NOT NULL,
                percentage REAL NOT NULL,
                change REAL NOT NULL
            );
        """)

        # Only seed if tables are empty
        row_count = conn.execute("SELECT COUNT(*) FROM inventory").fetchone()[0]
        if row_count == 0:
            _seed(conn)


def _seed(conn):
    for item in _load_json("inventory.json"):
        conn.execute(
            "INSERT INTO inventory VALUES (?,?,?,?,?,?,?,?,?,?)",
            (item["id"], item["sku"], item["name"], item["category"],
             item["warehouse"], item["quantity_on_hand"], item["reorder_point"],
             item["unit_cost"], item["location"], item["last_updated"]),
        )

    for order in _load_json("orders.json"):
        cur = conn.execute(
            "INSERT OR IGNORE INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)",
            (order["id"], order["order_number"], order["customer"],
             order["status"], order.get("warehouse"), order.get("category"),
             order["order_date"], order["expected_delivery"],
             order.get("actual_delivery"), order["total_value"]),
        )
        if cur.rowcount:
            for item in order.get("items", []):
                conn.execute(
                    "INSERT INTO order_items (order_id, sku, name, quantity, unit_price) VALUES (?,?,?,?,?)",
                    (order["id"], item["sku"], item["name"], item["quantity"], item["unit_price"]),
                )

    for row in _load_json("demand_forecasts.json"):
        conn.execute(
            "INSERT INTO demand_forecasts VALUES (?,?,?,?,?,?,?)",
            (row["id"], row["item_sku"], row["item_name"], row["current_demand"],
             row["forecasted_demand"], row["trend"], row["period"]),
        )

    for row in _load_json("backlog_items.json"):
        conn.execute(
            "INSERT INTO backlog_items VALUES (?,?,?,?,?,?,?,?)",
            (row["id"], row["order_id"], row["item_sku"], row["item_name"],
             row["quantity_needed"], row["quantity_available"],
             row["days_delayed"], row["priority"]),
        )

    for row in _load_json("purchase_orders.json"):
        conn.execute(
            "INSERT INTO purchase_orders VALUES (?,?,?,?,?,?,?,?,?)",
            (row["id"], row["backlog_item_id"], row["supplier_name"],
             row["quantity"], row["unit_cost"], row["expected_delivery_date"],
             row["status"], row["created_date"], row.get("notes")),
        )

    for row in _load_json("transactions.json"):
        conn.execute(
            "INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?)",
            (row["id"], row["date"], row["description"], row["category"],
             row["warehouse"], row["amount"], row["vendor"], row["type"]),
        )

    spending_data = _load_json("spending.json")

    s = spending_data["spending_summary"]
    conn.execute(
        "INSERT INTO spending_summary VALUES (1,?,?,?,?,?,?,?,?)",
        (s["total_procurement_cost"], s["total_operational_cost"],
         s["total_labor_cost"], s["total_overhead"],
         s["procurement_change"], s["operational_change"],
         s["labor_change"], s["overhead_change"]),
    )

    for row in spending_data["monthly_spending"]:
        conn.execute(
            "INSERT INTO monthly_spending VALUES (?,?,?,?,?)",
            (row["month"], row["procurement"], row["operational"],
             row["labor"], row["overhead"]),
        )

    for row in spending_data["category_spending"]:
        conn.execute(
            "INSERT INTO category_spending VALUES (?,?,?,?)",
            (row["category"], row["amount"], row["percentage"], row["change"]),
        )


# ---------------------------------------------------------------------------
# Query helpers used by main.py
# ---------------------------------------------------------------------------

def _rows_to_dicts(rows):
    return [dict(r) for r in rows]


def _attach_order_items(conn, orders):
    """Batch-fetch all order_items for a list of orders in a single query."""
    if not orders:
        return orders
    order_map = {o["id"]: o for o in orders}
    for o in orders:
        o["items"] = []
    ids = list(order_map)
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT order_id, sku, name, quantity, unit_price FROM order_items WHERE order_id IN ({placeholders})",
        ids,
    ).fetchall()
    for row in rows:
        order_map[row["order_id"]]["items"].append(dict(row))
    return orders


def get_inventory(warehouse=None, category=None):
    sql = "SELECT * FROM inventory WHERE 1=1"
    params = []
    if warehouse and warehouse != "all":
        sql += " AND warehouse = ?"
        params.append(warehouse)
    if category and category != "all":
        sql += " AND LOWER(category) = LOWER(?)"
        params.append(category)
    with get_conn() as conn:
        return _rows_to_dicts(conn.execute(sql, params).fetchall())


def get_inventory_item(item_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM inventory WHERE id = ?", (item_id,)).fetchone()
        return dict(row) if row else None


QUARTER_MAP = {
    "Q1-2025": ["2025-01", "2025-02", "2025-03"],
    "Q2-2025": ["2025-04", "2025-05", "2025-06"],
    "Q3-2025": ["2025-07", "2025-08", "2025-09"],
    "Q4-2025": ["2025-10", "2025-11", "2025-12"],
}


def get_orders(warehouse=None, category=None, status=None, month=None):
    sql = "SELECT * FROM orders WHERE 1=1"
    params = []
    if warehouse and warehouse != "all":
        sql += " AND warehouse = ?"
        params.append(warehouse)
    if category and category != "all":
        sql += " AND LOWER(category) = LOWER(?)"
        params.append(category)
    if status and status != "all":
        sql += " AND LOWER(status) = LOWER(?)"
        params.append(status)
    if month and month != "all":
        if month.startswith("Q") and month in QUARTER_MAP:
            months = QUARTER_MAP[month]
            placeholders = " OR ".join("order_date LIKE ?" for _ in months)
            sql += f" AND ({placeholders})"
            params.extend(f"{m}%" for m in months)
        else:
            sql += " AND order_date LIKE ?"
            params.append(f"{month}%")
    with get_conn() as conn:
        orders = _rows_to_dicts(conn.execute(sql, params).fetchall())
        return _attach_order_items(conn, orders)


def get_order(order_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            return None
        orders = _attach_order_items(conn, [dict(row)])
        return orders[0]


def get_demand_forecasts():
    with get_conn() as conn:
        return _rows_to_dicts(conn.execute("SELECT * FROM demand_forecasts").fetchall())


def get_backlog_items():
    with get_conn() as conn:
        rows = _rows_to_dicts(conn.execute("SELECT * FROM backlog_items").fetchall())
        po_ids = {
            r["backlog_item_id"]
            for r in conn.execute("SELECT DISTINCT backlog_item_id FROM purchase_orders").fetchall()
        }
    for row in rows:
        row["has_purchase_order"] = row["id"] in po_ids
    return rows


def get_purchase_orders():
    with get_conn() as conn:
        return _rows_to_dicts(conn.execute("SELECT * FROM purchase_orders").fetchall())


def create_purchase_order(po_id, backlog_item_id, supplier_name, quantity,
                           unit_cost, expected_delivery_date, created_date, notes=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO purchase_orders VALUES (?,?,?,?,?,?,?,?,?)",
            (po_id, backlog_item_id, supplier_name, quantity, unit_cost,
             expected_delivery_date, "Pending", created_date, notes),
        )
        row = conn.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,)).fetchone()
        return dict(row)


def get_spending_summary():
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM spending_summary WHERE id = 1").fetchone()
    d = dict(row)
    d.pop("id")
    return d


def get_monthly_spending():
    with get_conn() as conn:
        return _rows_to_dicts(conn.execute("SELECT * FROM monthly_spending").fetchall())


def get_category_spending():
    with get_conn() as conn:
        return _rows_to_dicts(conn.execute("SELECT * FROM category_spending").fetchall())


def get_transactions():
    with get_conn() as conn:
        return _rows_to_dicts(conn.execute("SELECT * FROM transactions").fetchall())


def get_quarterly_reports():
    sql = """
        SELECT
            CASE
                WHEN SUBSTR(order_date, 1, 7) IN ('2025-01','2025-02','2025-03') THEN 'Q1-2025'
                WHEN SUBSTR(order_date, 1, 7) IN ('2025-04','2025-05','2025-06') THEN 'Q2-2025'
                WHEN SUBSTR(order_date, 1, 7) IN ('2025-07','2025-08','2025-09') THEN 'Q3-2025'
                WHEN SUBSTR(order_date, 1, 7) IN ('2025-10','2025-11','2025-12') THEN 'Q4-2025'
            END AS quarter,
            COUNT(*) AS total_orders,
            ROUND(SUM(total_value), 2) AS total_revenue,
            SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END) AS delivered_orders,
            ROUND(AVG(total_value), 2) AS avg_order_value,
            ROUND(SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS fulfillment_rate
        FROM orders
        WHERE quarter IS NOT NULL
        GROUP BY quarter
        ORDER BY quarter
    """
    with get_conn() as conn:
        return _rows_to_dicts(conn.execute(sql).fetchall())


def get_monthly_trends():
    sql = """
        SELECT
            SUBSTR(order_date, 1, 7) AS month,
            COUNT(*) AS order_count,
            ROUND(SUM(total_value), 2) AS revenue,
            SUM(CASE WHEN status = 'Delivered' THEN 1 ELSE 0 END) AS delivered_count
        FROM orders
        WHERE order_date != ''
        GROUP BY month
        ORDER BY month
    """
    with get_conn() as conn:
        return _rows_to_dicts(conn.execute(sql).fetchall())
