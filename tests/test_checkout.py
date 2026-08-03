import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as ecommerce_app


class CheckoutRouteTests(unittest.TestCase):
    def setUp(self):
        ecommerce_app.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI="sqlite:///:memory:")
        self.client = ecommerce_app.app.test_client()
        with ecommerce_app.app.app_context():
            ecommerce_app.db.drop_all()
            ecommerce_app.db.create_all()

    def test_checkout_page_renders_with_cart_summary(self):
        with ecommerce_app.app.app_context():
            ecommerce_app.db.session.add(
                ecommerce_app.Product(
                    name="Test Laptop",
                    price=1000.0,
                    image="laptop.jpg",
                    category="electronics",
                    description="Test product",
                    stock=3,
                )
            )
            ecommerce_app.db.session.commit()

        with ecommerce_app.app.test_client() as client:
            with client.session_transaction() as session:
                session["cart"] = {"1": 2}
            response = client.get("/checkout")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Checkout", response.data)
        self.assertIn(b"Place Order", response.data)


if __name__ == "__main__":
    unittest.main()
