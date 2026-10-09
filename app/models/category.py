from app.db import query_db, modify_db

class Category:
    def __init__(self, row):
        self.id = row['id']
        self.name = row['name']

    @classmethod
    def all(cls):
        """Retrieve all categories sorted alphabetically."""
        rows = query_db("SELECT * FROM categories ORDER BY name ASC")
        return [cls(r) for r in rows]

    @classmethod
    def get_by_id(cls, category_id):
        """Find a category by its ID."""
        row = query_db("SELECT * FROM categories WHERE id = ?", [category_id], one=True)
        return cls(row) if row else None

    @classmethod
    def get_by_name(cls, name):
        """Find a category by its name."""
        row = query_db("SELECT * FROM categories WHERE name = ?", [name], one=True)
        return cls(row) if row else None

    @classmethod
    def add(cls, name):
        """Create a new category if it does not already exist."""
        existing = cls.get_by_name(name)
        if existing:
            return existing
        new_id = modify_db("INSERT INTO categories (name) VALUES (?)", [name])
        return cls.get_by_id(new_id)

    @classmethod
    def ensure_defaults(cls):
        """Ensure default categories exist if the table is empty."""
        if not cls.all():
            cls.add("Öl")
            cls.add("Ickeöl")
