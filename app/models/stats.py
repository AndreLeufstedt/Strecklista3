from flask import current_app
from app.db import query_db
from app.models.user import User
from app.utils import format_dmy

class Stats:
    @classmethod
    def _jobbmat_barcode(cls):
        return current_app.config.get('JOBBMAT_BARCODE', 'Jobbmat')

    @classmethod
    def top_product(cls):
        """Retrieve the most purchased product (excluding office food account)."""
        row = query_db(
            """SELECT p.name, COUNT(t.id) AS count
               FROM products p
               JOIN transactions t ON p.id = t.product_id
               JOIN users u ON u.id = t.user_id
               WHERE u.barcode != ? AND t.price > 0
               GROUP BY p.id
               ORDER BY count DESC LIMIT 1""",
            [cls._jobbmat_barcode()],
            one=True
        )
        if row:
            return (row['name'], int(row['count']))
        return ("None", 0)

    @classmethod
    def top_user_debt(cls):
        """Retrieve the user with the highest debt right now."""
        now_list = cls.toplist_user_now()
        if now_list:
            return now_list[0]
        return None

    @classmethod
    def top_user_total(cls):
        """Retrieve the user with the most total purchases all-time."""
        row = query_db(
            """SELECT u.name, SUM(t.price) AS total
               FROM transactions t
               JOIN users u ON u.id = t.user_id
               WHERE t.price > 0 AND u.barcode != ?
               GROUP BY u.id
               ORDER BY total DESC LIMIT 1""",
            [cls._jobbmat_barcode()],
            one=True
        )
        if row:
            return (row['name'], float(row['total']))
        return ("None", 0.0)

    @classmethod
    def total_four_weeks(cls):
        """Calculate total purchases in the last 4 weeks (28 days)."""
        row = query_db(
            """SELECT COALESCE(SUM(t.price), 0.0) AS total
               FROM transactions t
               JOIN users u ON u.id = t.user_id
               WHERE t.price > 0 
                 AND date(t.created_at) > date('now', '-28 days')
                 AND u.barcode != ?""",
            [cls._jobbmat_barcode()],
            one=True
        )
        return float(row['total']) if row else 0.0

    @classmethod
    def timeseries(cls):
        """Retrieve timeseries data for graph plotting (day, category, total)."""
        rows = query_db(
            """SELECT date(t.created_at) AS day, c.name AS category, SUM(t.price) AS total
               FROM transactions t
               JOIN products p ON t.product_id = p.id
               JOIN categories c ON p.category_id = c.id
               JOIN users u ON u.id = t.user_id
               WHERE t.price > 0 AND u.barcode != ?
               GROUP BY c.id, date(t.created_at)
               ORDER BY day ASC""",
            [cls._jobbmat_barcode()]
        )
        return [(r['day'], r['category'], float(r['total'])) for r in rows]

    @classmethod
    def toplist_user_now(cls, limit=3):
        """Top users with highest debt currently."""
        users = User.all()
        users = [u for u in users if u.barcode != cls._jobbmat_barcode()]
        users.sort(key=lambda u: u.debt(), reverse=True)
        return users[:limit]

    @classmethod
    def toplist_user_alltime(cls, limit=3):
        """Top users by total purchase amount all-time."""
        rows = query_db(
            """SELECT u.name, COUNT(t.id) AS count, SUM(t.price) AS total
               FROM transactions t
               JOIN users u ON u.id = t.user_id
               WHERE t.price > 0 AND u.barcode != ?
               GROUP BY u.id
               ORDER BY total DESC LIMIT ?""",
            [cls._jobbmat_barcode(), limit]
        )
        return [{'name': r['name'], 'count': r['count'], 'total': float(r['total'])} for r in rows]

    @classmethod
    def toplist_product(cls, category_id, limit=3):
        """Top products for a specific category."""
        rows = query_db(
            """SELECT p.name, COUNT(t.id) AS count, SUM(t.price) AS total
               FROM transactions t
               JOIN products p ON t.product_id = p.id
               WHERE p.category_id = ? AND t.price > 0
               GROUP BY p.id
               ORDER BY count DESC LIMIT ?""",
            [category_id, limit]
        )
        return [{'name': r['name'], 'count': r['count'], 'total': float(r['total'])} for r in rows]

    @classmethod
    def toplist_user_by_category(cls, category_id, limit=3):
        """Top users for a specific category."""
        rows = query_db(
            """SELECT u.name, COUNT(t.id) AS count, SUM(t.price) AS total
               FROM transactions t
               JOIN products p ON t.product_id = p.id
               JOIN users u ON u.id = t.user_id
               WHERE p.category_id = ? AND t.price > 0 AND u.barcode != ?
               GROUP BY u.id
               ORDER BY total DESC LIMIT ?""",
            [category_id, cls._jobbmat_barcode(), limit]
        )
        return [{'name': r['name'], 'count': r['count'], 'total': float(r['total'])} for r in rows]

    @classmethod
    def total_all_time(cls):
        """Calculate total amount of all purchases all-time."""
        row = query_db(
            """SELECT COALESCE(SUM(t.price), 0.0) AS total
               FROM transactions t
               JOIN users u ON u.id = t.user_id
               WHERE t.price > 0 AND u.barcode != ?""",
            [cls._jobbmat_barcode()],
            one=True
        )
        return float(row['total']) if row else 0.0

    @classmethod
    def total_purchases_count(cls):
        """Count total purchases all-time."""
        row = query_db(
            """SELECT COUNT(t.id) AS count
               FROM transactions t
               JOIN users u ON u.id = t.user_id
               WHERE t.price > 0 AND u.barcode != ?""",
            [cls._jobbmat_barcode()],
            one=True
        )
        return int(row['count']) if row else 0

    @classmethod
    def user_summary_list(cls, search_query=None):
        """List active users with aggregate stats for the statistics overview."""
        params = [cls._jobbmat_barcode()]
        where_filter = ""
        if search_query and search_query.strip():
            where_filter = "AND (u.name LIKE ? OR u.barcode LIKE ?)"
            term = f"%{search_query.strip()}%"
            params.extend([term, term])

        rows = query_db(
            f"""SELECT 
                   u.id, 
                   u.name, 
                   u.barcode, 
                   u.image,
                   COUNT(CASE WHEN t.price > 0 THEN t.id END) AS items_count,
                   COALESCE(SUM(CASE WHEN t.price > 0 THEN t.price ELSE 0.0 END), 0.0) AS total_spent
               FROM users u
               LEFT JOIN transactions t ON u.id = t.user_id
               WHERE u.hidden = 0 AND u.barcode != ? {where_filter}
               GROUP BY u.id
               ORDER BY total_spent DESC, u.name COLLATE NOCASE ASC""",
            params
        )

        users_stats = []
        for r in rows:
            debt_row = query_db(
                "SELECT COALESCE(SUM(price), 0.0) AS debt FROM transactions WHERE user_id = ?",
                [r['id']],
                one=True
            )
            debt = float(debt_row['debt']) if debt_row else 0.0
            users_stats.append({
                'id': r['id'],
                'name': r['name'],
                'barcode': r['barcode'],
                'image': r['image'],
                'items_count': int(r['items_count']),
                'total_spent': float(r['total_spent']),
                'debt': debt
            })
        return users_stats

    @classmethod
    def user_product_breakdown(cls, user_id):
        """Get every product purchased by a specific user with quantity, total sum, and last purchase date."""
        rows = query_db(
            """SELECT 
                   p.id,
                   p.name,
                   p.barcode,
                   p.price AS current_price,
                   c.name AS category_name,
                   COUNT(t.id) AS count,
                   COALESCE(SUM(t.price), 0.0) AS total,
                   MAX(t.created_at) AS last_bought
               FROM transactions t
               JOIN products p ON t.product_id = p.id
               JOIN categories c ON p.category_id = c.id
               WHERE t.user_id = ? AND t.price > 0
               GROUP BY p.id
               ORDER BY count DESC, total DESC, p.name COLLATE NOCASE ASC""",
            [user_id]
        )
        return [{
            'id': r['id'],
            'name': r['name'],
            'barcode': r['barcode'],
            'current_price': float(r['current_price']),
            'category_name': r['category_name'],
            'count': int(r['count']),
            'total': float(r['total']),
            'last_bought': r['last_bought']
        } for r in rows]

    @classmethod
    def user_category_breakdown(cls, user_id):
        """Get spending per category for a specific user."""
        rows = query_db(
            """SELECT 
                   c.name AS category_name,
                   COUNT(t.id) AS count,
                   COALESCE(SUM(t.price), 0.0) AS total
               FROM transactions t
               JOIN products p ON t.product_id = p.id
               JOIN categories c ON p.category_id = c.id
               WHERE t.user_id = ? AND t.price > 0
               GROUP BY c.id
               ORDER BY total DESC""",
            [user_id]
        )
        return [{
            'category_name': r['category_name'],
            'count': int(r['count']),
            'total': float(r['total'])
        } for r in rows]

    @classmethod
    def user_recent_purchases(cls, user_id, limit=20):
        """Get the most recent purchase transactions for a user."""
        rows = query_db(
            """SELECT 
                   t.id,
                   t.price,
                   t.created_at,
                   p.name AS product_name,
                   c.name AS category_name
               FROM transactions t
               JOIN products p ON t.product_id = p.id
               JOIN categories c ON p.category_id = c.id
               WHERE t.user_id = ? AND t.price > 0
               ORDER BY t.id DESC
               LIMIT ?""",
            [user_id, limit]
        )
        return [{
            'id': r['id'],
            'price': float(r['price']),
            'created_at': format_dmy(r['created_at']),
            'product_name': r['product_name'],
            'category_name': r['category_name']
        } for r in rows]

    @classmethod
    def user_favorite_product(cls, user_id):
        """Get the favorite product (most purchased) for a user."""
        row = query_db(
            """SELECT p.name, COUNT(t.id) AS count, SUM(t.price) AS total
               FROM transactions t
               JOIN products p ON t.product_id = p.id
               WHERE t.user_id = ? AND t.price > 0
               GROUP BY p.id
               ORDER BY count DESC, total DESC
               LIMIT 1""",
            [user_id],
            one=True
        )
        if row:
            return {'name': row['name'], 'count': int(row['count']), 'total': float(row['total'])}
        return None

    @classmethod
    def purchases_by_date_range(cls, start_date_str, end_date_str):
        """Retrieve all individual purchases within a date range (inclusive)."""
        start_dt = f"{start_date_str} 00:00:00"
        end_dt = f"{end_date_str} 23:59:59"

        rows = query_db(
            """SELECT 
                   t.id,
                   t.created_at,
                   t.price,
                   t.type,
                   t.notes,
                   u.id AS user_id,
                   u.name AS user_name,
                   u.barcode AS user_barcode,
                   p.id AS product_id,
                   p.name AS product_name,
                   p.barcode AS product_barcode,
                   c.id AS category_id,
                   COALESCE(c.name, 'Okänd') AS category_name
               FROM transactions t
               JOIN users u ON t.user_id = u.id
               JOIN products p ON t.product_id = p.id
               LEFT JOIN categories c ON p.category_id = c.id
               WHERE t.created_at >= ? AND t.created_at <= ? AND t.price > 0
               ORDER BY t.created_at DESC, t.id DESC""",
            [start_dt, end_dt]
        )
        return [{
            'id': r['id'],
            'created_at': format_dmy(r['created_at']),
            'price': float(r['price']),
            'type': r['type'],
            'notes': r['notes'],
            'user_id': r['user_id'],
            'user_name': r['user_name'],
            'user_barcode': r['user_barcode'],
            'product_id': r['product_id'],
            'product_name': r['product_name'],
            'product_barcode': r['product_barcode'],
            'category_id': r['category_id'],
            'category_name': r['category_name']
        } for r in rows]

    @classmethod
    def purchases_summary_by_date_range(cls, start_date_str, end_date_str, include_zero=False):
        """Calculate aggregated purchase metrics within a date range (inclusive), sorted most to least purchased."""
        start_dt = f"{start_date_str} 00:00:00"
        end_dt = f"{end_date_str} 23:59:59"

        # Overall metrics
        summary_row = query_db(
            """SELECT 
                   COALESCE(SUM(t.price), 0.0) AS total_amount,
                   COUNT(t.id) AS total_count,
                   COUNT(DISTINCT t.user_id) AS unique_users
               FROM transactions t
               WHERE t.created_at >= ? AND t.created_at <= ? AND t.price > 0""",
            [start_dt, end_dt],
            one=True
        )
        total_amount = float(summary_row['total_amount']) if summary_row else 0.0
        total_count = int(summary_row['total_count']) if summary_row else 0
        unique_users = int(summary_row['unique_users']) if summary_row else 0
        avg_purchase = (total_amount / total_count) if total_count > 0 else 0.0

        # Breakdown by product, sorted from most purchased to least purchased
        if include_zero:
            prod_rows = query_db(
                """SELECT 
                       p.id AS product_id,
                       p.name AS product_name,
                       p.barcode AS product_barcode,
                       p.image AS product_image,
                       p.price AS current_price,
                       COALESCE(c.name, 'Okänd') AS category_name,
                       COUNT(t.id) AS count,
                       COALESCE(SUM(t.price), 0.0) AS total_amount
                   FROM products p
                   LEFT JOIN categories c ON p.category_id = c.id
                   LEFT JOIN transactions t ON p.id = t.product_id AND t.created_at >= ? AND t.created_at <= ? AND t.price > 0
                   WHERE p.hidden = 0
                   GROUP BY p.id
                   ORDER BY count DESC, total_amount DESC, p.name COLLATE NOCASE ASC""",
                [start_dt, end_dt]
            )
        else:
            prod_rows = query_db(
                """SELECT 
                       p.id AS product_id,
                       p.name AS product_name,
                       p.barcode AS product_barcode,
                       p.image AS product_image,
                       p.price AS current_price,
                       COALESCE(c.name, 'Okänd') AS category_name,
                       COUNT(t.id) AS count,
                       SUM(t.price) AS total_amount
                   FROM transactions t
                   JOIN products p ON t.product_id = p.id
                   LEFT JOIN categories c ON p.category_id = c.id
                   WHERE t.created_at >= ? AND t.created_at <= ? AND t.price > 0
                   GROUP BY p.id
                   ORDER BY count DESC, total_amount DESC, p.name COLLATE NOCASE ASC""",
                [start_dt, end_dt]
            )

        by_product = []
        for idx, r in enumerate(prod_rows, 1):
            cnt = int(r['count'])
            tot = float(r['total_amount'])
            avg_price = (tot / cnt) if cnt > 0 else float(r['current_price'])
            pct = (cnt / total_count * 100.0) if total_count > 0 else 0.0
            by_product.append({
                'rank': idx,
                'product_id': r['product_id'],
                'product_name': r['product_name'],
                'product_barcode': r['product_barcode'],
                'product_image': r['product_image'],
                'current_price': float(r['current_price']),
                'category_name': r['category_name'],
                'count': cnt,
                'total_amount': tot,
                'avg_price': avg_price,
                'percent': pct
            })

        # Breakdown by category
        cat_rows = query_db(
            """SELECT 
                   c.id AS category_id,
                   COALESCE(c.name, 'Okänd') AS category_name,
                   COUNT(t.id) AS count,
                   SUM(t.price) AS total_amount
               FROM transactions t
               JOIN products p ON t.product_id = p.id
               LEFT JOIN categories c ON p.category_id = c.id
               WHERE t.created_at >= ? AND t.created_at <= ? AND t.price > 0
               GROUP BY c.id
               ORDER BY total_amount DESC""",
            [start_dt, end_dt]
        )
        by_category = []
        for r in cat_rows:
            cnt = int(r['count'])
            tot = float(r['total_amount'])
            pct = (tot / total_amount * 100.0) if total_amount > 0 else 0.0
            by_category.append({
                'category_id': r['category_id'],
                'category_name': r['category_name'],
                'count': cnt,
                'total_amount': tot,
                'percent': pct
            })

        top_product = by_product[0] if (by_product and by_product[0]['count'] > 0) else None

        return {
            'total_amount': total_amount,
            'total_count': total_count,
            'unique_users': unique_users,
            'avg_purchase': avg_purchase,
            'top_product': top_product,
            'by_product': by_product,
            'by_category': by_category
        }
