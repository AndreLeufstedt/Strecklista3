from app.db import query_db, modify_db

class Setting:
    DEFAULT_SETTINGS = {
        'user_timeout': '15',
        'confirm_timeout': '3',
        'guest_surcharge': '3'
    }

    @classmethod
    def get(cls, key, default=None):
        """Retrieve a setting string value by its key."""
        row = query_db("SELECT value FROM settings WHERE key = ?", [key], one=True)
        if row:
            return row['value']
        return cls.DEFAULT_SETTINGS.get(key, default)

    @classmethod
    def get_int(cls, key, default=0):
        """Retrieve a setting as an integer with fallback."""
        val = cls.get(key)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    @classmethod
    def get_float(cls, key, default=0.0):
        """Retrieve a setting as a float with fallback."""
        val = cls.get(key)
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    @classmethod
    def set(cls, key, value):
        """Store or update a setting value."""
        str_val = str(value).strip()
        modify_db(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            [key, str_val]
        )
        return str_val

    @classmethod
    def get_all(cls):
        """Retrieve all settings as a dictionary with defaults populated."""
        rows = query_db("SELECT key, value FROM settings")
        results = dict(cls.DEFAULT_SETTINGS)
        for r in rows:
            results[r['key']] = r['value']
        return results

    @classmethod
    def ensure_defaults(cls):
        """Ensure all default settings exist in the database."""
        for key, val in cls.DEFAULT_SETTINGS.items():
            existing = query_db("SELECT key FROM settings WHERE key = ?", [key], one=True)
            if not existing:
                modify_db("INSERT INTO settings (key, value) VALUES (?, ?)", [key, val])
