from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from app.models.user import User
from app.models.product import Product
from app.models.transaction import Transaction
from app.models.setting import Setting

kiosk_bp = Blueprint('kiosk', __name__)

@kiosk_bp.route('/')
def index():
    return render_template('index.html')

@kiosk_bp.route('/disabled')
def user_disabled():
    return render_template('disabled.html')

@kiosk_bp.route('/user', methods=['POST'])
def user_arrival():
    barcode = request.form.get('barcode', '').strip()
    if not barcode:
        return redirect(url_for('kiosk.index'))

    # Check if this is the explicit logout barcode
    if barcode == current_app.config.get('LOGOUT_BARCODE', 'log out'):
        return redirect(url_for('kiosk.index'))

    user = User.get_by_barcode(barcode)
    if user and not user.hidden():
        if user.disabled():
            return redirect(url_for('kiosk.user_disabled'))
        return redirect(url_for('kiosk.show_user', barcode=barcode))

    # If barcode is not a user, check if a product was scanned from the home screen
    product = Product.get_by_barcode(barcode)
    if product and not product.hidden():
        return redirect(url_for('kiosk.show_product', barcode=product.barcode))

    flash('The scanned code matches neither a user nor a product!')
    return redirect(url_for('kiosk.index'))

@kiosk_bp.route('/user/<barcode>')
def show_user(barcode):
    user = User.get_by_barcode(barcode)
    if not user or user.hidden():
        flash('User does not exist!')
        return redirect(url_for('kiosk.index'))
    if user.disabled():
        return redirect(url_for('kiosk.user_disabled'))

    bought_barcode = request.args.get('bought')
    bought_product = Product.get_by_barcode(bought_barcode) if bought_barcode else None
    paid = request.args.get('paid', False)
    undone = request.args.get('undone', False)
    disabled = request.args.get('disabled', False)

    user_timeout = Setting.get_int('user_timeout', default=current_app.config.get('USER_TIMEOUT', 15))
    confirm_timeout = Setting.get_int('confirm_timeout', default=current_app.config.get('CONFIRM_TIMEOUT', 3))

    return render_template(
        'user.html',
        user=user,
        bought=bought_product,
        paid=bool(paid),
        undone=bool(undone),
        disabled=bool(disabled),
        user_timeout=user_timeout,
        confirm_timeout=confirm_timeout
    )

@kiosk_bp.route('/user/<barcode>/buy', methods=['POST'])
def user_buy(barcode):
    user = User.get_by_barcode(barcode)
    if not user or user.hidden():
        flash('User does not exist!')
        return redirect(url_for('kiosk.index'))
    if user.disabled():
        return redirect(url_for('kiosk.user_disabled'))

    scanned = request.form.get('barcode', '').strip()
    if not scanned:
        return redirect(url_for('kiosk.show_user', barcode=barcode))

    # 1. Check for logout barcode
    if scanned == current_app.config.get('LOGOUT_BARCODE', 'log out'):
        flash('You have been logged out!')
        return redirect(url_for('kiosk.index'))

    # 2. Check for balance paid barcode
    if scanned == current_app.config.get('PAID_BARCODE', 'BETALT'):
        return redirect(url_for('kiosk.user_paid', barcode=barcode))

    # 3. Check for undo barcode
    if scanned == current_app.config.get('UNDO_BARCODE', 'undo'):
        return redirect(url_for('kiosk.user_undo', barcode=barcode))

    # 4. Check if another user barcode was scanned (switch active user)
    another_user = User.get_by_barcode(scanned)
    if another_user and not another_user.hidden():
        if another_user.disabled():
            return redirect(url_for('kiosk.user_disabled'))
        return redirect(url_for('kiosk.show_user', barcode=scanned))

    # 5. Check if barcode is a product
    product = Product.get_by_barcode(scanned)
    if not product or product.hidden():
        flash('Product does not exist!')
        return redirect(url_for('kiosk.show_user', barcode=barcode))

    # Verify office meal policy restrictions
    jobbmat_barcode = current_app.config.get('JOBBMAT_BARCODE', 'Jobbmat')
    if user.barcode == jobbmat_barcode and not product.allowed_jobbmat():
        flash('This item is not allowed on the office food account!')
        return redirect(url_for('kiosk.show_user', barcode=barcode, disabled=1))

    # Execute purchase
    Transaction.create_purchase(user, product)
    return redirect(url_for('kiosk.show_user', barcode=barcode, bought=product.barcode))

@kiosk_bp.route('/user/<barcode>/paid')
def user_paid(barcode):
    user = User.get_by_barcode(barcode)
    if not user or user.hidden():
        return redirect(url_for('kiosk.index'))
    Transaction.pay_debt(user)
    return redirect(url_for('kiosk.show_user', barcode=barcode, paid=1))

@kiosk_bp.route('/user/<barcode>/undo')
def user_undo(barcode):
    user = User.get_by_barcode(barcode)
    if not user or user.hidden():
        return redirect(url_for('kiosk.index'))
    Transaction.undo_last(user)
    return redirect(url_for('kiosk.show_user', barcode=barcode, undone=1))

@kiosk_bp.route('/product', methods=['POST'])
def product_arrival():
    barcode = request.form.get('barcode', '').strip()
    product = Product.get_by_barcode(barcode)
    if not product or product.hidden():
        flash('The product or user does not exist!')
        return redirect(url_for('kiosk.index'))
    return redirect(url_for('kiosk.show_product', barcode=product.barcode))

@kiosk_bp.route('/product/<barcode>')
def show_product(barcode):
    product = Product.get_by_barcode(barcode)
    if not product or product.hidden():
        flash('Product does not exist!')
        return redirect(url_for('kiosk.index'))
    user_timeout = Setting.get_int('user_timeout', default=current_app.config.get('USER_TIMEOUT', 15))
    return render_template(
        'product.html',
        product=product,
        user_timeout=user_timeout
    )
