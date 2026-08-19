import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as ecommerce_app


class CheckoutRouteTests(unittest.TestCase):
    def setUp(self):
        ecommerce_app.configure_test_database()
        self.client = ecommerce_app.app.test_client()
        with ecommerce_app.app.app_context():
            ecommerce_app.db.drop_all()
            ecommerce_app.db.create_all()

    def test_guest_checkout_redirects_to_login(self):
        with ecommerce_app.app.test_client() as client:
            with client.session_transaction() as session:
                session["cart"] = {"1": 1}
            response = client.get("/checkout")
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login", response.headers["Location"])

    def test_checkout_page_renders_with_cart_summary(self):
        with ecommerce_app.app.app_context():
            user = ecommerce_app.User(
                username="testuser",
                email="test@example.com",
                password=ecommerce_app.generate_password_hash("password123"),
            )
            ecommerce_app.db.session.add(user)
            product = ecommerce_app.Product(
                name="Test Laptop",
                price=1000.0,
                image="laptop.jpg",
                category="electronics",
                description="Test product",
                stock=3,
            )
            ecommerce_app.db.session.add(product)
            ecommerce_app.db.session.commit()
            user_id = user.id
            product_id = product.id

        with ecommerce_app.app.test_client() as client:
            with client.session_transaction() as session:
                session["user_id"] = user_id
                session["username"] = "testuser"
                session["cart"] = {str(product_id): 2}
            response = client.get("/checkout")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Checkout", response.data)
        self.assertIn(b"Place Order", response.data)


if __name__ == "__main__":
    unittest.main()
