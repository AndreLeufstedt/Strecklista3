import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'strecklistan3-secret-key-2026')
    DATABASE = os.environ.get('DATABASE', os.path.join(BASE_DIR, 'streck.db'))
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'app', 'static', 'uploads'))

    # Kiosk Special Barcodes
    PAID_BARCODE = 'BETALT'
    UNDO_BARCODE = 'undo'
    LOGOUT_BARCODE = 'log out'
    JOBBMAT_BARCODE = 'Jobbmat'
    REMOVE_JOBBMAT_BARCODE = 'Ta+bort+jobbmat'

    # Categories permitted on the office food (jobbmat) account
    ALLOWED_JOBBMAT_CATEGORIES = ['Ickeöl']

    # Timeouts in seconds for kiosk navigation
    USER_TIMEOUT = 15
    CONFIRM_TIMEOUT = 3
