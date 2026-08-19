import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as ecommerce_app


class CheckoutUpgradeTests(unittest.TestCase):
    def setUp(self):
        ecommerce_app.configure_test_database()
        self.client = ecommerce_app.app.test_client()
        with ecommerce_app.app.app_context():
            ecommerce_app.db.drop_all()
            ecommerce_app.db.create_all()

            # Create Users
            self.customer1 = ecommerce_app.User(
                username="customer1",
                email="cust1@example.com",
                password=ecommerce_app.generate_password_hash("pass123"),
                is_admin=False,
            )
            self.customer2 = ecommerce_app.User(
                username="customer2",
                email="cust2@example.com",
                password=ecommerce_app.generate_password_hash("pass123"),
                is_admin=False,
            )
            self.admin = ecommerce_app.User(
                username="adminuser",
                email="admin@example.com",
                password=ecommerce_app.generate_password_hash("admin123"),
                is_admin=True,
            )

            # Create Products
            self.product1 = ecommerce_app.Product(
                name="Dell Inspiron Laptop",
                price=50000.0,
                image="laptop.jpg",
                category="electronics",
                description="High performance laptop",
                stock=5,
            )
            self.product2 = ecommerce_app.Product(
                name="Converse Shoes",
                price=3000.0,
                image="shoe.jpg",
                category="fashion",
                description="Canvas shoes",
                stock=2,
            )

            ecommerce_app.db.session.add_all([self.customer1, self.customer2, self.admin, self.product1, self.product2])
            ecommerce_app.db.session.commit()

            self.c1_id = self.customer1.id
            self.c2_id = self.customer2.id
            self.admin_id = self.admin.id
            self.p1_id = self.product1.id
            self.p2_id = self.product2.id

    def test_stock_limits_in_cart_addition_and_increase(self):
        """Cart cannot add or increase quantity beyond available stock."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.c1_id
                session["username"] = "customer1"

            # Product 2 has stock = 2. Add twice.
            client.get(f"/add_to_cart/{self.p2_id}")
            client.get(f"/add_to_cart/{self.p2_id}")

            with client.session_transaction() as session:
                self.assertEqual(session["cart"][str(self.p2_id)], 2)

            # Try to add a 3rd time via add_to_cart (should be blocked)
            res_over = client.get(f"/add_to_cart/{self.p2_id}", follow_redirects=True)
            self.assertIn(b"Cannot add more units", res_over.data)

            with client.session_transaction() as session:
                self.assertEqual(session["cart"][str(self.p2_id)], 2)

            # Try to increase quantity via POST /increase_quantity (should be blocked)
            res_inc = client.post(f"/increase_quantity/{self.p2_id}", follow_redirects=True)
            self.assertIn(b"Maximum available stock", res_inc.data)

            with client.session_transaction() as session:
                self.assertEqual(session["cart"][str(self.p2_id)], 2)

    def test_successful_checkout_persists_shipping_payment_and_deducts_stock(self):
        """Placing an order stores shipping, payment method, calculates price, reduces stock, clears cart."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.c1_id
                session["username"] = "customer1"
                # Order 2 units of Laptop (price=50000 each)
                session["cart"] = {str(self.p1_id): 2}

            checkout_data = {
                "full_name": "Aarav Sharma",
                "email": "aarav@example.com",
                "phone": "+91 9876543210",
                "address": "Flat 402, Skyline Towers, MG Road",
                "city": "Mumbai",
                "state": "Maharashtra",
                "pin": "400001",
                "payment_method": "cod",
            }

            response = client.post("/checkout", data=checkout_data, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Order Placed Successfully", response.data)
            self.assertIn(b"Aarav Sharma", response.data)
            self.assertIn(b"Flat 402, Skyline Towers", response.data)
            self.assertIn(b"Cash on Delivery", response.data)

            # Check cart was cleared in session
            with client.session_transaction() as session:
                self.assertEqual(session.get("cart"), {})

            # Verify Database
            with ecommerce_app.app.app_context():
                # Stock should be reduced from 5 to 3
                product = ecommerce_app.Product.query.get(self.p1_id)
                self.assertEqual(product.stock, 3)

                order = ecommerce_app.Order.query.filter_by(user_id=self.c1_id).first()
                self.assertIsNotNone(order)
                self.assertEqual(order.status, "Pending")
                self.assertEqual(order.shipping_full_name, "Aarav Sharma")
                self.assertEqual(order.shipping_phone, "+91 9876543210")
                self.assertEqual(order.shipping_address, "Flat 402, Skyline Towers, MG Road")
                self.assertEqual(order.shipping_city, "Mumbai")
                self.assertEqual(order.shipping_state, "Maharashtra")
                self.assertEqual(order.shipping_pin, "400001")
                self.assertEqual(order.payment_method, "Cash on Delivery")
                self.assertTrue(order.order_number.startswith("ZACH-"))
                # 2 * 50000 = 100000, 10% discount = 10000, free shipping = 90000 total
                self.assertEqual(order.total_amount, 90000.0)

                # Verify items
                self.assertEqual(len(order.items), 1)
                self.assertEqual(order.items[0].product_name, "Dell Inspiron Laptop")
                self.assertEqual(order.items[0].quantity, 2)
                self.assertEqual(order.items[0].unit_price, 50000.0)

    def test_checkout_rejects_insufficient_stock(self):
        """Checkout fails atomically if stock is insufficient at time of order."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.c1_id
                session["username"] = "customer1"
                # Customer has 2 in cart, but stock will be set to 1
                session["cart"] = {str(self.p2_id): 2}

            # Set stock to 1 directly
            with ecommerce_app.app.app_context():
                p = ecommerce_app.Product.query.get(self.p2_id)
                p.stock = 1
                ecommerce_app.db.session.commit()

            checkout_data = {
                "full_name": "John Doe",
                "email": "john@example.com",
                "phone": "9876543210",
                "address": "123 Street",
                "city": "Delhi",
                "state": "Delhi",
                "pin": "110001",
                "payment_method": "upi",
            }

            response = client.post("/checkout", data=checkout_data, follow_redirects=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Insufficient stock available", response.data)

            # Verify no order created and stock remains 1
            with ecommerce_app.app.app_context():
                order_count = ecommerce_app.Order.query.count()
                self.assertEqual(order_count, 0)
                p = ecommerce_app.Product.query.get(self.p2_id)
                self.assertEqual(p.stock, 1)

    def test_customer_authorization_order_access(self):
        """Customer cannot view another customer's order or confirmation."""
        # Create order for customer 1
        with ecommerce_app.app.app_context():
            order = ecommerce_app.Order(
                user_id=self.c1_id,
                order_number="ZACH-TESTCUST1",
                status="Pending",
                total_amount=5000.0,
                shipping_full_name="Customer One",
            )
            ecommerce_app.db.session.add(order)
            ecommerce_app.db.session.commit()
            order_id = order.id

        # Login as customer 2
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.c2_id
                session["username"] = "customer2"

            # Attempt to view customer 1's order details -> 404
            res_details = client.get(f"/order/{order_id}")
            self.assertEqual(res_details.status_code, 404)

            # Attempt to view customer 1's confirmation -> 404
            res_success = client.get(f"/order-success/{order_id}")
            self.assertEqual(res_success.status_code, 404)

    def test_admin_order_details_and_status_lifecycle(self):
        """Admin can view full order with shipping and update status through the lifecycle."""
        with ecommerce_app.app.app_context():
            order = ecommerce_app.Order(
                user_id=self.c1_id,
                order_number="ZACH-ADMINTEST",
                status="Pending",
                total_amount=3000.0,
                shipping_full_name="Rohan Gupta",
                shipping_phone="9988776655",
                shipping_address="45 Park Avenue",
                shipping_city="Bangalore",
                shipping_state="Karnataka",
                shipping_pin="560001",
                payment_method="UPI",
            )
            ecommerce_app.db.session.add(order)
            ecommerce_app.db.session.commit()
            order_id = order.id

        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.admin_id
                session["username"] = "adminuser"

            # View admin order details
            res = client.get(f"/admin/order/{order_id}")
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Rohan Gupta", res.data)
            self.assertIn(b"45 Park Avenue", res.data)
            self.assertIn(b"UPI", res.data)
            self.assertIn(b"Pending", res.data)

            # Advance status using change_order_status
            client.get(f"/admin/order/{order_id}/status")
            with ecommerce_app.app.app_context():
                o = ecommerce_app.Order.query.get(order_id)
                self.assertEqual(o.status, "Confirmed")

            # Update status explicitly via POST to Shipped
            client.post(f"/admin/order/{order_id}", data={"status": "Shipped"})
            with ecommerce_app.app.app_context():
                o = ecommerce_app.Order.query.get(order_id)
                self.assertEqual(o.status, "Shipped")


if __name__ == "__main__":
    unittest.main()
