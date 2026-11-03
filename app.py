from decimal import Decimal
from datetime import date, datetime

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB = dict(
    host="localhost",
    port=5432,
    dbname="food_ordering_system_db",
    user="postgres",              # <- change if different
    password="Cs25b10##",     # <- change
)

def query(sql):
    conn = psycopg2.connect(**DB)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
    finally:
        conn.close()
    clean = []
    for r in rows:
        row = {}
        for k, v in r.items():
            if isinstance(v, Decimal):
                v = float(v)
            elif isinstance(v, (datetime, date)):
                v = v.isoformat(sep=" ")
            row[k] = v
        clean.append(row)
    return clean

# ---- Delivery fleet (uses only columns that exist in delivery_agent) ----
@app.route("/api/fleet")
def fleet():
    return jsonify(query("""
        SELECT 'Agent #' || agent_id AS driver_name,
               is_available,
               vehicle_no,
               license_id
        FROM delivery_agent
        ORDER BY agent_id
    """))

# ---- Restaurants (assumes a table named hotel; see note below) ----
@app.route("/api/restaurants")
def restaurants():
    return jsonify(query("""
        SELECT r.restaurant_name  AS restaurant_name,
               r.rating,
               r.cuisine_type,
               COUNT(m.item_id) AS total_items
        FROM restaurant r
        LEFT JOIN menu_item m ON m.hotel_id = r.hotel_id
        GROUP BY r.hotel_id, r.restaurant_name, r.rating, r.cuisine_type
        ORDER BY r.hotel_id
    """))

# ---- Orders (assumes orders has cust_id, hotel_id, order_date_time, tot_amount) ----
@app.route("/api/orders")
def orders():
    return jsonify(query("""
        SELECT o.order_id,
               'Customer #' || c.cust_id || ' (' || c.city || ')' AS customer_name,
               r.restaurant_name AS restaurant_name,
               o.order_date_time,
               o.tot_amount
        FROM orders o
        JOIN customer c ON c.cust_id  = o.cust_id
        JOIN restaurant r    ON r.hotel_id = o.hotel_id
        ORDER BY o.order_date_time DESC
    """))

# ---- Helper: lists every table and column so we can fix any wrong guess ----
@app.route("/api/schema")
def schema():
    return jsonify(query("""
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
    """))

@app.errorhandler(Exception)
def handle_error(e):
    return jsonify(error=str(e)), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)