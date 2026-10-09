from flask import current_app
from app.db import query_db, modify_db
from app.models.category import Category
from app.models.setting import Setting

class Product:
    def __init__(self, row):
        if row:
            self.id = row['id']
            self.barcode = row['barcode']
            self.name = row['name']
            self.price = float(row['price'])
            self.category_id = row['category_id']
            self.is_enabled = bool(row['enabled'])
            self.is_hidden = bool(row['hidden']) if ('hidden' in row.keys() and row['hidden'] is not None) else False
            self.image = row['image']
            self.notes = row['notes']
            self.created_at = row['created_at']
        else:
            self.id = None
            self.barcode = None
            self.name = None
            self.price = 0.0
            self.category_id = None
            self.is_enabled = False
            self.is_hidden = False
            self.image = None
            self.notes = None
            self.created_at = None

    def exists(self):
        return self.id is not None

    def enabled(self):
        return self.is_enabled

    def hidden(self):
        return self.is_hidden

    def hide(self):
        """Soft-delete / hide the product."""
        if self.exists():
            modify_db("UPDATE products SET hidden = 1 WHERE id = ?", [self.id])
            self.is_hidden = True
        return self.is_hidden

    def unhide(self):
        """Restore / unhide the product."""
        if self.exists():
            modify_db("UPDATE products SET hidden = 0 WHERE id = ?", [self.id])
            self.is_hidden = False
        return self.is_hidden

    def picture(self):
        if self.image:
            return self.image
        return None

    def category(self):
        cat = Category.get_by_id(self.category_id)
        return cat.name if cat else "Unknown"

    def allowed_jobbmat(self):
        allowed = current_app.config.get('ALLOWED_JOBBMAT_CATEGORIES', ['Ickeöl'])
        return self.category() in allowed

    def public_price(self):
        """Calculate the standalone / guest price displayed when scanned without logging in."""
        surcharge = Setting.get_float('guest_surcharge', default=3.0)
        return self.price + surcharge

    def toplist(self, limit=10):
        """Retrieve users who purchased this product the most."""
        if not self.exists():
            return []
        rows = query_db(
            """SELECT u.id, u.name, u.barcode, COUNT(t.id) AS total
               FROM users u
               JOIN transactions t ON t.user_id = u.id
               WHERE t.product_id = ? AND t.price > 0
               GROUP BY u.id
               ORDER BY total DESC
               LIMIT ?""",
            [self.id, limit]
        )
        return [{'name': r['name'], 'barcode': r['barcode'], 'total': r['total']} for r in rows]

    def update(self, name=None, price=None, category_id=None, image=None, notes=None, enabled=None):
        if not self.exists():
            return False
        updates = []
        args = []
        if name is not None and name.strip():
            updates.append("name = ?")
            args.append(name.strip())
            self.name = name.strip()
        if price is not None:
            updates.append("price = ?")
            args.append(float(price))
            self.price = float(price)
        if category_id is not None:
            updates.append("category_id = ?")
            args.append(int(category_id))
            self.category_id = int(category_id)
        if image is not None:
            updates.append("image = ?")
            args.append(image)
            self.image = image
        if notes is not None:
            updates.append("notes = ?")
            args.append(notes)
            self.notes = notes
        if enabled is not None:
            updates.append("enabled = ?")
            args.append(1 if enabled else 0)
            self.is_enabled = bool(enabled)
            
        if updates:
            args.append(self.id)
            modify_db(f"UPDATE products SET {', '.join(updates)} WHERE id = ?", args)
        return True

    @classmethod
    def get_by_barcode(cls, barcode):
        if not barcode:
            return None
        barcode_clean = str(barcode).strip()
        row = query_db("SELECT * FROM products WHERE barcode = ?", [barcode_clean], one=True)
        return cls(row) if row else None

    @classmethod
    def get_by_id(cls, product_id):
        row = query_db("SELECT * FROM products WHERE id = ?", [product_id], one=True)
        return cls(row) if row else None

    @classmethod
    def all(cls, active_only=False, include_hidden=False):
        sql = "SELECT * FROM products"
        conditions = []
        if not include_hidden:
            conditions.append("hidden = 0")
        if active_only:
            conditions.append("enabled = 1")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY name COLLATE NOCASE ASC"
        rows = query_db(sql)
        return [cls(r) for r in rows]

    @classmethod
    def all_hidden(cls):
        """Retrieve all soft-deleted / hidden products."""
        rows = query_db("SELECT * FROM products WHERE hidden = 1 ORDER BY name COLLATE NOCASE ASC")
        return [cls(r) for r in rows]

    @classmethod
    def search(cls, query_str, include_hidden=False, only_hidden=False):
        """Search products by name, barcode, or category name."""
        if not query_str or not query_str.strip():
            if only_hidden:
                return cls.all_hidden()
            return cls.all(include_hidden=include_hidden)
        term = f"%{query_str.strip()}%"
        if only_hidden:
            filter_sql = "AND p.hidden = 1"
        elif not include_hidden:
            filter_sql = "AND p.hidden = 0"
        else:
            filter_sql = ""
        rows = query_db(
            f"""SELECT p.* FROM products p
               LEFT JOIN categories c ON p.category_id = c.id
               WHERE (p.name LIKE ? OR p.barcode LIKE ? OR c.name LIKE ?) {filter_sql}
               ORDER BY p.name COLLATE NOCASE ASC""",
            [term, term, term]
        )
        return [cls(r) for r in rows]

    @classmethod
    def add(cls, barcode, name, price, category_id, image=None, notes=None):
        barcode_clean = str(barcode).strip()
        existing = cls.get_by_barcode(barcode_clean)
        if existing:
            # Check transaction count for this product
            tx_count_row = query_db("SELECT COUNT(id) AS cnt FROM transactions WHERE product_id = ?", [existing.id], one=True)
            tx_count = tx_count_row['cnt'] if tx_count_row else 0
            if existing.hidden() and tx_count == 0:
                existing.unhide()
                existing.update(name=name, price=price, category_id=category_id, image=image, notes=notes, enabled=1)
                return cls.get_by_id(existing.id)
            return None
        new_id = modify_db(
            "INSERT INTO products (barcode, name, price, category_id, enabled, hidden, image, notes) VALUES (?, ?, ?, ?, 1, 0, ?, ?)",
            [barcode_clean, name.strip(), float(price), int(category_id), image, notes]
        )
        return cls.get_by_id(new_id)
