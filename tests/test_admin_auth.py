import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as ecommerce_app
from make_admin import make_admin


class AdminAuthTests(unittest.TestCase):
    def setUp(self):
        ecommerce_app.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SECRET_KEY="test_secret_key",
        )
        self.client = ecommerce_app.app.test_client()
        with ecommerce_app.app.app_context():
            ecommerce_app.db.drop_all()
            ecommerce_app.db.create_all()

            # Create normal customer
            self.customer = ecommerce_app.User(
                username="customer_user",
                email="customer@example.com",
                password=ecommerce_app.generate_password_hash("pass123"),
                is_admin=False,
                created_at=datetime.utcnow(),
            )
            # Create admin user
            self.admin = ecommerce_app.User(
                username="admin_user",
                email="admin@example.com",
                password=ecommerce_app.generate_password_hash("admin123"),
                is_admin=True,
                created_at=datetime.utcnow(),
            )
            # Sample product
            self.product = ecommerce_app.Product(
                name="Gaming Laptop",
                price=85000.0,
                image="laptop.jpg",
                category="electronics",
                description="High performance gaming laptop",
                stock=5,
            )
            ecommerce_app.db.session.add_all([self.customer, self.admin, self.product])
            ecommerce_app.db.session.commit()

            self.customer_id = self.customer.id
            self.admin_id = self.admin.id
            self.product_id = self.product.id

            # Sample order
            self.order = ecommerce_app.Order(
                user_id=self.customer_id,
                order_number="ZACH-TEST101",
                status="Processing",
                total_amount=85000.0,
                created_at=datetime.utcnow(),
            )
            ecommerce_app.db.session.add(self.order)
            ecommerce_app.db.session.commit()
            self.order_id = self.order.id

    def test_case_c_logged_out_visitor_redirected_from_admin_routes(self):
        """CASE C: Logged-out visitor manually opens /admin or admin endpoints -> redirect to login."""
        response = self.client.get("/admin", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

        response = self.client.get("/admin/orders", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

        response = self.client.get(f"/edit_product/{self.product_id}", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

        response = self.client.get(f"/delete_product/{self.product_id}", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

        response = self.client.get(f"/admin/order/{self.order_id}/status", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

        response = self.client.get("/admin/users", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_case_a_and_d_normal_customer_denied_admin_access(self):
        """CASE A & D: Normal customer logs in -> admin routes return 403 Forbidden, navbar hides Admin link."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.customer_id
                session["username"] = "customer_user"

            # Check navbar has no Admin link for normal customer
            home_resp = client.get("/")
            self.assertEqual(home_resp.status_code, 200)
            self.assertNotIn(b'href="/admin"', home_resp.data)

            # Check admin dashboard access -> 403
            admin_resp = client.get("/admin")
            self.assertEqual(admin_resp.status_code, 403)

            # Check admin orders access -> 403
            orders_resp = client.get("/admin/orders")
            self.assertEqual(orders_resp.status_code, 403)

            # Check admin users access -> 403
            users_resp = client.get("/admin/users")
            self.assertEqual(users_resp.status_code, 403)

            # Check edit product access -> 403
            edit_resp = client.get(f"/edit_product/{self.product_id}")
            self.assertEqual(edit_resp.status_code, 403)

            # Check delete product access -> 403
            del_resp = client.get(f"/delete_product/{self.product_id}")
            self.assertEqual(del_resp.status_code, 403)

            # Check change order status access -> 403
            status_resp = client.get(f"/admin/order/{self.order_id}/status")
            self.assertEqual(status_resp.status_code, 403)

    def test_case_b_admin_user_can_access_all_admin_features(self):
        """CASE B: Admin user logs in -> sees Admin link, can access /admin, /admin/users, add/edit/delete product, manage orders."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.admin_id
                session["username"] = "admin_user"

            # Check navbar contains Admin link
            home_resp = client.get("/")
            self.assertEqual(home_resp.status_code, 200)
            self.assertIn(b'href="/admin"', home_resp.data)

            # Check /admin dashboard renders and has link to /admin/users
            admin_resp = client.get("/admin")
            self.assertEqual(admin_resp.status_code, 200)
            self.assertIn(b"ZACHIFY ADMIN", admin_resp.data)
            self.assertIn(b"Store Dashboard", admin_resp.data)
            self.assertIn(b'href="/admin/users"', admin_resp.data)

            # Check /admin/users renders correctly
            users_resp = client.get("/admin/users")
            self.assertEqual(users_resp.status_code, 200)
            self.assertIn(b"Registered Users", users_resp.data)
            self.assertIn(b"Total Users", users_resp.data)
            self.assertIn(b"Total Admins", users_resp.data)
            self.assertIn(b"Total Customers", users_resp.data)
            self.assertIn(b"admin_user", users_resp.data)
            self.assertIn(b"customer_user", users_resp.data)
            self.assertIn(b"admin@example.com", users_resp.data)
            self.assertIn(b"customer@example.com", users_resp.data)
            self.assertIn(b"Admin", users_resp.data)
            self.assertIn(b"Customer", users_resp.data)
            self.assertIn(b"Back to Dashboard", users_resp.data)
            # Ensure password hash is NOT leaked
            self.assertNotIn(b"pbkdf2:sha256", users_resp.data)
            self.assertNotIn(b"admin123", users_resp.data)
            self.assertNotIn(b"pass123", users_resp.data)

            # Check add product via POST /admin
            add_resp = client.post(
                "/admin",
                data={
                    "name": "New Admin Item",
                    "price": "1999.0",
                    "image": "item.jpg",
                    "category": "accessories",
                    "description": "Brand new accessory",
                    "stock": "15",
                },
                follow_redirects=True,
            )
            self.assertEqual(add_resp.status_code, 200)
            with ecommerce_app.app.app_context():
                created = ecommerce_app.Product.query.filter_by(name="New Admin Item").first()
                self.assertIsNotNone(created)
                new_id = created.id

            # Check edit product
            edit_resp = client.post(
                f"/edit_product/{new_id}",
                data={
                    "name": "Updated Admin Item",
                    "price": "2499.0",
                    "image": "item.jpg",
                    "category": "accessories",
                    "description": "Updated description",
                    "stock": "20",
                },
                follow_redirects=False,
            )
            self.assertEqual(edit_resp.status_code, 302)
            with ecommerce_app.app.app_context():
                updated = ecommerce_app.Product.query.get(new_id)
                self.assertEqual(updated.name, "Updated Admin Item")
                self.assertEqual(updated.stock, 20)

            # Check admin orders
            orders_resp = client.get("/admin/orders")
            self.assertEqual(orders_resp.status_code, 200)
            self.assertIn(b"ZACH-TEST101", orders_resp.data)

            # Check change order status
            status_resp = client.get(f"/admin/order/{self.order_id}/status", follow_redirects=False)
            self.assertEqual(status_resp.status_code, 302)
            with ecommerce_app.app.app_context():
                order = ecommerce_app.Order.query.get(self.order_id)
                self.assertEqual(order.status, "Packed")

            # Check delete product
            del_resp = client.get(f"/delete_product/{new_id}", follow_redirects=False)
            self.assertEqual(del_resp.status_code, 302)
            with ecommerce_app.app.app_context():
                deleted = ecommerce_app.Product.query.get(new_id)
                self.assertIsNone(deleted)

    def test_make_admin_promotion(self):
        """Verify user promotion to admin."""
        with ecommerce_app.app.app_context():
            user = ecommerce_app.User.query.filter_by(email="customer@example.com").first()
            self.assertFalse(user.is_admin)

        make_admin("customer@example.com")

        with ecommerce_app.app.app_context():
            updated_user = ecommerce_app.User.query.filter_by(email="customer@example.com").first()
            self.assertTrue(updated_user.is_admin)


if __name__ == "__main__":
    unittest.main()
