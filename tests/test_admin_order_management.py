import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as ecommerce_app


class AdminOrderManagementTests(unittest.TestCase):
    def setUp(self):
        ecommerce_app.configure_test_database()
        self.client = ecommerce_app.app.test_client()
        with ecommerce_app.app.app_context():
            ecommerce_app.db.drop_all()
            ecommerce_app.db.create_all()

            # Normal Customer
            self.customer = ecommerce_app.User(
                username="customer_user",
                email="customer@example.com",
                password=ecommerce_app.generate_password_hash("pass123"),
                is_admin=False,
                created_at=datetime.utcnow(),
            )
            # Admin User
            self.admin = ecommerce_app.User(
                username="admin_user",
                email="admin@example.com",
                password=ecommerce_app.generate_password_hash("admin123"),
                is_admin=True,
                created_at=datetime.utcnow(),
            )
            # Product
            self.product = ecommerce_app.Product(
                name="Wireless Headphones",
                price=4500.0,
                image="headphone.jpg",
                category="electronics",
                description="Premium noise cancelling headphones",
                stock=15,
            )

            ecommerce_app.db.session.add_all([self.customer, self.admin, self.product])
            ecommerce_app.db.session.commit()

            self.customer_id = self.customer.id
            self.admin_id = self.admin.id
            self.product_id = self.product.id

            # Customer Order
            self.order = ecommerce_app.Order(
                user_id=self.customer_id,
                order_number="ZACH-ORD-9901",
                total_amount=9000.0,
                status="Processing",
                created_at=datetime.utcnow(),
            )
            ecommerce_app.db.session.add(self.order)
            ecommerce_app.db.session.flush()

            self.order_item = ecommerce_app.OrderItem(
                order_id=self.order.id,
                product_id=self.product_id,
                product_name="Wireless Headphones",
                product_image="headphone.jpg",
                quantity=2,
                unit_price=4500.0,
                total_price=9000.0,
            )
            ecommerce_app.db.session.add(self.order_item)
            ecommerce_app.db.session.commit()
            self.order_id = self.order.id

    def test_security_guest_redirected_to_login(self):
        """Logged out users cannot access admin orders or order details."""
        res_orders = self.client.get("/admin/orders", follow_redirects=False)
        self.assertEqual(res_orders.status_code, 302)
        self.assertIn("/login", res_orders.headers["Location"])

        res_details = self.client.get(f"/admin/order/{self.order_id}", follow_redirects=False)
        self.assertEqual(res_details.status_code, 302)
        self.assertIn("/login", res_details.headers["Location"])

    def test_security_customer_receives_403(self):
        """Normal logged-in customers receive 403 Forbidden on admin order routes."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.customer_id
                session["username"] = "customer_user"

            res_orders = client.get("/admin/orders")
            self.assertEqual(res_orders.status_code, 403)

            res_details = client.get(f"/admin/order/{self.order_id}")
            self.assertEqual(res_details.status_code, 403)

    def test_admin_view_orders_list_has_view_details_link(self):
        """Admin can view the orders list and sees View Details button."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.admin_id
                session["username"] = "admin_user"

            res = client.get("/admin/orders")
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Customer Orders", res.data)
            self.assertIn(b"ZACH-ORD-9901", res.data)
            self.assertIn(b"customer_user", res.data)
            self.assertIn(b"customer@example.com", res.data)
            self.assertIn(b"View Details", res.data)
            self.assertTrue(
                f"/admin/order/{self.order_id}".encode() in res.data or f"/admin/orders/{self.order_id}".encode() in res.data,
                "Expected link to admin order details"
            )

    def test_admin_view_order_details_page(self):
        """Admin can open dedicated order details page and see customer info, items, and status manager."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.admin_id
                session["username"] = "admin_user"

            res = client.get(f"/admin/order/{self.order_id}")
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Order #ZACH-ORD-9901", res.data)
            self.assertIn(b"customer_user", res.data)
            self.assertIn(b"customer@example.com", res.data)
            self.assertIn(b"Wireless Headphones", res.data)
            self.assertIn(b"4500.00", res.data)
            self.assertIn(b"9000.00", res.data)
            self.assertIn(b"Manage Status", res.data)
            self.assertIn(b"Update Status", res.data)
            self.assertIn(b"Back to Orders", res.data)

    def test_admin_update_order_status(self):
        """Admin can update order status from Order Details page."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.admin_id
                session["username"] = "admin_user"

            # Update status to Shipped
            post_res = client.post(
                f"/admin/order/{self.order_id}",
                data={"status": "Shipped"},
                follow_redirects=True,
            )
            self.assertEqual(post_res.status_code, 200)
            self.assertIn(b"status updated to &#39;Shipped&#39;", post_res.data)

            with ecommerce_app.app.app_context():
                order = ecommerce_app.Order.query.get(self.order_id)
                self.assertEqual(order.status, "Shipped")

            # Update status to Delivered
            post_res2 = client.post(
                f"/admin/order/{self.order_id}",
                data={"status": "Delivered"},
                follow_redirects=True,
            )
            self.assertEqual(post_res2.status_code, 200)

            with ecommerce_app.app.app_context():
                order = ecommerce_app.Order.query.get(self.order_id)
                self.assertEqual(order.status, "Delivered")

    def test_customer_order_pages_continue_working(self):
        """Customer order listing /orders and /order/<id> remain fully functional."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.customer_id
                session["username"] = "customer_user"

            res_cust_orders = client.get("/orders")
            self.assertEqual(res_cust_orders.status_code, 200)
            self.assertIn(b"ZACH-ORD-9901", res_cust_orders.data)

            res_cust_detail = client.get(f"/order/{self.order_id}")
            self.assertEqual(res_cust_detail.status_code, 200)
            self.assertIn(b"ZACH-ORD-9901", res_cust_detail.data)
            self.assertIn(b"Wireless Headphones", res_cust_detail.data)


if __name__ == "__main__":
    unittest.main()
