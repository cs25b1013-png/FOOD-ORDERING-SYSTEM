# 🍕 Food Ordering System - Live Operations Portal

A full-stack food ordering and fleet management system built with **PostgreSQL**, **Python (Flask)**, and a **Tailwind CSS + Chart.js Dashboard UI**. 

This system models a real-world food delivery application divided across 3 operational domains: **User Identity & Fleet**, **Restaurant Catalog**, and **Order Fulfillment Analytics**.

---

## 📸 Application Architecture & Features

* **Live Analytics Dashboard:** Interactive Chart.js charts showing revenue distribution by food category and restaurant performance metrics.
* **Live Orders Ledger:** Real-time transaction history fetching customer order records, item sub-totals, and fulfillment status updates.
* **Logistics Fleet Manager:** Fleet status dashboard showing online/busy driver duty indicators and vehicle registration numbers.
* **Restaurant & Menu Catalog:** Merchant listings displaying ratings, cuisine types, and menu item pricing ranges.

---

## 🗄️ Database Schema & Ownership

The system runs on **PostgreSQL** with 8 relational tables normalized into 3 operational modules:

| Module | Table Name | Key Columns | Team Owner |
| :--- | :--- | :--- | :--- |
| **User & Fleet** | `USERS` | `user_id`, `first_name`, `last_name`, `email`, `phone_number` | **Member 1** |
| | `CUSTOMER` | `cust_id`, `street`, `city`, `state`, `pincode` | **Member 1** |
| | `DELIVERY_AGENT` | `agent_id`, `vehicle_no`, `license_id`, `is_available` | **Member 1** |
| **Catalog** | `RESTAURANT` | `hotel_id`, `restaurant_name`, `cuisine_type`, `rating` | **Member 2** |
| | `MENU_ITEM` | `item_id`, `hotel_id`, `category`, `price`, `item_name` | **Member 2** |
| **Transactions** | `ORDERS` | `order_id`, `hotel_id`, `cust_id`, `tot_amount` | **Member 3** |
| | `ORDER_DETAILS` | `order_details_id`, `order_id`, `item_id`, `quantity`, `sub_total` | **Member 3** |
| | `ORDER_STATUS_LOG` | `log_id`, `order_id`, `status_update`, `updated_at` | **Member 3** |

---

## 🚀 Getting Started Locally

### **Prerequisites**
- **Python 3.x**
- **PostgreSQL Database**
- Python Packages: `flask`, `flask-cors`, `psycopg2-binary`

### **1. Clone the Repository**
```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/food-ordering-system.git
cd food-ordering-system
```

### **2. Install Dependencies**
```bash
pip install flask flask-cors psycopg2-binary
```

### **3. Database Setup**
1. Open PostgreSQL (via `psql` or pgAdmin).
2. Create the database:
   ```sql
   CREATE DATABASE food_ordering_system_db;
   ```
3. Run your table creation (DDL) and sample data insertion scripts.

### **4. Configure Backend Credentials**
In `app.py`, update the database connection password on line 16:
```python
def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="food_ordering_system_db",
        user="postgres",
        password="YOUR_POSTGRES_PASSWORD",  # Put your local PostgreSQL password here
        port="5432"
    )
    return conn
```

### **5. Run the Backend Server**
```bash
python app.py
```
The Flask REST API will start running at `http://127.0.0.1:5000`.

### **6. Launch the Dashboard**
Double-click `index.html` to open the live UI in any web browser!

---

## 🔌 API Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/orders` | Retrieves live order history joined with customer & restaurant details |
| `GET` | `/api/fleet` | Retrieves delivery driver accounts, availability, and vehicle IDs |
| `GET` | `/api/restaurants` | Retrieves active restaurants and count of total menu items |

---

## 🛠️ Built With

* **Backend:** Python (Flask), `psycopg2` (PostgreSQL Adapter)
* **Frontend:** HTML5, Tailwind CSS, JavaScript (Fetch API), Chart.js
* **Database:** PostgreSQL
