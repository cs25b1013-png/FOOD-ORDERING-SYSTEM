-- Food Ordering System: schema + sample data
-- Run this on a NEW, EMPTY database (see README steps). It never drops anything:
-- if a table already exists, the script stops with an error instead of overwriting it.
-- Column names (hotel_id, cust_id, tot_amount, order_date_time ...) match your existing app.py.

BEGIN;

-- 1. customer: one customer -> many orders
CREATE TABLE customer (
    cust_id    SERIAL PRIMARY KEY,
    cust_name  VARCHAR(100) NOT NULL,
    email      VARCHAR(120) NOT NULL UNIQUE,          -- UNIQUE: no duplicate emails
    phone      VARCHAR(15)  CHECK (phone ~ '^[0-9]{7,15}$'),   -- NULL allowed (optional)
    city       VARCHAR(60)  NOT NULL
);

-- 2. restaurant: one restaurant -> many menu items and many orders
CREATE TABLE restaurant (
    hotel_id        SERIAL PRIMARY KEY,
    restaurant_name VARCHAR(100) NOT NULL UNIQUE,
    rating          NUMERIC(2,1) CHECK (rating BETWEEN 0 AND 5),
    cuisine_type    VARCHAR(50)
);

-- 3. menu_item: belongs to exactly one restaurant
CREATE TABLE menu_item (
    item_id      SERIAL PRIMARY KEY,
    hotel_id     INT NOT NULL REFERENCES restaurant(hotel_id) ON DELETE RESTRICT,
    item_name    VARCHAR(100) NOT NULL,
    category     VARCHAR(50)  NOT NULL,
    price        NUMERIC(8,2) NOT NULL CHECK (price > 0 AND price <= 100000),
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (hotel_id, item_name)                      -- same dish name only once per restaurant
);

-- 4. delivery_agent (unchanged columns used by /api/fleet)
CREATE TABLE delivery_agent (
    agent_id     SERIAL PRIMARY KEY,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    vehicle_no   VARCHAR(20) NOT NULL UNIQUE,
    license_id   VARCHAR(30) NOT NULL UNIQUE
);

-- 5. orders: header row of an order
CREATE TABLE orders (
    order_id        SERIAL PRIMARY KEY,
    cust_id         INT NOT NULL REFERENCES customer(cust_id)   ON DELETE RESTRICT,
    hotel_id        INT NOT NULL REFERENCES restaurant(hotel_id) ON DELETE RESTRICT,
    agent_id        INT REFERENCES delivery_agent(agent_id) ON DELETE SET NULL,  -- NULL = not assigned yet
    order_date_time TIMESTAMP NOT NULL DEFAULT NOW(),
    tot_amount      NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (tot_amount >= 0),
    status          VARCHAR(20) NOT NULL DEFAULT 'Pending'
                    CHECK (status IN ('Pending','Confirmed','Preparing',
                                      'Out for Delivery','Delivered','Cancelled'))
);

-- 6. order_items: junction table -> many-to-many between orders and menu_item
CREATE TABLE order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id      INT NOT NULL REFERENCES orders(order_id)    ON DELETE CASCADE,
    item_id       INT NOT NULL REFERENCES menu_item(item_id)  ON DELETE RESTRICT,
    quantity      INT NOT NULL CHECK (quantity > 0),
    price         NUMERIC(8,2) NOT NULL CHECK (price >= 0),   -- price at the time of ordering
    UNIQUE (order_id, item_id)                                -- an item appears once per order
);

-- 7. order_status_history: audit trail (old_status is NULL for the first row of an order)
CREATE TABLE order_status_history (
    history_id SERIAL PRIMARY KEY,
    order_id   INT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    old_status VARCHAR(20),
    new_status VARCHAR(20) NOT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_status   ON orders(status);
CREATE INDEX idx_orders_cust     ON orders(cust_id);
CREATE INDEX idx_items_item      ON order_items(item_id);

-- ---------------- sample data ----------------
INSERT INTO customer (cust_name, email, phone, city) VALUES
 ('Aarav Sharma', 'aarav@example.com', '9876543210', 'Chennai'),
 ('Priya Nair',   'priya@example.com', '9876501234', 'Bengaluru'),
 ('Rahul Verma',  'rahul@example.com', NULL,         'Chennai'),
 ('Sneha Iyer',   'sneha@example.com', '9123456780', 'Hyderabad'),
 ('Karthik Raj',  'karthik@example.com','9988776655','Mumbai');

INSERT INTO restaurant (restaurant_name, rating, cuisine_type) VALUES
 ('Spice Garden',  4.5, 'North Indian'),
 ('Tiffin Express',4.2, 'South Indian'),
 ('Burger Hub',    4.0, 'Fast Food');

INSERT INTO menu_item (hotel_id, item_name, category, price, is_available) VALUES
 (1,'Paneer Butter Masala','Main Course',220,TRUE),
 (1,'Butter Naan','Bread',40,TRUE),
 (1,'Paneer Tikka','Starter',180,TRUE),
 (1,'Dal Makhani','Main Course',190,TRUE),
 (2,'Masala Dosa','Tiffin',90,TRUE),
 (2,'Idli Sambar','Tiffin',60,TRUE),
 (2,'Filter Coffee','Beverage',35,TRUE),
 (2,'Medu Vada','Starter',50,FALSE),
 (3,'Veg Burger','Fast Food',120,TRUE),
 (3,'French Fries','Fast Food',80,TRUE),
 (3,'Cold Coffee','Beverage',95,TRUE);

INSERT INTO delivery_agent (is_available, vehicle_no, license_id) VALUES
 (TRUE,'TN09AB1234','DL-TN-0001'),
 (FALSE,'TN10CD5678','DL-TN-0002'),
 (TRUE,'KA03EF9012','DL-KA-0003'),
 (TRUE,'MH12GH3456','DL-MH-0004');

-- 4 sample orders (order_id 1..4 on a fresh database)
INSERT INTO orders (cust_id, hotel_id, agent_id, order_date_time, status) VALUES
 (1, 1, 1,    NOW() - INTERVAL '3 days', 'Delivered'),
 (2, 2, 2,    NOW() - INTERVAL '2 hours','Out for Delivery'),
 (3, 3, NULL, NOW() - INTERVAL '10 minutes','Pending'),
 (4, 1, NULL, NOW() - INTERVAL '1 day',  'Cancelled');

-- item prices are copied from menu_item (price snapshot)
INSERT INTO order_items (order_id, item_id, quantity, price)
SELECT v.order_id, m.item_id, v.qty, m.price
FROM (VALUES (1,1,2),(1,2,3),(2,5,2),(2,7,2),(3,9,1),(3,10,1),(3,11,1),(4,3,1),(4,4,1))
     AS v(order_id, item_id, qty)
JOIN menu_item m ON m.item_id = v.item_id;

-- totals calculated by the database from order_items
UPDATE orders o
SET tot_amount = (SELECT COALESCE(SUM(quantity * price), 0) FROM order_items WHERE order_id = o.order_id);

INSERT INTO order_status_history (order_id, old_status, new_status) VALUES
 (1,NULL,'Pending'),(1,'Pending','Confirmed'),(1,'Confirmed','Preparing'),
 (1,'Preparing','Out for Delivery'),(1,'Out for Delivery','Delivered'),
 (2,NULL,'Pending'),(2,'Pending','Confirmed'),(2,'Confirmed','Preparing'),(2,'Preparing','Out for Delivery'),
 (3,NULL,'Pending'),
 (4,NULL,'Pending'),(4,'Pending','Cancelled');

COMMIT;
