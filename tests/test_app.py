import os
import unittest
import tempfile
import shutil
from app import create_app
from app.db import init_db
from app.models.user import User
from app.models.product import Product
from app.models.category import Category
from app.models.setting import Setting

class StrecklistanTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        self.upload_dir = tempfile.mkdtemp()

        self.app = create_app({
            'TESTING': True,
            'DATABASE': self.db_path,
            'UPLOAD_FOLDER': self.upload_dir,
            'WTF_CSRF_ENABLED': False
        })
        self.client = self.app.test_client()

        with self.app.app_context():
            init_db()
            Category.ensure_defaults()
            Setting.ensure_defaults()

            # Create test users
            User.add('test_user', 'Test User')
            User.add('disabled_user', 'Disabled User')
            user_disabled = User.get_by_barcode('disabled_user')
            user_disabled.disable()

            # Create office food account
            User.add('Jobbmat', 'Jobbmat')

            # Create test products
            cat_beer = Category.get_by_name('Öl')
            cat_food = Category.get_by_name('Ickeöl')
            Product.add('beer_123', 'Test Beer', 20.0, cat_beer.id)
            Product.add('food_123', 'Sandwich', 15.0, cat_food.id)

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
        if os.path.exists(self.upload_dir):
            shutil.rmtree(self.upload_dir)

    def test_kiosk_landing(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_scan_user_and_product_from_index(self):
        # Scan user barcode -> redirect to user page
        response = self.client.post('/user', data={'barcode': 'test_user'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/user/test_user', response.headers['Location'])

        # Scan product barcode from home screen -> redirect to product page
        response = self.client.post('/user', data={'barcode': 'beer_123'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/product/beer_123', response.headers['Location'])

        # Scan disabled user barcode -> redirect to /disabled
        response = self.client.post('/user', data={'barcode': 'disabled_user'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/disabled', response.headers['Location'])

    def test_purchase_and_debt(self):
        with self.app.app_context():
            user = User.get_by_barcode('test_user')
            self.assertEqual(user.debt(), 0.0)

        # Execute purchase (charges member price: 20.0 kr)
        response = self.client.post('/user/test_user/buy', data={'barcode': 'beer_123'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            user = User.get_by_barcode('test_user')
            self.assertEqual(user.debt(), 20.0)
            transactions = user.transactions()
            self.assertEqual(len(transactions), 1)
            self.assertEqual(transactions[0]['name'], 'Test Beer')

    def test_undo_transaction(self):
        # Make two purchases
        self.client.post('/user/test_user/buy', data={'barcode': 'beer_123'}, follow_redirects=True)
        self.client.post('/user/test_user/buy', data={'barcode': 'food_123'}, follow_redirects=True)

        with self.app.app_context():
            user = User.get_by_barcode('test_user')
            self.assertEqual(user.debt(), 35.0)
            # Verify newest transaction appears first (index 0)
            txs = user.transactions()
            self.assertEqual(txs[0]['name'], 'Sandwich')
            self.assertEqual(txs[1]['name'], 'Test Beer')

        # Undo the last purchase via 'undo' barcode
        self.client.post('/user/test_user/buy', data={'barcode': 'undo'}, follow_redirects=True)

        with self.app.app_context():
            user = User.get_by_barcode('test_user')
            self.assertEqual(user.debt(), 20.0)

    def test_payment_clears_debt(self):
        # Make a purchase
        self.client.post('/user/test_user/buy', data={'barcode': 'beer_123'}, follow_redirects=True)

        # Pay debt via PAID barcode
        self.client.post('/user/test_user/buy', data={'barcode': 'BETALT'}, follow_redirects=True)

        with self.app.app_context():
            user = User.get_by_barcode('test_user')
            self.assertEqual(user.debt(), 0.0)

    def test_jobbmat_rules(self):
        # Food (Non-beer) is permitted on office account
        response = self.client.post('/user/Jobbmat/buy', data={'barcode': 'food_123'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            user = User.get_by_barcode('Jobbmat')
            self.assertEqual(user.debt(), 15.0)

        # Beer is NOT permitted on office account
        response = self.client.post('/user/Jobbmat/buy', data={'barcode': 'beer_123'}, follow_redirects=True)
        with self.app.app_context():
            user = User.get_by_barcode('Jobbmat')
            self.assertEqual(user.debt(), 15.0)  # Debt remains unchanged

        # Remove item (reversal)
        response = self.client.post('/user/Ta+bort+jobbmat/buy', data={'barcode': 'food_123'}, follow_redirects=True)
        with self.app.app_context():
            user = User.get_by_barcode('Jobbmat')
            self.assertEqual(user.debt(), 0.0)

    def test_admin_features(self):
        # Visiting /admin directly redirects to /admin/product
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/product', response.headers['Location'])

        response_follow = self.client.get('/admin', follow_redirects=True)
        self.assertEqual(response_follow.status_code, 200)
        self.assertIn(b'Produktlista', response_follow.data)

        # Create new product through admin
        with self.app.app_context():
            category = Category.get_by_name('Öl')
            category_id = category.id

        response = self.client.post('/admin/product/add', data={
            'barcode': 'cider_999',
            'name': 'Apple Cider',
            'price': '18.0',
            'category': str(category_id)
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            product = Product.get_by_barcode('cider_999')
            self.assertIsNotNone(product)
            self.assertEqual(product.name, 'Apple Cider')
            self.assertEqual(product.price, 18.0)

    def test_stats_and_csv(self):
        self.client.post('/user/test_user/buy', data={'barcode': 'beer_123'}, follow_redirects=True)

        response = self.client.get('/stats')
        self.assertEqual(response.status_code, 200)
        # Verify scanner bar is removed from stats page
        self.assertNotIn(b'scanner-container', response.data)
        self.assertNotIn(b'Skanna streckkod', response.data)
        self.assertIn(b'Personstatistik', response.data)

        # Test individual user detailed statistics
        user_stats_resp = self.client.get('/stats/user/test_user')
        self.assertEqual(user_stats_resp.status_code, 200)
        # Verify scanner bar is removed from user stats page
        self.assertNotIn(b'scanner-container', user_stats_resp.data)
        self.assertNotIn(b'Skanna streckkod', user_stats_resp.data)
        # Verify user breakdown contains purchased product
        self.assertIn(b'Test Beer', user_stats_resp.data)
        self.assertIn(b'20.0 kr', user_stats_resp.data)

        response_csv = self.client.get('/stats/timeseries.csv')
        self.assertEqual(response_csv.status_code, 200)
        self.assertIn('Datum', response_csv.data.decode('utf-8'))

    def test_settings_and_dynamic_timeouts(self):
        # Check initial default settings
        with self.app.app_context():
            self.assertEqual(Setting.get_int('user_timeout'), 15)
            self.assertEqual(Setting.get_int('confirm_timeout'), 3)
            self.assertEqual(Setting.get_float('guest_surcharge'), 3.0)

        # Update settings via admin POST request
        response = self.client.post('/admin/settings', data={
            'user_timeout': '25',
            'confirm_timeout': '5',
            'guest_surcharge': '4.5'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            self.assertEqual(Setting.get_int('user_timeout'), 25)
            self.assertEqual(Setting.get_int('confirm_timeout'), 5)
            self.assertEqual(Setting.get_float('guest_surcharge'), 4.5)

        # Verify that the user page reflects updated timeout in the meta refresh tag
        user_response = self.client.get('/user/test_user')
        self.assertEqual(user_response.status_code, 200)
        self.assertIn(b'content="25; URL=/"', user_response.data)

    def test_dual_pricing_logic(self):
        # Member price is 20.0 kr, default surcharge is 3.0 kr -> standalone price is 23.0 kr
        with self.app.app_context():
            product = Product.get_by_barcode('beer_123')
            self.assertEqual(product.price, 20.0)
            self.assertEqual(product.public_price(), 23.0)

        # View standalone product page: should display standalone price 23.0 kr without exposing member price
        product_response = self.client.get('/product/beer_123')
        self.assertEqual(product_response.status_code, 200)
        self.assertIn(b'23.0 kr', product_response.data)
        self.assertNotIn(b'Medlemspris', product_response.data)

        # Purchasing as a logged-in user: only charges the 20.0 kr member price!
        self.client.post('/user/test_user/buy', data={'barcode': 'beer_123'}, follow_redirects=True)
        with self.app.app_context():
            user = User.get_by_barcode('test_user')
            self.assertEqual(user.debt(), 20.0)

    def test_user_and_product_search(self):
        with self.app.app_context():
            # Add additional users and products to verify search
            User.add('alice_1', 'Alice Andersson')
            User.add('bob_1', 'Bob Berg')

            # Search users
            results_name = User.search('Alice')
            self.assertEqual(len(results_name), 1)
            self.assertEqual(results_name[0].name, 'Alice Andersson')

            results_barcode = User.search('bob_1')
            self.assertEqual(len(results_barcode), 1)
            self.assertEqual(results_barcode[0].barcode, 'bob_1')

            # Search products
            results_prod = Product.search('Beer')
            self.assertEqual(len(results_prod), 1)
            self.assertEqual(results_prod[0].name, 'Test Beer')

            results_cat = Product.search('Ickeöl')
            self.assertEqual(len(results_cat), 1)
            self.assertEqual(results_cat[0].name, 'Sandwich')

        # Test admin HTTP endpoints with search query parameters
        resp_user = self.client.get('/admin/user?q=Alice')
        self.assertEqual(resp_user.status_code, 200)
        self.assertIn(b'Alice Andersson', resp_user.data)
        self.assertNotIn(b'Bob Berg', resp_user.data)

        resp_prod = self.client.get('/admin/product?q=Sandwich')
        self.assertEqual(resp_prod.status_code, 200)
        self.assertIn(b'Sandwich', resp_prod.data)
        self.assertNotIn(b'Test Beer', resp_prod.data)

    def test_debt_export_ordering(self):
        with self.app.app_context():
            # Create users:
            # - Zackarias (with debt)
            # - Adam (with debt)
            # - Beatrice (no debt)
            # - Aaron (no debt)
            User.add('zack', 'Zackarias')
            User.add('adam', 'Adam')
            User.add('beatrice', 'Beatrice')
            User.add('aaron', 'Aaron')

        # Give debt to Zackarias and Adam
        self.client.post('/user/zack/buy', data={'barcode': 'beer_123'}, follow_redirects=True)
        self.client.post('/user/adam/buy', data={'barcode': 'beer_123'}, follow_redirects=True)

        resp = self.client.get('/admin/export')
        self.assertEqual(resp.status_code, 200)

        html = resp.data.decode('utf-8')
        # In export table, debtor 'Adam' should come before debtor 'Zackarias'
        pos_adam = html.find('Adam')
        pos_zack = html.find('Zackarias')
        # Debt-free 'Aaron' and 'Beatrice' should come AFTER all debtors
        pos_aaron = html.find('Aaron')
        pos_beatrice = html.find('Beatrice')

        self.assertTrue(pos_adam != -1 and pos_zack != -1)
        self.assertTrue(pos_aaron != -1 and pos_beatrice != -1)

        # Debtors first (alphabetically: Adam < Zackarias)
        self.assertLess(pos_adam, pos_zack)
        # All debtors come before non-debtors (Zackarias < Aaron)
        self.assertLess(pos_zack, pos_aaron)
        # Non-debtors alphabetical: Aaron < Beatrice
        self.assertLess(pos_aaron, pos_beatrice)

    def test_delete_hide_user_and_restore(self):
        with self.app.app_context():
            User.add('wrong_user', 'Mistake User')
            user = User.get_by_barcode('wrong_user')
            self.assertIsNotNone(user)
            self.assertFalse(user.hidden())

        # Delete (soft-delete / hide) the user via admin
        resp = self.client.get('/admin/user/wrong_user/delete', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        with self.app.app_context():
            user = User.get_by_barcode('wrong_user')
            self.assertTrue(user.hidden())

            # User is excluded from default User.all() list
            all_users = User.all()
            self.assertNotIn('wrong_user', [u.barcode for u in all_users])

            # User is present in all_hidden() list
            hidden_users = User.all_hidden()
            self.assertIn('wrong_user', [u.barcode for u in hidden_users])

        # Normal admin list doesn't show the hidden user
        resp_list = self.client.get('/admin/user')
        self.assertEqual(resp_list.status_code, 200)
        self.assertNotIn(b'Mistake User', resp_list.data)

        # Hidden user view (/admin/user?hidden=1) DOES show the user
        resp_hidden_list = self.client.get('/admin/user?hidden=1')
        self.assertEqual(resp_hidden_list.status_code, 200)
        self.assertIn(b'Mistake User', resp_hidden_list.data)

        # Scanning the hidden user barcode at kiosk home rejects it
        resp_kiosk = self.client.post('/user', data={'barcode': 'wrong_user'}, follow_redirects=True)
        self.assertIn('matches neither a user nor a product', resp_kiosk.data.decode('utf-8'))

        # Direct navigation to /user/wrong_user redirects back to kiosk home
        resp_direct = self.client.get('/user/wrong_user', follow_redirects=False)
        self.assertEqual(resp_direct.status_code, 302)
        self.assertEqual(resp_direct.headers['Location'], '/')

        # Re-adding a user with the same barcode (created by mistake, 0 transactions) reuses and unhides it
        resp_readd = self.client.post('/admin/user/add', data={
            'barcode': 'wrong_user',
            'name': 'Corrected Name'
        }, follow_redirects=True)
        self.assertEqual(resp_readd.status_code, 200)

        with self.app.app_context():
            user_readded = User.get_by_barcode('wrong_user')
            self.assertFalse(user_readded.hidden())
            self.assertEqual(user_readded.name, 'Corrected Name')

            # Test restoring a user explicitly via /admin/user/<barcode>/restore
            user_readded.hide()
            self.assertTrue(user_readded.hidden())

        resp_restore = self.client.get('/admin/user/wrong_user/restore', follow_redirects=True)
        self.assertEqual(resp_restore.status_code, 200)
        with self.app.app_context():
            user_restored = User.get_by_barcode('wrong_user')
            self.assertFalse(user_restored.hidden())

    def test_delete_hide_product_and_restore(self):
        with self.app.app_context():
            cat = Category.get_by_name('Öl')
            Product.add('wrong_prod', 'Mistake Beer', 25.0, cat.id)
            prod = Product.get_by_barcode('wrong_prod')
            self.assertIsNotNone(prod)
            self.assertFalse(prod.hidden())

        # Delete (soft-delete / hide) product via admin
        resp = self.client.get('/admin/product/wrong_prod/delete', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        with self.app.app_context():
            prod = Product.get_by_barcode('wrong_prod')
            self.assertTrue(prod.hidden())

            # Product is excluded from default Product.all()
            all_prods = Product.all()
            self.assertNotIn('wrong_prod', [p.barcode for p in all_prods])

            # Product is present in all_hidden()
            hidden_prods = Product.all_hidden()
            self.assertIn('wrong_prod', [p.barcode for p in hidden_prods])

        # Normal admin list doesn't show the hidden product
        resp_list = self.client.get('/admin/product')
        self.assertEqual(resp_list.status_code, 200)
        self.assertNotIn(b'Mistake Beer', resp_list.data)

        # Hidden product view (/admin/product?hidden=1) DOES show the product
        resp_hidden_list = self.client.get('/admin/product?hidden=1')
        self.assertEqual(resp_hidden_list.status_code, 200)
        self.assertIn(b'Mistake Beer', resp_hidden_list.data)

        # Scanning the hidden product barcode at kiosk home is rejected
        resp_kiosk = self.client.post('/user', data={'barcode': 'wrong_prod'}, follow_redirects=True)
        self.assertIn('matches neither a user nor a product', resp_kiosk.data.decode('utf-8'))

        # Purchasing hidden product as a user is rejected
        resp_buy = self.client.post('/user/test_user/buy', data={'barcode': 'wrong_prod'}, follow_redirects=True)
        self.assertIn('Product does not exist', resp_buy.data.decode('utf-8'))

        # Direct navigation to /product/wrong_prod redirects back to kiosk home
        resp_direct = self.client.get('/product/wrong_prod', follow_redirects=False)
        self.assertEqual(resp_direct.status_code, 302)
        self.assertEqual(resp_direct.headers['Location'], '/')

        # Re-adding a product with the same barcode (0 transactions) reuses and unhides it
        with self.app.app_context():
            cat = Category.get_by_name('Öl')
            cat_id = cat.id

        resp_readd = self.client.post('/admin/product/add', data={
            'barcode': 'wrong_prod',
            'name': 'Corrected Beer',
            'price': '26.0',
            'category': str(cat_id)
        }, follow_redirects=True)
        self.assertEqual(resp_readd.status_code, 200)

        with self.app.app_context():
            prod_readded = Product.get_by_barcode('wrong_prod')
            self.assertFalse(prod_readded.hidden())
            self.assertEqual(prod_readded.name, 'Corrected Beer')

            # Test restoring a product explicitly via /admin/product/<barcode>/restore
            prod_readded.hide()
            self.assertTrue(prod_readded.hidden())

        resp_restore = self.client.get('/admin/product/wrong_prod/restore', follow_redirects=True)
        self.assertEqual(resp_restore.status_code, 200)
        with self.app.app_context():
            prod_restored = Product.get_by_barcode('wrong_prod')
            self.assertFalse(prod_restored.hidden())

    def test_admin_purchase_stats_range(self):
        import datetime

        today = datetime.date.today()
        today_str = today.strftime('%Y-%m-%d')
        four_weeks_ago_str = (today - datetime.timedelta(days=28)).strftime('%Y-%m-%d')

        # 1. Initial empty state with default 4-week range
        resp = self.client.get('/admin/purchases')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('Köpstatistik', html)
        self.assertIn(f'value="{four_weeks_ago_str}"', html)
        self.assertIn(f'value="{today_str}"', html)
        self.assertIn('Inga produkter har blivit köpta', html)

        # 2. Make purchases: 2 beers and 1 sandwich
        self.client.post('/user/test_user/buy', data={'barcode': 'beer_123'}, follow_redirects=True)
        self.client.post('/user/test_user/buy', data={'barcode': 'beer_123'}, follow_redirects=True)
        self.client.post('/user/test_user/buy', data={'barcode': 'food_123'}, follow_redirects=True)

        # 3. Verify purchases show up within default 4-week range sorted most to least purchased
        resp_after = self.client.get('/admin/purchases')
        self.assertEqual(resp_after.status_code, 200)
        html_after = resp_after.data.decode('utf-8')
        self.assertIn('Test Beer', html_after)
        self.assertIn('Sandwich', html_after)
        self.assertIn('55.0 kr', html_after)
        self.assertIn('3 st', html_after)
        # Test Beer (2 st) should appear before Sandwich (1 st) in product table
        idx_beer = html_after.find('Test Beer')
        idx_sandwich = html_after.find('Sandwich')
        self.assertTrue(idx_beer != -1 and idx_sandwich != -1 and idx_beer < idx_sandwich)

        # 4. Custom range that excludes today
        past_start = (today - datetime.timedelta(days=100)).strftime('%Y-%m-%d')
        past_end = (today - datetime.timedelta(days=50)).strftime('%Y-%m-%d')
        resp_excluded = self.client.get(f'/admin/purchases?start_date={past_start}&end_date={past_end}')
        self.assertEqual(resp_excluded.status_code, 200)
        html_excluded = resp_excluded.data.decode('utf-8')
        self.assertIn('Inga produkter har blivit köpta', html_excluded)
        self.assertNotIn('Test Beer', html_excluded)

        # 5. Swapped range (start > end) should normalize properly
        resp_swapped = self.client.get(f'/admin/purchases?start_date={today_str}&end_date={four_weeks_ago_str}')
        self.assertEqual(resp_swapped.status_code, 200)
        self.assertIn('Test Beer', resp_swapped.data.decode('utf-8'))

        # 6. CSV Product ranking Export
        resp_prod_csv = self.client.get(f'/admin/purchases/export_products.csv?start_date={four_weeks_ago_str}&end_date={today_str}')
        self.assertEqual(resp_prod_csv.status_code, 200)
        self.assertEqual(resp_prod_csv.mimetype, 'text/csv')
        csv_prod_content = resp_prod_csv.data.decode('utf-8')
        self.assertIn('Test Beer', csv_prod_content)
        self.assertIn('Sandwich', csv_prod_content)

        # 7. CSV Raw transactions Export with day/month/year date formatting
        resp_csv = self.client.get(f'/admin/purchases/export.csv?start_date={four_weeks_ago_str}&end_date={today_str}')
        self.assertEqual(resp_csv.status_code, 200)
        self.assertEqual(resp_csv.mimetype, 'text/csv')
        csv_content = resp_csv.data.decode('utf-8')
        self.assertIn('Test Beer', csv_content)
        self.assertIn('Sandwich', csv_content)
        self.assertIn('Test User', csv_content)
        today_dmy = today.strftime('%d/%m/%Y')
        self.assertIn(today_dmy, csv_content)
        self.assertIn(today_dmy, html_after)

        # 8. Verify user transactions display in day/month/year format
        with self.app.app_context():
            user = User.get_by_barcode('test_user')
            txs = user.transactions()
            self.assertTrue(txs[0]['added'].startswith(today_dmy))

if __name__ == '__main__':
    unittest.main()

