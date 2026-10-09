import sqlite3
import os
from flask import g, current_app

def get_db():
    """Retrieve or initialize the SQLite database connection for the current request."""
    if '_database' not in g:
        db_path = current_app.config['DATABASE']
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        conn = sqlite3.connect(
            db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row
        # Enable Foreign Keys and WAL journal mode for optimal concurrent performance
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        g._database = conn
    return g._database

def close_db(e=None):
    """Close the database connection at the end of the request."""
    db = g.pop('_database', None)
    if db is not None:
        db.close()

def init_db(app=None):
    """Initialize database tables using schema.sql."""
    if app:
        with app.app_context():
            _run_init_script()
    else:
        _run_init_script()

def _run_init_script():
    db = get_db()
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        db.cursor().executescript(f.read())
    try:
        db.execute("ALTER TABLE users ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0;")
    except sqlite3.OperationalError:
        pass
    try:
        db.execute("ALTER TABLE products ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0;")
    except sqlite3.OperationalError:
        pass
    db.commit()

def query_db(query, args=(), one=False):
    """Helper function to execute read queries and return dict-like rows."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

def modify_db(query, args=()):
    """Helper function for INSERT, UPDATE, and DELETE statements."""
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id
