# E-Commerce Management System

# 3 PostgreSQL databases + Python CLI/GUI


## How everything fits together
| File | Role |
|---|---|
| `setup_databases.py` | Creates `inventory_db`, `crm_db`, `orders_db`, all tables, and dummy data. Safe to re-run (resets data). |
| `db_core.py` | One shared layer: connections, table metadata, generic view/add/edit/delete, and `create_order()` that uses all 3 DBs. |
| `cli_app.py` | Terminal front end (menus). |
| `gui_app.py` | Simple window (Tkinter): pick DB + table, then Refresh / Add / Edit / Delete buttons. |
| `make_diagrams.py` | Draws `architecture.png` and `er_diagram.png`. |

PostgreSQL cannot join across databases, so `orders.customer_id` and `order_items.product_id` are *logical* links.
The app checks them (see `create_order`) by querying `crm_db` and `inventory_db`.

## Run it
```bash
pip install -r requirements.txt
# Postgres must be running. Defaults: localhost:5432, user postgres, password postgres
# Change with:  export PGHOST=... PGPORT=... PGUSER=... PGPASSWORD=...
python setup_databases.py     # 1) create DBs + dummy data
python cli_app.py             # 2a) terminal UI
python gui_app.py             # 2b) window UI (needs tkinter)
```


# This is a simple e-commerce management system built with Python and PostgreSQL. It uses three separate databases, and each one handles a different part of the business:

- **inventory_db** stores products, warehouses and stock levels.
- **crm_db** stores customers, loyalty tiers and customer notes.
- **orders_db** stores orders, order items and shipping status.

The program can be used in two ways, a command line interface (CLI) and a graphical interface (GUI). Both let the user do all four CRUD operations on any table in any database:

- **Create:** add new records, such as a product, a customer or an order.
- **Read:** view the data in a table.
- **Update:** edit existing records, such as changing a price or a shipping status.
- **Delete:** remove records that are no longer needed.

The CLI also has extra actions:

- Check the stock of a product across all warehouses.
- Look up a customer's details.
- Upgrade a customer's loyalty tier.
- View recent orders.
- Create a new order.

Creating an order uses all three databases together. It checks the customer and their loyalty discount in the CRM database, reads the price and stock from the inventory database, and saves the order in the orders database.

A separate setup file creates the three databases and fills them with sample data. It can be run again at any time to reset everything.

**Technologies used:** Python, PostgreSQL, psycopg2 and Tkinter.