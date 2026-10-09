# Database Schema – Strecklistan 3

This document describes the database structure for **Strecklistan 3**. The database runs on pure **SQLite3** with Foreign Keys enabled and optimized indexes for high performance and auditability.

---

## Tables Overview

1. **`categories`** – Product categories (e.g., *Beer*, *Non-beer*, snacks, etc.)
2. **`users`** – User accounts and their barcodes
3. **`products`** – Items, prices, and associated categories
4. **`transactions`** – Complete ledger of all purchases, payments, and refunds/undo operations
5. **`settings`** – Key-value application configurations (timeouts, guest surcharges, etc.)

---

## 1. `categories`

Stores available product categories. Used for stats grouping, export settlements, and account restrictions (such as office meal policies).

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Unique category ID |
| `name` | `TEXT` | `NOT NULL UNIQUE` | Category name (e.g. "Beer", "Non-beer") |

---

## 2. `users`

Stores user accounts.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Internal ID |
| `barcode` | `TEXT` | `NOT NULL UNIQUE` | Barcode, card number, or identifier string |
| `name` | `TEXT` | `NOT NULL` | Display name of the user |
| `enabled` | `INTEGER` | `NOT NULL DEFAULT 1` | `1` = active, `0` = disabled/suspended |
| `hidden` | `INTEGER` | `NOT NULL DEFAULT 0` | `1` = hidden/soft-deleted, `0` = visible |
| `image` | `TEXT` | `DEFAULT NULL` | Relative path or filename to profile image |
| `notes` | `TEXT` | `DEFAULT NULL` | Optional admin notes |
| `created_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Account creation timestamp |

**Indexes:**
* Unique index on `barcode` for O(1) scanner lookups.

---

## 3. `products`

Stores all purchasable items.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Internal ID |
| `barcode` | `TEXT` | `NOT NULL UNIQUE` | Item barcode (EAN or custom) |
| `name` | `TEXT` | `NOT NULL` | Product name |
| `price` | `REAL` | `NOT NULL` | Standard member price in SEK |
| `category_id` | `INTEGER` | `NOT NULL REFERENCES categories(id)` | Foreign key to `categories` |
| `enabled` | `INTEGER` | `NOT NULL DEFAULT 1` | `1` = active in inventory, `0` = discontinued |
| `hidden` | `INTEGER` | `NOT NULL DEFAULT 0` | `1` = hidden/soft-deleted, `0` = visible |
| `image` | `TEXT` | `DEFAULT NULL` | Relative path to product image |
| `notes` | `TEXT` | `DEFAULT NULL` | Optional notes |
| `created_at` | `TIMESTAMP` | `DEFAULT CURRENT_TIMESTAMP` | Creation timestamp |

**Pricing Note:**
* **Member Price:** When a user logs in and buys, the exact `price` is charged.
* **Public / Standalone Price:** When a product is scanned directly from the home screen without an active user session, `price + guest_surcharge` is displayed.

**Indexes:**
* Unique index on `barcode` for O(1) scanner lookups.
* Index on `category_id` for category-based filtering and statistics.

---

## 4. `transactions`

The transaction ledger. Records all events.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | Transaction ID |
| `created_at` | `TIMESTAMP` | `NOT NULL DEFAULT CURRENT_TIMESTAMP` | Timestamp of event |
| `user_id` | `INTEGER` | `NOT NULL REFERENCES users(id)` | User associated with transaction |
| `product_id` | `INTEGER` | `REFERENCES products(id)` | Purchased product (NULL for balance payments) |
| `price` | `REAL` | `NOT NULL` | Amount (+ for purchase, - for payment/credit) |
| `type` | `TEXT` | `NOT NULL DEFAULT 'PURCHASE'` | `'PURCHASE'`, `'PAYMENT'`, `'REFUND'` |
| `notes` | `TEXT` | `DEFAULT NULL` | Free text / system info |

**Indexes:**
* Index on `user_id` – Fast user debt calculation and recent history.
* Index on `created_at` – Fast time-range querying for charts and stats.
* Index on `product_id` – Fast aggregation for top-seller toplists.

---

## 5. `settings`

Stores dynamic system settings that can be customized via the administration interface without restarting the app.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `key` | `TEXT` | `PRIMARY KEY` | Configuration key |
| `value` | `TEXT` | `NOT NULL` | Serialized setting value |

Default keys:
* `user_timeout`: Inactivity timeout in seconds on the user screen before logging out (default: `15`).
* `confirm_timeout`: Time in seconds the confirmation screen is shown before auto-resetting (default: `3`).
* `guest_surcharge`: Surcharge added to member price when displaying product price to guests (default: `3`).

---

## Debt Calculation Logic

1. **Total Debt:**
   ```sql
   SELECT COALESCE(SUM(price), 0.0) AS debt
   FROM transactions
   WHERE user_id = :user_id;
   ```

2. **Last Payment ID:**
   ```sql
   SELECT id FROM transactions
   WHERE user_id = :user_id AND (type = 'PAYMENT' OR price < 0 OR notes = 'paid')
   ORDER BY id DESC LIMIT 1;
   ```

3. **Debt Per Category (since last payment):**
   ```sql
   SELECT c.name, COALESCE(SUM(t.price), 0.0) AS debt
   FROM transactions t
   JOIN products p ON t.product_id = p.id
   JOIN categories c ON p.category_id = c.id
   WHERE t.user_id = :user_id AND t.id > :last_payment_id
   GROUP BY c.id;
   ```

---

## DDL Script (`schema.sql`)

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    image TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    enabled INTEGER NOT NULL DEFAULT 1,
    image TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER NOT NULL REFERENCES users(id),
    product_id INTEGER REFERENCES products(id),
    price REAL NOT NULL,
    type TEXT NOT NULL DEFAULT 'PURCHASE',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_barcode ON users(barcode);
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_transactions_product ON transactions(product_id);
```
