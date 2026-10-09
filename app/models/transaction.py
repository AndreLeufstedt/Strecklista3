from app.db import query_db, modify_db

class Transaction:
    def __init__(self, row):
        if row:
            self.id = row['id']
            self.created_at = row['created_at']
            self.user_id = row['user_id']
            self.product_id = row['product_id']
            self.price = float(row['price'])
            self.type = row['type']
            self.notes = row['notes']
        else:
            self.id = None
            self.created_at = None
            self.user_id = None
            self.product_id = None
            self.price = 0.0
            self.type = 'PURCHASE'
            self.notes = None

    @classmethod
    def create_purchase(cls, user, product, price=None, notes=None):
        """Record a purchase transaction for a user."""
        if not user.exists() or not product.exists():
            return None

        actual_price = product.price if price is None else float(price)
        # If user has the reverse flag (e.g., meal reversal barcode), invert the price
        if getattr(user, 'reverse', False):
            actual_price = -actual_price

        tx_type = 'PURCHASE' if actual_price >= 0 else 'REFUND'
        new_id = modify_db(
            """INSERT INTO transactions (user_id, product_id, price, type, notes)
               VALUES (?, ?, ?, ?, ?)""",
            [user.id, product.id, actual_price, tx_type, notes]
        )
        row = query_db("SELECT * FROM transactions WHERE id = ?", [new_id], one=True)
        return cls(row)

    @classmethod
    def pay_debt(cls, user, notes='paid'):
        """Settle a user's debt by booking an offsetting payment transaction."""
        if not user.exists():
            return None
        debt = user.debt()
        new_id = modify_db(
            """INSERT INTO transactions (user_id, product_id, price, type, notes)
               VALUES (?, NULL, ?, 'PAYMENT', ?)""",
            [user.id, -debt, notes]
        )
        row = query_db("SELECT * FROM transactions WHERE id = ?", [new_id], one=True)
        return cls(row)

    @classmethod
    def undo_last(cls, user):
        """Undo the most recent transaction for the user."""
        if not user.exists():
            return False
        
        last_tx = query_db(
            "SELECT id FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            [user.id],
            one=True
        )
        if not last_tx:
            return False
            
        modify_db("DELETE FROM transactions WHERE id = ?", [last_tx['id']])
        return True
