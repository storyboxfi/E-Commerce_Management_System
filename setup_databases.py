from db_core import connect, CONFIG

SCHEMAS = {
"inventory_db": """
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    sku        VARCHAR(20) UNIQUE NOT NULL,
    name       VARCHAR(100) NOT NULL,
    category   VARCHAR(50),
    price      NUMERIC(10,2) NOT NULL CHECK (price >= 0)
);
CREATE TABLE warehouses (
    warehouse_id SERIAL PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    city         VARCHAR(100)
);
CREATE TABLE stock_levels (
    stock_id     SERIAL PRIMARY KEY,
    product_id   INT NOT NULL REFERENCES products(product_id)   ON DELETE CASCADE,
    warehouse_id INT NOT NULL REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    quantity     INT NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    UNIQUE (product_id, warehouse_id)
);""",
"crm_db": """
CREATE TABLE loyalty_tiers (
    tier_id          SERIAL PRIMARY KEY,
    name             VARCHAR(30) UNIQUE NOT NULL,
    min_points       INT NOT NULL,
    discount_percent NUMERIC(4,1) NOT NULL
);
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    first_name  VARCHAR(50) NOT NULL,
    last_name   VARCHAR(50) NOT NULL,
    email       VARCHAR(100) UNIQUE NOT NULL,
    phone       VARCHAR(30),
    tier_id     INT NOT NULL DEFAULT 1 REFERENCES loyalty_tiers(tier_id),
    points      INT NOT NULL DEFAULT 0,
    created_at  TIMESTAMP DEFAULT NOW()
);
CREATE TABLE customer_notes (
    note_id     SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    note        TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);""",
"orders_db": """
CREATE TABLE orders (
    order_id    SERIAL PRIMARY KEY,
    customer_id INT NOT NULL,          -- logical link to crm_db.customers
    order_date  TIMESTAMP DEFAULT NOW(),
    total       NUMERIC(10,2) NOT NULL
);
CREATE TABLE order_items (
    item_id    SERIAL PRIMARY KEY,
    order_id   INT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_id INT NOT NULL,           -- logical link to inventory_db.products
    quantity   INT NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10,2) NOT NULL
);
CREATE TABLE shipping_status (
    shipping_id SERIAL PRIMARY KEY,
    order_id    INT UNIQUE NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    status      VARCHAR(20) NOT NULL DEFAULT 'Processing'
                CHECK (status IN ('Processing','Shipped','Delivered','Cancelled')),
    updated_at  TIMESTAMP DEFAULT NOW()
);""",
}

# Dummy data 

PRODUCTS = [("LAP-001","UltraBook 14","Laptops",999.00), ("PHN-001","Nova X Phone","Phones",699.00),
            ("HDP-001","NoiseCancel Headphones","Audio",199.50), ("MSE-001","Wireless Mouse","Accessories",25.99),
            ("KBD-001","Mechanical Keyboard","Accessories",89.90), ("MON-001","27in 4K Monitor","Displays",329.00)]
WAREHOUSES = [("Helsinki Central","Helsinki"), ("Tampere Hub","Tampere"), ("Turku Depot","Turku")]
STOCK = [(1,1,25),(1,2,10),(2,1,40),(2,3,15),(3,1,60),(3,2,35),(4,1,200),(4,2,150),(4,3,90),
         (5,2,45),(5,3,30),(6,1,12),(6,3,0)]
TIERS = [("Bronze",0,0),("Silver",500,5),("Gold",1500,10),("Platinum",3000,15)]
CUSTOMERS = [("Aino","Virtanen","aino.virtanen@example.com","+358401111111",3,1700),
             ("Mikko","Korhonen","mikko.korhonen@example.com","+358402222222",1,120),
             ("Laura","Nieminen","laura.nieminen@example.com","+358403333333",2,640),
             ("Juha","Makinen","juha.makinen@example.com","+358404444444",4,3400),
             ("Sofia","Hamalainen","sofia.hamalainen@example.com",None,1,0),
             ("Eero","Laine","eero.laine@example.com","+358406666666",2,900)]
NOTES = [(1,"Prefers email contact."),(1,"Asked about extended warranty."),(4,"VIP - ships to office address."),
         (3,"Returned a defective mouse, replaced.")]
# (customer_id, [(product_id, qty)], discount%, status)
ORDERS = [(1,[(1,1),(4,2)],10,"Delivered"),(2,[(3,1)],0,"Shipped"),(3,[(5,1),(4,1)],5,"Processing"),
          (4,[(2,1),(3,2)],15,"Delivered"),(6,[(6,1)],5,"Processing")]


def recreate_databases():
    conn = connect("postgres"); conn.autocommit = True
    cur = conn.cursor()
    for db in SCHEMAS:
        cur.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (db,))
        cur.execute(f"DROP DATABASE IF EXISTS {db}")
        cur.execute(f"CREATE DATABASE {db}")
        print(f"[OK] created database {db}")
    conn.close()


def create_tables():
    for db, ddl in SCHEMAS.items():
        with connect(db) as conn, conn.cursor() as cur:
            cur.execute(ddl)
        print(f"[OK] tables created in {db}")


def insert_dummy_data():
    price = {i + 1: p[3] for i, p in enumerate(PRODUCTS)}
    with connect("inventory_db") as c, c.cursor() as cur:
        cur.executemany("INSERT INTO products (sku,name,category,price) VALUES (%s,%s,%s,%s)", PRODUCTS)
        cur.executemany("INSERT INTO warehouses (name,city) VALUES (%s,%s)", WAREHOUSES)
        cur.executemany("INSERT INTO stock_levels (product_id,warehouse_id,quantity) VALUES (%s,%s,%s)", STOCK)
    with connect("crm_db") as c, c.cursor() as cur:
        cur.executemany("INSERT INTO loyalty_tiers (name,min_points,discount_percent) VALUES (%s,%s,%s)", TIERS)
        cur.executemany("INSERT INTO customers (first_name,last_name,email,phone,tier_id,points) VALUES (%s,%s,%s,%s,%s,%s)", CUSTOMERS)
        cur.executemany("INSERT INTO customer_notes (customer_id,note) VALUES (%s,%s)", NOTES)
    with connect("orders_db") as c, c.cursor() as cur:
        for cust, items, disc, status in ORDERS:
            total = round(sum(price[p] * q for p, q in items) * (1 - disc / 100), 2)
            cur.execute("INSERT INTO orders (customer_id,total) VALUES (%s,%s) RETURNING order_id", (cust, total))
            oid = cur.fetchone()[0]
            for p, q in items:
                cur.execute("INSERT INTO order_items (order_id,product_id,quantity,unit_price) VALUES (%s,%s,%s,%s)",
                            (oid, p, q, price[p]))
            cur.execute("INSERT INTO shipping_status (order_id,status) VALUES (%s,%s)", (oid, status))
    print("[OK] dummy data inserted into all 3 databases")


if __name__ == "__main__":
    print(f"Connecting to PostgreSQL at {CONFIG['host']}:{CONFIG['port']} as {CONFIG['user']} ...")
    recreate_databases()
    create_tables()
    insert_dummy_data()
    print("\nDone! Now run:  python cli_app.py   (terminal)   or   python gui_app.py   (window)")
