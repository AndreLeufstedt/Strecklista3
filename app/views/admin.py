import os
import csv
import datetime
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, Response
from werkzeug.utils import secure_filename
from app.models.user import User
from app.models.product import Product
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.setting import Setting
from app.models.stats import Stats
from app.utils import format_dmy, format_date_dmy

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

def save_uploaded_file(file, subfolder):
    """Save an uploaded file safely and return its relative path."""
    if not file or not file.filename:
        return None
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder)
    os.makedirs(upload_dir, exist_ok=True)
    filename = secure_filename(file.filename)
    dest_path = os.path.join(upload_dir, filename)
    file.save(dest_path)
    return f"uploads/{subfolder}/{filename}"

# --- Admin Entry / Redirect ---
@admin_bp.route('')
@admin_bp.route('/')
def index():
    return redirect(url_for('admin.product_list'))

# --- User Management ---
@admin_bp.route('/user')
def user_list():
    show_hidden = request.args.get('hidden', '0') == '1'
    query_str = request.args.get('q', '').strip()
    if show_hidden:
        users = User.search(query_str, only_hidden=True)
    else:
        users = User.search(query_str, include_hidden=False)
    return render_template(
        'admin/userlist.html',
        users=users,
        search_query=query_str,
        show_hidden=show_hidden
    )

@admin_bp.route('/user/add', methods=['GET', 'POST'])
def user_add():
    if request.method == 'POST':
        barcode = request.form.get('barcode', '').strip()
        name = request.form.get('name', '').strip()
        if not barcode or not name:
            flash('Both barcode and name are required!')
            return redirect(url_for('admin.user_add'))

        existing = User.get_by_barcode(barcode)
        if existing and not (existing.hidden() and len(existing.transactions()) == 0):
            flash('Barcode / User ID is not unique!')
            return redirect(url_for('admin.user_add'))

        pic_path = save_uploaded_file(request.files.get('picture'), 'users')
        user = User.add(barcode=barcode, name=name, image=pic_path)
        if not user:
            flash('Could not create the user.')
            return redirect(url_for('admin.user_add'))

        flash(f'User "{user.name}" has been added.')
        return redirect(url_for('admin.user_show', barcode=user.barcode))

    return render_template('admin/useradd.html')

@admin_bp.route('/user/<barcode>')
def user_show(barcode):
    user = User.get_by_barcode(barcode)
    if not user:
        flash('User not found!')
        return redirect(url_for('admin.user_list'))
    return render_template('admin/user.html', user=user)

@admin_bp.route('/user/<barcode>/update', methods=['POST'])
def user_update(barcode):
    user = User.get_by_barcode(barcode)
    if not user:
        flash('User not found!')
        return redirect(url_for('admin.user_list'))

    name = request.form.get('name')
    pic_file = request.files.get('picture')
    pic_path = save_uploaded_file(pic_file, 'users') if pic_file and pic_file.filename else None

    user.update(name=name, image=pic_path)
    flash(f'User "{user.name}" has been updated.')
    return redirect(url_for('admin.user_show', barcode=user.barcode))

@admin_bp.route('/user/<barcode>/enable')
def user_enable(barcode):
    user = User.get_by_barcode(barcode)
    if user:
        user.enable()
        flash(f'User "{user.name}" is now active.')
    return redirect(url_for('admin.user_show', barcode=barcode))

@admin_bp.route('/user/<barcode>/disable')
def user_disable(barcode):
    user = User.get_by_barcode(barcode)
    if user:
        user.disable()
        flash(f'User "{user.name}" is now disabled.')
    return redirect(url_for('admin.user_show', barcode=barcode))

@admin_bp.route('/user/<barcode>/delete', methods=['GET', 'POST'])
def user_delete(barcode):
    user = User.get_by_barcode(barcode)
    if user:
        user.hide()
        flash(f'Användaren "{user.name}" har tagits bort (dold).')
    else:
        flash('Användaren hittades inte!')
    return redirect(url_for('admin.user_list'))

@admin_bp.route('/user/<barcode>/restore', methods=['GET', 'POST'])
def user_restore(barcode):
    user = User.get_by_barcode(barcode)
    if user:
        user.unhide()
        flash(f'Användaren "{user.name}" har återställts.')
        return redirect(url_for('admin.user_show', barcode=barcode))
    flash('Användaren hittades inte!')
    return redirect(url_for('admin.user_list'))

# --- Product Management ---
@admin_bp.route('/product')
def product_list():
    show_hidden = request.args.get('hidden', '0') == '1'
    query_str = request.args.get('q', '').strip()
    if show_hidden:
        products = Product.search(query_str, only_hidden=True)
    else:
        products = Product.search(query_str, include_hidden=False)
    return render_template(
        'admin/productlist.html',
        products=products,
        search_query=query_str,
        show_hidden=show_hidden
    )

@admin_bp.route('/product/add', methods=['GET', 'POST'])
def product_add():
    categories = Category.all()
    if request.method == 'POST':
        barcode = request.form.get('barcode', '').strip()
        name = request.form.get('name', '').strip()
        price = request.form.get('price', '0')
        category_id = request.form.get('category')

        if not barcode or not name or not category_id:
            flash('Name, price, category, and barcode are all required!')
            return redirect(url_for('admin.product_add'))

        existing = Product.get_by_barcode(barcode)
        if existing and not (existing.hidden() and len(existing.toplist()) == 0):
            flash('Product barcode is not unique!')
            return redirect(url_for('admin.product_add'))

        pic_path = save_uploaded_file(request.files.get('picture'), 'products')
        product = Product.add(
            barcode=barcode,
            name=name,
            price=price,
            category_id=category_id,
            image=pic_path
        )
        if not product:
            flash('Could not add product.')
            return redirect(url_for('admin.product_add'))

        flash(f'Product "{product.name}" has been added.')
        return redirect(url_for('admin.product_show', barcode=product.barcode))

    return render_template('admin/productadd.html', categories=categories)

@admin_bp.route('/product/<barcode>')
def product_show(barcode):
    product = Product.get_by_barcode(barcode)
    if not product:
        flash('Product not found!')
        return redirect(url_for('admin.product_list'))
    categories = Category.all()
    return render_template('admin/product.html', product=product, categories=categories)

@admin_bp.route('/product/<barcode>/update', methods=['POST'])
def product_update(barcode):
    product = Product.get_by_barcode(barcode)
    if not product:
        flash('Product not found!')
        return redirect(url_for('admin.product_list'))

    name = request.form.get('name')
    price = request.form.get('price')
    category_id = request.form.get('category')
    pic_file = request.files.get('picture')
    pic_path = save_uploaded_file(pic_file, 'products') if pic_file and pic_file.filename else None

    product.update(name=name, price=price, category_id=category_id, image=pic_path)
    flash(f'Product "{product.name}" has been updated.')
    return redirect(url_for('admin.product_show', barcode=product.barcode))

@admin_bp.route('/product/<barcode>/delete', methods=['GET', 'POST'])
def product_delete(barcode):
    product = Product.get_by_barcode(barcode)
    if product:
        product.hide()
        flash(f'Produkten "{product.name}" har tagits bort (dold).')
    else:
        flash('Produkten hittades inte!')
    return redirect(url_for('admin.product_list'))

@admin_bp.route('/product/<barcode>/restore', methods=['GET', 'POST'])
def product_restore(barcode):
    product = Product.get_by_barcode(barcode)
    if product:
        product.unhide()
        flash(f'Produkten "{product.name}" har återställts.')
        return redirect(url_for('admin.product_show', barcode=barcode))
    flash('Produkten hittades inte!')
    return redirect(url_for('admin.product_list'))

# --- Export & Balance Settlement ---
@admin_bp.route('/export')
def export_debts():
    users = User.all()
    categories = Category.all()

    # Precalculate debt for each user
    user_debts = {u.id: u.debt() for u in users}

    # Sort: debtors (debt > 0) alphabetically by name first,
    # followed by debt-free (debt <= 0) alphabetically by name
    debtors = [u for u in users if user_debts[u.id] > 0]
    debtors.sort(key=lambda u: u.name.lower())

    debt_free = [u for u in users if user_debts[u.id] <= 0]
    debt_free.sort(key=lambda u: u.name.lower())

    sorted_users = debtors + debt_free
    return render_template(
        'admin/export.html',
        users=sorted_users,
        categories=categories,
        user_debts=user_debts
    )

@admin_bp.route('/export/empty')
def export_empty():
    """Reset all user balances to zero at once."""
    for user in User.all():
        if user.debt() != 0:
            Transaction.pay_debt(user, notes='Bulk settlement / export')
    flash('All debts have been cleared!')
    return redirect(url_for('admin.export_debts'))

# --- Settings ---
@admin_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    if request.method == 'POST':
        user_timeout = request.form.get('user_timeout', '').strip()
        confirm_timeout = request.form.get('confirm_timeout', '').strip()
        guest_surcharge = request.form.get('guest_surcharge', '').strip()

        try:
            u_val = max(1, int(user_timeout))
            c_val = max(1, int(confirm_timeout))
            g_val = max(0.0, float(guest_surcharge))
            Setting.set('user_timeout', u_val)
            Setting.set('confirm_timeout', c_val)
            Setting.set('guest_surcharge', g_val)
            flash('Inställningarna har sparats!')
        except ValueError:
            flash('Vänligen ange giltiga numeriska värden!')

        return redirect(url_for('admin.settings'))

    current_settings = Setting.get_all()
    return render_template('admin/settings.html', settings=current_settings)

# --- Purchase Statistics & Date Range Analysis ---
def parse_date_range(start_str, end_str):
    """Parse and validate date range, defaulting to the last 4 weeks (28 days)."""
    today = datetime.date.today()
    default_start = today - datetime.timedelta(days=28)
    default_end = today

    try:
        if start_str:
            s_date = datetime.datetime.strptime(start_str, '%Y-%m-%d').date()
        else:
            s_date = default_start
    except ValueError:
        s_date = default_start

    try:
        if end_str:
            e_date = datetime.datetime.strptime(end_str, '%Y-%m-%d').date()
        else:
            e_date = default_end
    except ValueError:
        e_date = default_end

    if s_date > e_date:
        s_date, e_date = e_date, s_date

    return s_date.strftime('%Y-%m-%d'), e_date.strftime('%Y-%m-%d')

@admin_bp.route('/purchases')
@admin_bp.route('/stats')
def purchase_stats():
    """Display product sales rankings and purchase history within a date range (default 4 weeks)."""
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()
    include_zero = request.args.get('include_zero', '0') == '1'

    start_date, end_date = parse_date_range(start_date_str, end_date_str)

    today = datetime.date.today()
    four_weeks_ago = (today - datetime.timedelta(days=28)).strftime('%Y-%m-%d')
    seven_days_ago = (today - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    month_start = today.replace(day=1).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')

    purchases = Stats.purchases_by_date_range(start_date, end_date)
    summary = Stats.purchases_summary_by_date_range(start_date, end_date, include_zero=include_zero)

    return render_template(
        'admin/purchases.html',
        purchases=purchases,
        summary=summary,
        start_date=start_date,
        end_date=end_date,
        include_zero=include_zero,
        today=today_str,
        four_weeks_ago=four_weeks_ago,
        seven_days_ago=seven_days_ago,
        month_start=month_start
    )

@admin_bp.route('/purchases/export_products.csv')
def purchase_export_products_csv():
    """Export product purchase ranking within the specified date range to a CSV file."""
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()
    include_zero = request.args.get('include_zero', '0') == '1'

    start_date, end_date = parse_date_range(start_date_str, end_date_str)
    summary = Stats.purchases_summary_by_date_range(start_date, end_date, include_zero=include_zero)

    output = io.StringIO()
    # UTF-8 BOM for Excel
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        'Placering',
        'Produkt',
        'Streckkod',
        'Kategori',
        'Antal köpta',
        'Total omsättning (kr)',
        'Snittpris (kr)',
        'Andel av köp (%)'
    ])

    for p in summary['by_product']:
        writer.writerow([
            p['rank'],
            p['product_name'],
            p['product_barcode'],
            p['category_name'],
            p['count'],
            f"{p['total_amount']:.2f}".replace('.', ','),
            f"{p['avg_price']:.2f}".replace('.', ','),
            f"{p['percent']:.1f}".replace('.', ',')
        ])

    csv_data = output.getvalue().encode('utf-8')
    filename = f"produktforsaljning_{start_date}_{end_date}.csv"
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

@admin_bp.route('/purchases/export.csv')
def purchase_export_csv():
    """Export individual purchase transactions within the specified date range to a CSV file."""
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()

    start_date, end_date = parse_date_range(start_date_str, end_date_str)
    purchases = Stats.purchases_by_date_range(start_date, end_date)

    output = io.StringIO()
    # UTF-8 BOM for seamless display in Excel
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')
    writer.writerow([
        'ID',
        'Datum och tid',
        'Användare',
        'Användar-ID',
        'Produkt',
        'Produkt-streckkod',
        'Kategori',
        'Belopp (kr)',
        'Noteringar'
    ])

    for p in purchases:
        writer.writerow([
            p['id'],
            format_dmy(p['created_at']),
            p['user_name'],
            p['user_barcode'],
            p['product_name'],
            p['product_barcode'],
            p['category_name'],
            f"{p['price']:.2f}".replace('.', ','),
            p['notes'] or ''
        ])

    csv_data = output.getvalue().encode('utf-8')
    filename = f"kop_{start_date}_{end_date}.csv"
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

