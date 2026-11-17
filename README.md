# 🍕 Food Ordering System - Live Operations Portal

A full-stack food ordering and fleet management system built with **PostgreSQL**, **Python (Flask)**, and a **Tailwind CSS + Chart.js Dashboard UI**.

Besides the live analytics dashboard, the system now supports **customer management, menu management, order placement with database transactions, and order status tracking**, and it is designed to demonstrate core DBMS concepts.

---

## 📸 Application Architecture & Features

The UI has 7 tabs:

| Tab | What it does |
| :--- | :--- |
| **Dashboard** | KPIs (revenue, active customers, fleet online, average order value) and Chart.js charts for restaurant revenue share and revenue by food category. Cancelled orders are excluded from revenue. |
| **Customers** | Full CRUD. Search by name, customer ID or city. Shows the number of orders per customer. Customers with orders cannot be deleted. |
| **Restaurants** | Read-only catalog of restaurants with rating, cuisine and number of menu items. |
| **Menu Management** | Full CRUD for food items. Filter by restaurant, search by name, quick price update, and Available / Unavailable toggle. |
| **Place Order** | Pick a customer and a restaurant, add available items to an interactive cart (+ / − / remove), and place the order. Shows the generated order ID. |
| **Orders** | Order ledger with status filter, clickable order ID for full details (items and status history), and a dropdown to update the status. |
| **Delivery Fleet** | Driver availability and vehicle details. |

---

## 🗄️ Database Schema

The database has 7 tables. The full DDL and sample data are in [`schema.sql`](schema.sql).

| Module | Table | Key Columns |
| :--- | :--- | :--- |
| **Customers & Fleet** | `customer` | `cust_id` (PK), `cust_name`, `email` (UNIQUE), `phone`, `city` |
| | `delivery_agent` | `agent_id` (PK), `vehicle_no` (UNIQUE), `license_id` (UNIQUE), `is_available` |
| **Catalog** | `restaurant` | `hotel_id` (PK), `restaurant_name`, `cuisine_type`, `rating` (CHECK 0-5) |
| | `menu_item` | `item_id` (PK), `hotel_id` (FK), `item_name`, `category`, `price` (CHECK > 0), `is_available` |
| **Transactions** | `orders` | `order_id` (PK), `cust_id` (FK), `hotel_id` (FK), `agent_id` (FK, nullable), `order_date_time`, `tot_amount`, `status` (CHECK) |
| | `order_items` | `order_item_id` (PK), `order_id` (FK), `item_id` (FK), `quantity` (CHECK > 0), `price`, UNIQUE(`order_id`, `item_id`) |
| | `order_status_history` | `history_id` (PK), `order_id` (FK), `old_status` (NULL for a new order), `new_status`, `changed_at` |

### Relationships
- **One-to-many:** customer → orders, restaurant → menu_item, restaurant → orders, orders → order_items, orders → order_status_history.
- **Many-to-many:** `orders` ↔ `menu_item`, resolved by the junction table `order_items`.
- `order_items.price` stores the price **at the time of ordering**, so changing a menu price later never changes past orders.

### Foreign key behaviour
- A customer or menu item used in an order **cannot be deleted** (`ON DELETE RESTRICT`). The API returns a clear 409 message. Mark an item Unavailable instead.
- Deleting an order removes its items and history (`ON DELETE CASCADE`).
- Deleting a delivery agent sets `orders.agent_id` to NULL (`ON DELETE SET NULL`).

---

## 🧠 DBMS Concepts Demonstrated

| Concept | Where |
| :--- | :--- |
| Primary and foreign keys, referential integrity | All tables |
| One-to-many and many-to-many | `order_items` junction table |
| Normalization | Order header (`orders`) separated from line items (`order_items`); restaurants, customers and menu in their own tables |
| CRUD with parameterized SQL | `/api/customers`, `/api/menu` |
| CHECK constraints | Price > 0, quantity > 0, rating 0-5, phone format, order status values |
| UNIQUE constraints | Customer email, `(order_id, item_id)`, `(hotel_id, item_name)` |
| JOINs | Orders with customer and restaurant, order details with menu items, category revenue |
| Aggregates, GROUP BY, ORDER BY | `COUNT` orders per customer, `COUNT` items per restaurant, `SUM` revenue per category, `SUM(quantity * price)` for order totals |
| WHERE and search | `ILIKE` search, status filter, restaurant filter |
| NULL handling | Optional phone, unassigned `agent_id`, `COALESCE` in partial updates and totals, `LEFT JOIN` |
| Transactions, COMMIT, ROLLBACK | Order placement and status update |
| Row locking | `FOR SHARE` on menu prices while ordering, `FOR UPDATE` on the order being updated |

### How order placement works (one transaction)
1. Validate the request: customer selected, restaurant selected, at least one item, quantities above zero.
2. Read item prices and availability from the database. The prices sent by the browser are ignored.
3. Check that every item is available and belongs to the selected restaurant.
4. `INSERT` the order with status `Pending`.
5. `INSERT` every row into `order_items` using the database prices.
6. `UPDATE orders` to set the total from `SUM(quantity * price)` over `order_items`.
7. `INSERT` the first row in `order_status_history`.
8. `COMMIT`. If anything fails, `ROLLBACK` undoes the whole order.

### Order status rules
Statuses: `Pending`, `Confirmed`, `Preparing`, `Out for Delivery`, `Delivered`, `Cancelled`.

| From | Allowed next status |
| :--- | :--- |
| Pending | Confirmed, Cancelled |
| Confirmed | Preparing, Cancelled |
| Preparing | Out for Delivery, Cancelled |
| Out for Delivery | Delivered |
| Delivered | none (final) |
| Cancelled | none (final) |

Invalid values are blocked by a database `CHECK` constraint. Invalid moves (for example Delivered → Pending) are rejected by the API. Every change is saved in `order_status_history`.

---

## 🚀 Getting Started Locally (Ubuntu)

### **Prerequisites**
- Python 3 with `venv`
- PostgreSQL
- Python packages: `flask`, `flask-cors`, `psycopg2-binary`

```bash
sudo apt update
sudo apt install -y postgresql python3 python3-venv python3-pip git
```

### **1. Clone the Repository**
```bash
git clone https://github.com/cs25b1013-png/FOOD-ORDERING-SYSTEM.git
cd FOOD-ORDERING-SYSTEM
```

### **2. Install Dependencies**
```bash
python3 -m venv venv
source venv/bin/activate
pip install flask flask-cors psycopg2-binary
```

### **3. Database Setup**
Set a password for the `postgres` user, create the database, and load the schema and sample data:
```bash
sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'choose_a_password';"
sudo -u postgres psql -c "CREATE DATABASE food_ordering_db;"
sudo -u postgres psql -d food_ordering_db -f schema.sql
```
`schema.sql` never drops tables. If you run it twice it stops with an "already exists" error. To start over, drop the database yourself and recreate it.

### **4. Configure Backend Credentials**
The password is **not stored in the code**. `app.py` reads the connection settings from environment variables:

| Variable | Default |
| :--- | :--- |
| `DB_HOST` | `localhost` |
| `DB_PORT` | `5432` |
| `DB_NAME` | `food_ordering_system_db` |
| `DB_USER` | `postgres` |
| `DB_PASSWORD` | empty (you must set it) |

```bash
export DB_NAME=food_ordering_db
export DB_PASSWORD='choose_a_password'
```

### **5. Run the Backend Server**
```bash
python app.py
```
The Flask REST API runs at `http://127.0.0.1:5000`. Keep this terminal open.

### **6. Launch the Dashboard**
Open `index.html` in a web browser (`xdg-open index.html`). The status pill at the top right turns green when the API is connected. An internet connection is needed for the Tailwind, Chart.js and Font Awesome CDN files.

---

## 🔌 API Endpoints Summary

All endpoints return JSON. Errors look like `{"error": "message"}` with a suitable status code (400 validation, 404 not found, 409 conflict, 500 server error).

### Dashboard and lookups
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/fleet` | Delivery agents, availability and vehicle IDs |
| `GET` | `/api/restaurants` | Restaurants with the count of menu items |
| `GET` | `/api/categories` | Revenue per food category (excludes cancelled orders) |
| `GET` | `/api/schema` | Lists all tables and columns (debug helper) |

### Customers
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/customers?q=` | List customers with order counts. `q` searches name, city or ID |
| `POST` | `/api/customers` | Add a customer (duplicate email returns 409) |
| `PUT` | `/api/customers/<id>` | Update a customer |
| `DELETE` | `/api/customers/<id>` | Delete a customer (409 if the customer has orders) |

### Menu
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/menu?hotel_id=&q=&available=1` | List items. Optional restaurant filter, name search, available-only |
| `POST` | `/api/menu` | Add a food item |
| `PUT` | `/api/menu/<id>` | Update name, category, price and availability |
| `PATCH` | `/api/menu/<id>` | Update only the price and/or availability |
| `DELETE` | `/api/menu/<id>` | Delete an item (409 if it appears in orders) |

### Orders
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/orders?status=` | Order list, optionally filtered by status |
| `POST` | `/api/orders` | Place an order. Body: `{"cust_id": 1, "hotel_id": 1, "items": [{"item_id": 1, "quantity": 2}]}`. Returns the new `order_id` and the server-calculated total |
| `GET` | `/api/orders/<id>` | Full order details: header, items and status history |
| `PUT` | `/api/orders/<id>/status` | Change status. Body: `{"status": "Confirmed"}` |

---

## ✅ Quick Test Checklist

- **Customers:** add, edit, search by name / ID / city, delete. Deleting a customer with orders is blocked.
- **Menu:** add, edit, change price, toggle availability, delete. Deleting an item used in orders is blocked. Negative prices are rejected.
- **Place Order:** order several items, then confirm the rows in `order_items` and that `orders.tot_amount` equals `SUM(quantity * price)`.
- **Status:** move Pending → Confirmed. Check that Confirmed → Pending, and any change from Delivered or Cancelled, is rejected.
- **Rollback demo in psql:**
  ```sql
  BEGIN;
  INSERT INTO orders (cust_id, hotel_id) VALUES (1, 1);
  INSERT INTO order_items (order_id, item_id, quantity, price)
    VALUES (currval('orders_order_id_seq'), 1, 0, 220);  -- fails: quantity CHECK
  ROLLBACK;
  SELECT COUNT(*) FROM orders;  -- unchanged
  ```

---

## 🔒 Security Notes

- Never commit database passwords. Use the `DB_PASSWORD` environment variable.
- All SQL uses parameterized queries to prevent SQL injection.
- Order totals are always calculated on the server from database prices. Prices sent by the browser are ignored.

---

## 🛠️ Built With

* **Backend:** Python (Flask), `flask-cors`, `psycopg2` (PostgreSQL adapter)
* **Frontend:** HTML5, Tailwind CSS, JavaScript (Fetch API), Chart.js, Font Awesome
* **Database:** PostgreSQL

## 📁 Project Files

| File | Purpose |
| :--- | :--- |
| `app.py` | Flask REST API and business logic (transactions, validation) |
| `index.html` | Single-page dashboard UI |
| `schema.sql` | Database tables, constraints and sample data |
| `README.md` | This documentation |
