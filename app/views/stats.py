from collections import deque
from flask import Blueprint, render_template, Response, stream_with_context, request, flash, redirect, url_for
from app.models.stats import Stats
from app.models.category import Category
from app.models.user import User

stats_bp = Blueprint('stats', __name__)

@stats_bp.route('/stats')
def index():
    search_query = request.args.get('q', '').strip()
    users_summary = Stats.user_summary_list(search_query=search_query)
    return render_template(
        'stats.html',
        stats=Stats,
        categories=Category.all(),
        users_summary=users_summary,
        search_query=search_query
    )

@stats_bp.route('/stats/user/<barcode>')
def user_stats(barcode):
    user = User.get_by_barcode(barcode)
    if not user:
        flash('Användaren hittades inte!')
        return redirect(url_for('stats.index'))

    product_breakdown = Stats.user_product_breakdown(user.id)
    category_breakdown = Stats.user_category_breakdown(user.id)
    recent_purchases = Stats.user_recent_purchases(user.id, limit=25)
    favorite_product = Stats.user_favorite_product(user.id)

    total_items = sum(p['count'] for p in product_breakdown)
    total_spent = sum(p['total'] for p in product_breakdown)

    return render_template(
        'stats_user.html',
        user=user,
        product_breakdown=product_breakdown,
        category_breakdown=category_breakdown,
        recent_purchases=recent_purchases,
        favorite_product=favorite_product,
        total_items=total_items,
        total_spent=total_spent
    )

@stats_bp.route('/stats/timeseries.csv')
def timeseries_csv():
    def generate():
        series = Stats.timeseries()
        categories = []
        category_history = []
        data = {}

        for row in series:
            category_name = row[1]
            if category_name not in categories:
                categories.append(category_name)
                category_history.append(deque([0.0] * 7))

        num_cats = len(categories)
        for row in series:
            day = row[0]
            cat = row[1]
            val = row[2]
            if day not in data:
                data[day] = [0.0] * (num_cats * 2 + 1)
            idx = categories.index(cat)
            data[day][idx] = val

        if categories:
            header_moving_avg = ','.join([f"Moving average {c}" for c in categories])
            yield f"Datum,{','.join(categories)},{header_moving_avg},Moving average total\n"
        else:
            yield "Datum,No data\n"

        for day in sorted(data.keys()):
            for idx in range(num_cats):
                category_history[idx].popleft()
                category_history[idx].append(data[day][idx])
                data[day][num_cats + idx] = sum(category_history[idx]) / 7.0

            # Calculate total moving average
            data[day][num_cats * 2] = sum(data[day][num_cats : num_cats * 2])
            values_str = ','.join([f"{v:10.3f}" for v in data[day]])
            yield f"{day},{values_str}\n"

    return Response(stream_with_context(generate()), mimetype='text/csv')
