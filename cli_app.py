import psycopg2
import db_core as core
from db_core import DATABASES


def show(rows, title=""):
    """Print rows as a simple aligned table."""
    if title:
        print(f"\n=== {title} ===")
    if not rows:
        print("(no rows)"); return
    cols = list(rows[0].keys())
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    line = "-+-".join("-" * widths[c] for c in cols)
    print(" | ".join(c.ljust(widths[c]) for c in cols)); print(line)
    for r in rows:
        print(" | ".join(str(r[c]).ljust(widths[c]) for c in cols))
    print(f"({len(rows)} rows)")


def choose(prompt, options):
    """Numbered menu -> returns chosen option or None for back."""
    print()
    for i, o in enumerate(options, 1):
        print(f"  {i}. {o}")
    print("  0. Back / Exit")
    while True:
        s = input(f"{prompt}: ").strip()
        if s == "0":
            return None
        if s.isdigit() and 1 <= int(s) <= len(options):
            return options[int(s) - 1]
        print("Invalid choice.")


def safe(fn):
    """Run an action and print DB errors nicely instead of crashing."""
    try:
        fn()
    except (psycopg2.Error, ValueError) as e:
        print(f"[ERROR] {str(e).strip()}")


# ---------- generic CRUD ----------
def view_table(db, table):
    show(core.fetch_table(db, table), f"{db}.{table}")


def add_row(db, table):
    vals = {c: input(f"  {c}: ").strip() for c in DATABASES[db][table]["cols"]}
    core.insert_row(db, table, vals); print("[OK] row added")


def edit_row(db, table):
    meta = DATABASES[db][table]
    pk = input(f"  {meta['pk']} of the row to edit: ").strip()
    print("  (press Enter to keep the current value)")
    vals = {}
    for c in meta["cols"]:
        v = input(f"  new {c}: ").strip()
        if v != "":
            vals[c] = v
    if not vals:
        print("Nothing to change."); return
    n = core.update_row(db, table, pk, vals)
    print("[OK] row updated" if n else "[!] no row with that id")


def delete_row(db, table):
    meta = DATABASES[db][table]
    pk = input(f"  {meta['pk']} of the row to delete: ").strip()
    if input(f"  Really delete {pk}? (y/n): ").lower() == "y":
        n = core.delete_row(db, table, pk)
        print("[OK] row deleted" if n else "[!] no row with that id")


def table_menu(db):
    while True:
        table = choose(f"[{db}] choose a table", list(DATABASES[db]))
        if not table:
            return
        while True:
            act = choose(f"[{db}.{table}] action", ["View data", "Add row", "Edit row", "Delete row"])
            if not act:
                break
            actions = {"View data": view_table, "Add row": add_row, "Edit row": edit_row, "Delete row": delete_row}
            safe(lambda: actions[act](db, table))


# ---------- special actions per database ----------
def stock_across_warehouses():
    key = input("  product name or SKU (part of it, Enter = all): ").strip()
    show(core.run_query("inventory_db", """
        SELECT p.product_id, p.sku, p.name, w.name AS warehouse, s.quantity
        FROM products p JOIN stock_levels s USING (product_id) JOIN warehouses w USING (warehouse_id)
        WHERE p.name ILIKE %s OR p.sku ILIKE %s ORDER BY p.product_id, w.name""",
        (f"%{key}%", f"%{key}%")), "Stock across warehouses")


def update_price():
    pid, price = input("  product_id: ").strip(), input("  new price: ").strip()
    n = core.run_command("inventory_db", "UPDATE products SET price=%s WHERE product_id=%s", (price, pid))
    print("[OK] price updated" if n else "[!] product not found")


def lookup_customer():
    key = input("  name or email (part of it): ").strip()
    rows = core.run_query("crm_db", """
        SELECT c.customer_id, c.first_name, c.last_name, c.email, t.name AS tier, c.points
        FROM customers c JOIN loyalty_tiers t USING (tier_id)
        WHERE c.first_name ILIKE %s OR c.last_name ILIKE %s OR c.email ILIKE %s""", (f"%{key}%",) * 3)
    show(rows, "Customers")
    for r in rows:
        notes = core.run_query("crm_db", "SELECT note, created_at FROM customer_notes WHERE customer_id=%s",
                               (r["customer_id"],))
        show(notes, f"Notes for {r['first_name']} {r['last_name']}")


def upgrade_tier():
    show(core.run_query("crm_db", "SELECT * FROM loyalty_tiers ORDER BY tier_id"), "Tiers")
    cid, tid = input("  customer_id: ").strip(), input("  new tier_id: ").strip()
    n = core.run_command("crm_db", "UPDATE customers SET tier_id=%s WHERE customer_id=%s", (tid, cid))
    print("[OK] tier updated" if n else "[!] customer not found")


def recent_orders():
    # orders_db knows only customer_id -> we ask crm_db for names (cross-database lookup)
    rows = core.run_query("orders_db", """
        SELECT o.order_id, o.customer_id, o.order_date::date AS date, o.total, s.status
        FROM orders o JOIN shipping_status s USING (order_id) ORDER BY o.order_date DESC, o.order_id DESC LIMIT 10""")
    names = {r["customer_id"]: f"{r['first_name']} {r['last_name']}"
             for r in core.run_query("crm_db", "SELECT customer_id, first_name, last_name FROM customers")}
    for r in rows:
        r["customer"] = names.get(r["customer_id"], "?")
    show(rows, "Recent orders (customer names come from crm_db)")


def update_shipping():
    oid = input("  order_id: ").strip()
    st = choose("new status", core.SHIPPING_STATES)
    if st:
        n = core.run_command("orders_db",
                             "UPDATE shipping_status SET status=%s, updated_at=NOW() WHERE order_id=%s", (st, oid))
        print("[OK] status updated" if n else "[!] order not found")


def new_order():
    cid = int(input("  customer_id (crm_db): "))
    items = []
    while True:
        pid = input("  product_id (inventory_db, Enter to finish): ").strip()
        if not pid:
            break
        items.append((int(pid), int(input("  quantity: "))))
    if not items:
        print("No items."); return
    wh = int(input("  take stock from warehouse_id [1]: ") or 1)
    oid, total, disc = core.create_order(cid, items, wh)
    print(f"[OK] order #{oid} created, total {total} (loyalty discount {disc}%) - stock reduced, status Processing")


SPECIAL = {
    "inventory_db": {"Check product stock across warehouses": stock_across_warehouses, "Update a product price": update_price},
    "crm_db": {"Look up customer details": lookup_customer, "Upgrade loyalty tier": upgrade_tier},
    "orders_db": {"View recent orders": recent_orders, "Update shipping status": update_shipping,
                  "Create a new order (uses all 3 DBs)": new_order},
}


def database_menu(db):
    while True:
        extras = list(SPECIAL[db])
        pick = choose(f"[{db}]", ["Browse / add / edit / delete tables"] + extras)
        if not pick:
            return
        if pick.startswith("Browse"):
            table_menu(db)
        else:
            safe(SPECIAL[db][pick])


def main():
    print("=== E-Commerce & Retail Ecosystem (3 PostgreSQL databases) ===")
    while True:
        db = choose("Select a database", list(DATABASES))
        if not db:
            print("Bye!"); return
        safe(lambda: database_menu(db))


if __name__ == "__main__":
    main()
