import os
from decimal import Decimal
from datetime import date, datetime

import psycopg2
import psycopg2.errors
import psycopg2.extras
from flask import Flask, jsonify, request, abort
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
CORS(app)

# Credentials come from environment variables, so no password is stored in the code.
DB = dict(
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", 5432)),
    dbname=os.environ.get("DB_NAME", "food_ordering_system_db"),
    user=os.environ.get("DB_USER", "postgres"),
    password=os.environ.get("DB_PASSWORD", ""),
)

STATUSES = ["Pending", "Confirmed", "Preparing", "Out for Delivery", "Delivered", "Cancelled"]
# Allowed status changes. Delivered and Cancelled are final (empty list).
NEXT_STATUS = {
    "Pending": ["Confirmed", "Cancelled"],
    "Confirmed": ["Preparing", "Cancelled"],
    "Preparing": ["Out for Delivery", "Cancelled"],
    "Out for Delivery": ["Delivered"],
    "Delivered": [],
    "Cancelled": [],
}


# ---------------- database helpers ----------------
def get_connection():
    return psycopg2.connect(**DB)


def clean(rows):
    """Make rows JSON friendly (Decimal -> float, datetime -> text)."""
    result = []
    for r in rows:
        row = {}
        for k, v in r.items():
            if isinstance(v, Decimal):
                v = float(v)
            elif isinstance(v, (datetime, date)):
                v = v.isoformat(sep=" ")
            row[k] = v
        result.append(row)
    return result


def query(sql, params=None):
    """Run ONE statement as its own transaction (commit on success, rollback on error)."""
    conn = get_connection()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall() if cur.description else []
    finally:
        conn.close()
    return clean(rows)


# ---------------- validation helpers ----------------
def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, "Request body must be JSON")
    return data


def text(data, key, required=True, max_len=100):
    value = data.get(key)
    value = "" if value is None else str(value).strip()
    if required and not value:
        abort(400, f"{key} is required")
    if len(value) > max_len:
        abort(400, f"{key} must be at most {max_len} characters")
    return value or None


def positive_int(value, name):
    try:
        number = int(str(value))
    except ValueError:
        abort(400, f"{name} must be a whole number")
    if number <= 0:
        abort(400, f"{name} must be greater than zero")
    return number


def valid_price(value):
    try:
        price = Decimal(str(value))
    except Exception:
        abort(400, "Price must be a number")
    if not price.is_finite() or price <= 0 or price > 100000:
        abort(400, "Price must be greater than 0 and at most 100000")
    return price.quantize(Decimal("0.01"))


def valid_bool(value):
    if not isinstance(value, bool):
        abort(400, "is_available must be true or false")
    return value


def customer_fields(data):
    name = text(data, "cust_name")
    email = text(data, "email", max_len=120).lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        abort(400, "Invalid email address")
    phone = text(data, "phone", required=False, max_len=15)
    if phone and not (phone.isdigit() and 7 <= len(phone) <= 15):
        abort(400, "Phone must be 7-15 digits")
    city = text(data, "city", max_len=60)
    return name, email, phone, city


def menu_fields(data):
    name = text(data, "item_name")
    category = text(data, "category", max_len=50)
    price = valid_price(data.get("price"))
    available = valid_bool(data.get("is_available", True))
    return name, category, price, available


# ---------------- existing endpoints (kept) ----------------
@app.route("/api/fleet")
def fleet():
    return jsonify(query("""
        SELECT 'Agent #' || agent_id AS driver_name,
               is_available, vehicle_no, license_id
        FROM delivery_agent
        ORDER BY agent_id
    """))


@app.route("/api/restaurants")
def restaurants():
    # LEFT JOIN + COUNT + GROUP BY: restaurants with no items still show 0
    return jsonify(query("""
        SELECT r.hotel_id,
               r.restaurant_name,
               r.rating,
               r.cuisine_type,
               COUNT(m.item_id) AS total_items
        FROM restaurant r
        LEFT JOIN menu_item m ON m.hotel_id = r.hotel_id
        GROUP BY r.hotel_id, r.restaurant_name, r.rating, r.cuisine_type
        ORDER BY r.hotel_id
    """))


@app.route("/api/orders")
def orders():
    # Optional filter: /api/orders?status=Pending
    status = request.args.get("status", "").strip()
    if status and status not in STATUSES:
        abort(400, "Invalid status filter")
    return jsonify(query("""
        SELECT o.order_id, o.cust_id,
               c.cust_name AS customer_name,
               r.restaurant_name,
               o.order_date_time,
               o.tot_amount,
               o.status
        FROM orders o
        LEFT JOIN customer c   ON c.cust_id  = o.cust_id
        LEFT JOIN restaurant r ON r.hotel_id = o.hotel_id
        WHERE %(status)s = '' OR o.status = %(status)s
        ORDER BY o.order_date_time DESC, o.order_id DESC
    """, {"status": status}))


@app.route("/api/schema")
def schema():
    return jsonify(query("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
    """))


# ---------------- 1. customers (CRUD) ----------------
@app.route("/api/customers")
def list_customers():
    q = request.args.get("q", "").strip()
    return jsonify(query("""
        SELECT c.cust_id, c.cust_name, c.email, c.phone, c.city,
               COUNT(o.order_id) AS total_orders
        FROM customer c
        LEFT JOIN orders o ON o.cust_id = c.cust_id
        WHERE %(q)s = ''
           OR c.cust_name ILIKE %(like)s
           OR c.city ILIKE %(like)s
           OR c.cust_id::text = %(q)s
        GROUP BY c.cust_id
        ORDER BY c.cust_id
    """, {"q": q, "like": f"%{q}%"}))


@app.route("/api/customers", methods=["POST"])
def add_customer():
    values = customer_fields(body())
    row = query("""INSERT INTO customer (cust_name, email, phone, city)
                   VALUES (%s, %s, %s, %s) RETURNING cust_id""", values)[0]
    return jsonify(row), 201


@app.route("/api/customers/<int:cust_id>", methods=["PUT"])
def update_customer(cust_id):
    name, email, phone, city = customer_fields(body())
    rows = query("""UPDATE customer SET cust_name=%s, email=%s, phone=%s, city=%s
                    WHERE cust_id=%s RETURNING cust_id""",
                 (name, email, phone, city, cust_id))
    if not rows:
        abort(404, "Customer not found")
    return jsonify(rows[0])


@app.route("/api/customers/<int:cust_id>", methods=["DELETE"])
def delete_customer(cust_id):
    # Customers that have orders are blocked by the foreign key (see error handler below)
    rows = query("DELETE FROM customer WHERE cust_id=%s RETURNING cust_id", (cust_id,))
    if not rows:
        abort(404, "Customer not found")
    return jsonify(deleted=cust_id)


# ---------------- 2. menu items (CRUD) ----------------
@app.route("/api/menu")
def list_menu():
    hotel_id = request.args.get("hotel_id", "").strip()
    hotel_id = positive_int(hotel_id, "hotel_id") if hotel_id else None
    q = request.args.get("q", "").strip()
    only_available = request.args.get("available") == "1"
    return jsonify(query("""
        SELECT m.item_id, m.item_name, m.hotel_id, r.restaurant_name,
               m.category, m.price, m.is_available
        FROM menu_item m
        JOIN restaurant r ON r.hotel_id = m.hotel_id
        WHERE (%(hotel)s IS NULL OR m.hotel_id = %(hotel)s)
          AND m.item_name ILIKE %(like)s
          AND (NOT %(avail)s OR m.is_available)
        ORDER BY r.restaurant_name, m.category, m.item_name
    """, {"hotel": hotel_id, "like": f"%{q}%", "avail": only_available}))


@app.route("/api/menu", methods=["POST"])
def add_menu_item():
    data = body()
    hotel_id = positive_int(data.get("hotel_id"), "hotel_id")
    name, category, price, available = menu_fields(data)
    row = query("""INSERT INTO menu_item (hotel_id, item_name, category, price, is_available)
                   VALUES (%s, %s, %s, %s, %s) RETURNING item_id""",
                (hotel_id, name, category, price, available))[0]
    return jsonify(row), 201


@app.route("/api/menu/<int:item_id>", methods=["PUT"])
def update_menu_item(item_id):
    name, category, price, available = menu_fields(body())
    rows = query("""UPDATE menu_item SET item_name=%s, category=%s, price=%s, is_available=%s
                    WHERE item_id=%s RETURNING item_id""",
                 (name, category, price, available, item_id))
    if not rows:
        abort(404, "Menu item not found")
    return jsonify(rows[0])


@app.route("/api/menu/<int:item_id>", methods=["PATCH"])
def patch_menu_item(item_id):
    """Quick update of only the price and/or availability."""
    data = body()
    price = valid_price(data["price"]) if "price" in data else None
    available = valid_bool(data["is_available"]) if "is_available" in data else None
    if price is None and available is None:
        abort(400, "Send price and/or is_available")
    # COALESCE keeps the old value when the new one is NULL
    rows = query("""UPDATE menu_item
                    SET price = COALESCE(%s, price),
                        is_available = COALESCE(%s, is_available)
                    WHERE item_id=%s RETURNING item_id""", (price, available, item_id))
    if not rows:
        abort(404, "Menu item not found")
    return jsonify(rows[0])


@app.route("/api/menu/<int:item_id>", methods=["DELETE"])
def delete_menu_item(item_id):
    rows = query("DELETE FROM menu_item WHERE item_id=%s RETURNING item_id", (item_id,))
    if not rows:
        abort(404, "Menu item not found")
    return jsonify(deleted=item_id)


# ---------------- 3 + 4. place an order (one transaction) ----------------
@app.route("/api/orders", methods=["POST"])
def place_order():
    data = body()
    cust_id = positive_int(data.get("cust_id"), "cust_id")
    hotel_id = positive_int(data.get("hotel_id"), "hotel_id")
    items = data.get("items")
    if not isinstance(items, list) or not items:
        abort(400, "Add at least one item to the order")

    wanted = {}  # item_id -> quantity (duplicates are merged)
    for line in items:
        if not isinstance(line, dict):
            abort(400, "Invalid item entry")
        item_id = positive_int(line.get("item_id"), "item_id")
        wanted[item_id] = wanted.get(item_id, 0) + positive_int(line.get("quantity"), "quantity")
        if wanted[item_id] > 100:
            abort(400, "Quantity per item cannot exceed 100")

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT 1 FROM customer WHERE cust_id=%s", (cust_id,))
            if not cur.fetchone():
                abort(404, "Customer not found")
            cur.execute("SELECT 1 FROM restaurant WHERE hotel_id=%s", (hotel_id,))
            if not cur.fetchone():
                abort(404, "Restaurant not found")

            # Prices come from the database, never from the browser.
            # FOR SHARE stops the price changing until this transaction ends.
            cur.execute("""SELECT item_id, price, is_available, hotel_id
                           FROM menu_item WHERE item_id = ANY(%s) FOR SHARE""", (list(wanted),))
            found = {r["item_id"]: r for r in cur.fetchall()}
            for item_id in wanted:
                item = found.get(item_id)
                if item is None:
                    abort(404, f"Menu item {item_id} not found")
                if item["hotel_id"] != hotel_id:
                    abort(400, "All items must belong to the selected restaurant")
                if not item["is_available"]:
                    abort(400, f"Menu item {item_id} is not available")

            # 1. insert the order, 2. insert its items
            cur.execute("""INSERT INTO orders (cust_id, hotel_id, status, tot_amount)
                           VALUES (%s, %s, 'Pending', 0) RETURNING order_id""", (cust_id, hotel_id))
            order_id = cur.fetchone()["order_id"]
            for item_id, qty in wanted.items():
                cur.execute("""INSERT INTO order_items (order_id, item_id, quantity, price)
                               VALUES (%s, %s, %s, %s)""",
                            (order_id, item_id, qty, found[item_id]["price"]))

            # 3 + 4. total is calculated by the database from the stored prices
            cur.execute("""UPDATE orders
                           SET tot_amount = (SELECT COALESCE(SUM(quantity * price), 0)
                                             FROM order_items WHERE order_id = %s)
                           WHERE order_id = %s RETURNING tot_amount""", (order_id, order_id))
            total = cur.fetchone()["tot_amount"]
            cur.execute("""INSERT INTO order_status_history (order_id, old_status, new_status)
                           VALUES (%s, NULL, 'Pending')""", (order_id,))
        conn.commit()          # 5. everything succeeded
    except Exception:
        conn.rollback()        # anything failed: undo the whole order
        raise
    finally:
        conn.close()

    return jsonify(order_id=order_id, tot_amount=float(total), status="Pending"), 201


# ---------------- 5. order details and status ----------------
@app.route("/api/orders/<int:order_id>")
def order_details(order_id):
    header = query("""
        SELECT o.order_id, o.cust_id, c.cust_name AS customer_name, c.city,
               r.restaurant_name, o.order_date_time, o.tot_amount, o.status, o.agent_id
        FROM orders o
        LEFT JOIN customer c   ON c.cust_id  = o.cust_id
        LEFT JOIN restaurant r ON r.hotel_id = o.hotel_id
        WHERE o.order_id = %s""", (order_id,))
    if not header:
        abort(404, "Order not found")
    items = query("""
        SELECT m.item_name, oi.quantity, oi.price, oi.quantity * oi.price AS line_total
        FROM order_items oi
        JOIN menu_item m ON m.item_id = oi.item_id
        WHERE oi.order_id = %s ORDER BY oi.order_item_id""", (order_id,))
    history = query("""
        SELECT old_status, new_status, changed_at
        FROM order_status_history WHERE order_id = %s ORDER BY history_id""", (order_id,))
    return jsonify(order=header[0], items=items, history=history)


@app.route("/api/orders/<int:order_id>/status", methods=["PUT"])
def update_order_status(order_id):
    new_status = body().get("status")
    if new_status not in STATUSES:
        abort(400, "Invalid status")

    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT status FROM orders WHERE order_id=%s FOR UPDATE", (order_id,))
            row = cur.fetchone()
            if not row:
                abort(404, "Order not found")
            old_status = row["status"]
            if new_status not in NEXT_STATUS[old_status]:
                if not NEXT_STATUS[old_status]:
                    abort(400, f"A {old_status} order cannot be changed any more")
                abort(400, f"Cannot change status from {old_status} to {new_status}")
            cur.execute("UPDATE orders SET status=%s WHERE order_id=%s", (new_status, order_id))
            cur.execute("""INSERT INTO order_status_history (order_id, old_status, new_status)
                           VALUES (%s, %s, %s)""", (order_id, old_status, new_status))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return jsonify(order_id=order_id, old_status=old_status, status=new_status)


# ---------------- dashboard: revenue by category (JOIN + SUM + GROUP BY) ----------------
@app.route("/api/categories")
def category_revenue():
    return jsonify(query("""
        SELECT m.category, SUM(oi.quantity * oi.price) AS revenue
        FROM order_items oi
        JOIN menu_item m ON m.item_id = oi.item_id
        JOIN orders o    ON o.order_id = oi.order_id
        WHERE o.status <> 'Cancelled'
        GROUP BY m.category
        ORDER BY revenue DESC
    """))


# ---------------- error handling ----------------
@app.errorhandler(HTTPException)
def handle_http_error(e):
    return jsonify(error=e.description), e.code


@app.errorhandler(psycopg2.errors.UniqueViolation)
def handle_unique(e):
    return jsonify(error="Duplicate value: that record already exists (e.g. email or item name)"), 409


@app.errorhandler(psycopg2.errors.ForeignKeyViolation)
def handle_foreign_key(e):
    return jsonify(error="Operation blocked: this record is linked to other records "
                         "(e.g. a customer or menu item that is used in orders)"), 409


@app.errorhandler(psycopg2.errors.CheckViolation)
def handle_check(e):
    return jsonify(error="Value rejected by a database CHECK constraint"), 400


@app.errorhandler(Exception)
def handle_error(e):
    return jsonify(error=str(e)), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
