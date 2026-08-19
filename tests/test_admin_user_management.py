import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as ecommerce_app


class AdminUserManagementTests(unittest.TestCase):
    def setUp(self):
        ecommerce_app.configure_test_database()
        self.client = ecommerce_app.app.test_client()
        with ecommerce_app.app.app_context():
            ecommerce_app.db.drop_all()
            ecommerce_app.db.create_all()

            # Normal Customer
            self.customer = ecommerce_app.User(
                username="jane_shopper",
                email="jane@example.com",
                password=ecommerce_app.generate_password_hash("pass123"),
                is_admin=False,
                created_at=datetime.utcnow(),
            )
            # Admin User
            self.admin = ecommerce_app.User(
                username="store_admin",
                email="admin@example.com",
                password=ecommerce_app.generate_password_hash("admin123"),
                is_admin=True,
                created_at=datetime.utcnow(),
            )
            # Second Admin User
            self.admin2 = ecommerce_app.User(
                username="secondary_admin",
                email="admin2@example.com",
                password=ecommerce_app.generate_password_hash("admin123"),
                is_admin=True,
                created_at=datetime.utcnow(),
            )
            # System Default Admin
            self.default_admin = ecommerce_app.User(
                username="shahal",
                email="mhdshahal3182005@gmail.com",
                password=ecommerce_app.generate_password_hash("shahal123"),
                is_admin=True,
                created_at=datetime.utcnow(),
            )
            # Product
            self.product = ecommerce_app.Product(
                name="Wireless Headphones",
                price=4500.0,
                image="headphone.jpg",
                category="electronics",
                description="Premium headphones",
                stock=15,
            )

            ecommerce_app.db.session.add_all([self.customer, self.admin, self.admin2, self.default_admin, self.product])
            ecommerce_app.db.session.commit()

            self.customer_id = self.customer.id
            self.admin_id = self.admin.id
            self.admin2_id = self.admin2.id
            self.default_admin_id = self.default_admin.id
            self.product_id = self.product.id

            # Order for customer
            self.order = ecommerce_app.Order(
                user_id=self.customer_id,
                order_number="ZACH-TEST-8801",
                total_amount=4500.0,
                status="Processing",
                created_at=datetime.utcnow(),
            )
            ecommerce_app.db.session.add(self.order)
            ecommerce_app.db.session.commit()

            self.order_item = ecommerce_app.OrderItem(
                order_id=self.order.id,
                product_id=self.product_id,
                product_name="Wireless Headphones",
                product_image="headphone.jpg",
                quantity=1,
                unit_price=4500.0,
                total_price=4500.0,
            )
            ecommerce_app.db.session.add(self.order_item)
            ecommerce_app.db.session.commit()

    def login_as_admin(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin_id
            sess["username"] = "store_admin"

    def login_as_customer(self):
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.customer_id
            sess["username"] = "jane_shopper"

    def test_guest_cannot_access_user_management(self):
        response = self.client.get("/admin/users", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

    def test_customer_cannot_access_user_management(self):
        self.login_as_customer()
        response = self.client.get("/admin/users")
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_toggle_admin_status(self):
        self.login_as_customer()
        response = self.client.post(f"/admin/user/{self.customer_id}/toggle-admin")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_view_users_list(self):
        self.login_as_admin()
        response = self.client.get("/admin/users")
        self.assertEqual(response.status_code, 200)
        content = response.data.decode("utf-8")
        self.assertIn("jane_shopper", content)
        self.assertIn("store_admin", content)
        self.assertIn("mhdshahal3182005@gmail.com", content)
        self.assertIn("1 Order", content)

    def test_admin_users_search_filter(self):
        self.login_as_admin()
        # Search by username
        response = self.client.get("/admin/users?q=jane")
        self.assertEqual(response.status_code, 200)
        content = response.data.decode("utf-8")
        self.assertIn("jane_shopper", content)
        self.assertIn("jane@example.com", content)
        self.assertNotIn("secondary_admin", content)
        self.assertNotIn("admin2@example.com", content)

        # Filter by role
        response_role = self.client.get("/admin/users?role=customer")
        self.assertEqual(response_role.status_code, 200)
        content_role = response_role.data.decode("utf-8")
        self.assertIn("jane_shopper", content_role)
        self.assertNotIn("secondary_admin", content_role)

    def test_admin_can_view_user_details(self):
        self.login_as_admin()
        response = self.client.get(f"/admin/user/{self.customer_id}")
        self.assertEqual(response.status_code, 200)
        content = response.data.decode("utf-8")
        self.assertIn("jane_shopper", content)
        self.assertIn("jane@example.com", content)
        self.assertIn("ZACH-TEST-8801", content)
        self.assertIn("₹4500.00", content)

    def test_admin_can_promote_and_demote_user(self):
        self.login_as_admin()
        # Promote customer to admin
        response = self.client.post(f"/admin/user/{self.customer_id}/toggle-admin", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with ecommerce_app.app.app_context():
            user = ecommerce_app.User.query.get(self.customer_id)
            self.assertTrue(user.is_admin)

        # Demote user back to customer
        response = self.client.post(f"/admin/user/{self.customer_id}/toggle-admin", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with ecommerce_app.app.app_context():
            user = ecommerce_app.User.query.get(self.customer_id)
            self.assertFalse(user.is_admin)

    def test_lockout_protection_prevent_self_demotion(self):
        self.login_as_admin()
        # Attempt to demote self
        response = self.client.post(f"/admin/user/{self.admin_id}/toggle-admin", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        content = response.data.decode("utf-8")
        self.assertIn("cannot revoke your own administrator privileges", content.lower())
        with ecommerce_app.app.app_context():
            user = ecommerce_app.User.query.get(self.admin_id)
            self.assertTrue(user.is_admin)

    def test_lockout_protection_prevent_default_admin_demotion(self):
        self.login_as_admin()
        # Attempt to demote default system admin
        response = self.client.post(f"/admin/user/{self.default_admin_id}/toggle-admin", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        content = response.data.decode("utf-8")
        self.assertIn("designated system administrator", content.lower())
        with ecommerce_app.app.app_context():
            user = ecommerce_app.User.query.get(self.default_admin_id)
            self.assertTrue(user.is_admin)

    def test_user_details_404_for_invalid_id(self):
        self.login_as_admin()
        response = self.client.get("/admin/user/999999")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
