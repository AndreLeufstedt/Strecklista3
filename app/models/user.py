from flask import current_app
from app.db import query_db, modify_db
from app.utils import format_dmy

class User:
    def __init__(self, row, reverse=False):
        if row:
            self.id = row['id']
            self.barcode = row['barcode']
            self.name = row['name']
            self.is_enabled = bool(row['enabled'])
            self.is_hidden = bool(row['hidden']) if ('hidden' in row.keys() and row['hidden'] is not None) else False
            self.image = row['image']
            self.notes = row['notes']
            self.created_at = row['created_at']
        else:
            self.id = None
            self.barcode = None
            self.name = None
            self.is_enabled = False
            self.is_hidden = False
            self.image = None
            self.notes = None
            self.created_at = None
        self.reverse = reverse

    def exists(self):
        return self.id is not None

    def enabled(self):
        return self.is_enabled

    def disabled(self):
        return not self.is_enabled

    def hidden(self):
        return self.is_hidden

    def hide(self):
        """Soft-delete / hide the user."""
        if self.exists():
            modify_db("UPDATE users SET hidden = 1 WHERE id = ?", [self.id])
            self.is_hidden = True
        return self.is_hidden

    def unhide(self):
        """Restore / unhide the user."""
        if self.exists():
            modify_db("UPDATE users SET hidden = 0 WHERE id = ?", [self.id])
            self.is_hidden = False
        return self.is_hidden

    def picture(self):
        if self.image:
            return self.image
        return None

    def debt(self):
        """Calculate the current total debt for the user."""
        if not self.exists():
            return 0.0
        row = query_db(
            "SELECT COALESCE(SUM(price), 0.0) AS total_debt FROM transactions WHERE user_id = ?",
            [self.id],
            one=True
        )
        return float(row['total_debt']) if row else 0.0

    def last_paid_id(self):
        """Fetch the transaction ID of the most recent balance settlement."""
        if not self.exists():
            return 0
        row = query_db(
            """SELECT id FROM transactions 
               WHERE user_id = ? AND (type = 'PAYMENT' OR price < 0 OR notes = 'paid')
               ORDER BY id DESC LIMIT 1""",
            [self.id],
            one=True
        )
        return int(row['id']) if row else 0

    def debt_per_category(self):
        """Calculate debt per category since the most recent settlement."""
        if not self.exists():
            return []
        last_id = self.last_paid_id()
        rows = query_db(
            """SELECT c.name, COALESCE(SUM(t.price), 0.0) AS debt
               FROM transactions t
               JOIN products p ON t.product_id = p.id
               JOIN categories c ON p.category_id = c.id
               WHERE t.user_id = ? AND t.id > ?
               GROUP BY c.id
               ORDER BY c.name ASC""",
            [self.id, last_id]
        )
        return [{'name': r['name'], 'debt': float(r['debt'])} for r in rows]

    def transactions(self, limit=11):
        """Retrieve recent transactions in reverse chronological order (newest first) for UI display."""
        if not self.exists():
            return []
        rows = query_db(
            """SELECT t.id, t.created_at AS added, t.price, t.type, t.notes, p.name
               FROM transactions t
               LEFT JOIN products p ON t.product_id = p.id
               WHERE t.user_id = ?
               ORDER BY t.id DESC LIMIT ?""",
            [self.id, limit]
        )
        result = []
        for r in rows:
            item_name = r['name'] or r['notes'] or r['type']
            result.append({
                'id': r['id'],
                'added': format_dmy(r['added']),
                'price': float(r['price']),
                'name': item_name,
                'notes': r['notes'],
                'type': r['type']
            })
        return result

    def enable(self, val=True):
        if self.exists():
            modify_db("UPDATE users SET enabled = ? WHERE id = ?", [1 if val else 0, self.id])
            self.is_enabled = bool(val)
        return self.is_enabled

    def disable(self):
        return self.enable(False)

    def update(self, name=None, image=None, notes=None):
        if not self.exists():
            return False
        updates = []
        args = []
        if name is not None and name.strip():
            updates.append("name = ?")
            args.append(name.strip())
            self.name = name.strip()
        if image is not None:
            updates.append("image = ?")
            args.append(image)
            self.image = image
        if notes is not None:
            updates.append("notes = ?")
            args.append(notes)
            self.notes = notes
        if updates:
            args.append(self.id)
            modify_db(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", args)
        return True

    @classmethod
    def get_by_barcode(cls, barcode):
        if not barcode:
            return None
        barcode_str = str(barcode).strip()
        reverse = False
        
        # Check special case for office food reversal barcode
        remove_jobbmat_code = current_app.config.get('REMOVE_JOBBMAT_BARCODE', 'Ta+bort+jobbmat')
        jobbmat_code = current_app.config.get('JOBBMAT_BARCODE', 'Jobbmat')
        
        if barcode_str == remove_jobbmat_code:
            barcode_str = jobbmat_code
            reverse = True

        row = query_db("SELECT * FROM users WHERE barcode = ?", [barcode_str], one=True)
        if row:
            return cls(row, reverse=reverse)
        return None

    @classmethod
    def get_by_id(cls, user_id):
        row = query_db("SELECT * FROM users WHERE id = ?", [user_id], one=True)
        return cls(row) if row else None

    @classmethod
    def all(cls, active_only=False, include_hidden=False):
        sql = "SELECT * FROM users"
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
        """Retrieve all soft-deleted / hidden users."""
        rows = query_db("SELECT * FROM users WHERE hidden = 1 ORDER BY name COLLATE NOCASE ASC")
        return [cls(r) for r in rows]

    @classmethod
    def search(cls, query_str, include_hidden=False, only_hidden=False):
        """Search users by name or barcode."""
        if not query_str or not query_str.strip():
            if only_hidden:
                return cls.all_hidden()
            return cls.all(include_hidden=include_hidden)
        term = f"%{query_str.strip()}%"
        if only_hidden:
            filter_sql = "AND hidden = 1"
        elif not include_hidden:
            filter_sql = "AND hidden = 0"
        else:
            filter_sql = ""
        rows = query_db(
            f"SELECT * FROM users WHERE (name LIKE ? OR barcode LIKE ?) {filter_sql} ORDER BY name COLLATE NOCASE ASC",
            [term, term]
        )
        return [cls(r) for r in rows]

    @classmethod
    def add(cls, barcode, name, image=None, notes=None):
        barcode_clean = str(barcode).strip()
        existing = cls.get_by_barcode(barcode_clean)
        if existing:
            # If an existing user was hidden and has no transactions, recycle and unhide
            if existing.hidden() and len(existing.transactions()) == 0:
                existing.unhide()
                existing.enable(True)
                modify_db(
                    "UPDATE users SET enabled = 1, hidden = 0, name = ?, image = ?, notes = ? WHERE id = ?",
                    [name.strip(), image, notes, existing.id]
                )
                return cls.get_by_id(existing.id)
            return None
        new_id = modify_db(
            "INSERT INTO users (barcode, name, enabled, hidden, image, notes) VALUES (?, ?, 1, 0, ?, ?)",
            [barcode_clean, name.strip(), image, notes]
        )
        return cls.get_by_id(new_id)
