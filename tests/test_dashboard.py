import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as ecommerce_app


class DashboardRouteTests(unittest.TestCase):
    def setUp(self):
        ecommerce_app.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
        self.client = ecommerce_app.app.test_client()
        with ecommerce_app.app.app_context():
            ecommerce_app.db.drop_all()
            ecommerce_app.db.create_all()

    def test_dashboard_redirects_guests_to_login(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_dashboard_renders_logged_in_user_data(self):
        with ecommerce_app.app.app_context():
            user = ecommerce_app.User(
                username="Zach",
                email="zach@example.com",
                password=ecommerce_app.generate_password_hash("secret123"),
                created_at=datetime.utcnow(),
            )
            ecommerce_app.db.session.add(user)
            ecommerce_app.db.session.flush()

            product = ecommerce_app.Product(
                name="Test Laptop",
                price=1000.0,
                image="laptop.jpg",
                category="electronics",
                description="Test product",
                stock=3,
            )
            ecommerce_app.db.session.add(product)
            ecommerce_app.db.session.flush()

            order = ecommerce_app.Order(
                user_id=user.id,
                order_number="ORD-1001",
                status="Processing",
                total_amount=1000.0,
                created_at=datetime.utcnow(),
            )
            ecommerce_app.db.session.add(order)
            ecommerce_app.db.session.flush()

            ecommerce_app.db.session.add(
                ecommerce_app.OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.name,
                    product_image=product.image,
                    quantity=1,
                    unit_price=product.price,
                    total_price=product.price,
                )
            )
            ecommerce_app.db.session.add(
                ecommerce_app.Wishlist(user_id=user.id, product_id=product.id)
            )
            ecommerce_app.db.session.commit()
            user_id = user.id
            username = user.username

        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = user_id
                session["username"] = username

            response = client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome back", response.data)
        self.assertIn(b"Zach", response.data)
        self.assertIn(b"Test Laptop", response.data)
        self.assertIn(b"Processing", response.data)
