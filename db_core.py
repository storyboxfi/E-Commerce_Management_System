"""Shared database layer used by BOTH the CLI (cli_app.py) and the GUI (gui_app.py)."""

import os
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor

# Connection settings - override with environment variables if needed
CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": os.getenv("PGPORT", "5432"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "mypassword"),
}


DATABASES = {
    "inventory_db": {
        "products":    {"pk": "product_id",   "cols": ["sku", "name", "category", "price"]},
        "warehouses":  {"pk": "warehouse_id", "cols": ["name", "city"]},
        "stock_levels": {"pk": "stock_id",    "cols": ["product_id", "warehouse_id", "quantity"]},
    },
    "crm_db": {
        "customers":     {"pk": "customer_id", "cols": ["first_name", "last_name", "email", "phone", "tier_id", "points"]},
        "loyalty_tiers": {"pk": "tier_id",     "cols": ["name", "min_points", "discount_percent"]},
        "customer_notes": {"pk": "note_id",    "cols": ["customer_id", "note"]},
    },
    "orders_db": {
        "orders":          {"pk": "order_id",    "cols": ["customer_id", "total"]},
        "order_items":     {"pk": "item_id",     "cols": ["order_id", "product_id", "quantity", "unit_price"]},
        "shipping_status": {"pk": "shipping_id", "cols": ["order_id", "status"]},
    },
}

SHIPPING_STATES = ["Processing", "Shipped", "Delivered", "Cancelled"]


def connect(dbname="postgres"):
    return psycopg2.connect(dbname=dbname, **CONFIG)


def run_query(db, query, params=None):
    """Run a SELECT, return list of dict rows."""
    with connect(db) as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, params)
        return cur.fetchall()


def run_command(db, query, params=None):
    """Run INSERT/UPDATE/DELETE, return affected row count."""
    with connect(db) as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return cur.rowcount


def fetch_table(db, table, limit=200):
    pk = DATABASES[db][table]["pk"]
    q = sql.SQL("SELECT * FROM {} ORDER BY {} LIMIT %s").format(
        sql.Identifier(table), sql.Identifier(pk))
    return run_query(db, q, (limit,))


def _clean(values):
    return {k: (None if v == "" else v) for k, v in values.items()}


def insert_row(db, table, values):
    values = _clean(values)
    q = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, values)),
        sql.SQL(", ").join(sql.Placeholder() * len(values)))
    return run_command(db, q, list(values.values()))


def update_row(db, table, pk_value, values):
    values = _clean(values)
    pk = DATABASES[db][table]["pk"]
    q = sql.SQL("UPDATE {} SET {} WHERE {} = %s").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(c)) for c in values),
        sql.Identifier(pk))
    return run_command(db, q, list(values.values()) + [pk_value])


def delete_row(db, table, pk_value):
    pk = DATABASES[db][table]["pk"]
    q = sql.SQL("DELETE FROM {} WHERE {} = %s").format(sql.Identifier(table), sql.Identifier(pk))
    return run_command(db, q, (pk_value,))


# ---------- Cross-database business logic ----------
def create_order(customer_id, items, warehouse_id=1):
    """
    Create an order that touches ALL THREE databases:
      crm_db       -> verify the customer exists, apply loyalty discount
      inventory_db -> read product prices, reduce stock
      orders_db    -> write orders, order_items, shipping_status
    items: list of (product_id, quantity)
    """
    cust = run_query("crm_db", """SELECT c.customer_id, c.first_name, t.discount_percent
                                  FROM customers c JOIN loyalty_tiers t USING (tier_id)
                                  WHERE c.customer_id = %s""", (customer_id,))
    if not cust:
        raise ValueError(f"Customer {customer_id} not found in crm_db")
    discount = float(cust[0]["discount_percent"])

    priced, total = [], 0.0
    for pid, qty in items:
        prod = run_query("inventory_db", "SELECT price FROM products WHERE product_id=%s", (pid,))
        if not prod:
            raise ValueError(f"Product {pid} not found in inventory_db")
        stock = run_query("inventory_db",
                          "SELECT quantity FROM stock_levels WHERE product_id=%s AND warehouse_id=%s",
                          (pid, warehouse_id))
        if not stock or stock[0]["quantity"] < qty:
            raise ValueError(f"Not enough stock for product {pid} in warehouse {warehouse_id}")
        price = float(prod[0]["price"])
        priced.append((pid, qty, price))
        total += price * qty
    total = round(total * (1 - discount / 100), 2)

    with connect("orders_db") as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO orders (customer_id,total) VALUES (%s,%s) RETURNING order_id",
                    (customer_id, total))
        order_id = cur.fetchone()[0]
        for pid, qty, price in priced:
            cur.execute("INSERT INTO order_items (order_id,product_id,quantity,unit_price) VALUES (%s,%s,%s,%s)",
                        (order_id, pid, qty, price))
        cur.execute("INSERT INTO shipping_status (order_id,status) VALUES (%s,'Processing')", (order_id,))
    for pid, qty, _ in priced:
        run_command("inventory_db",
                    "UPDATE stock_levels SET quantity = quantity - %s WHERE product_id=%s AND warehouse_id=%s",
                    (qty, pid, warehouse_id))
    return order_id, total, discount
