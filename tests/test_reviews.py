import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as ecommerce_app


class ReviewSystemTests(unittest.TestCase):
    def setUp(self):
        ecommerce_app.configure_test_database()
        self.client = ecommerce_app.app.test_client()

        with ecommerce_app.app.app_context():
            ecommerce_app.db.drop_all()
            ecommerce_app.db.create_all()

            # Create Customer 1
            self.customer1 = ecommerce_app.User(
                username="customer1",
                email="customer1@example.com",
                password=ecommerce_app.generate_password_hash("pass123"),
                is_admin=False,
                created_at=datetime.utcnow(),
            )
            # Create Customer 2
            self.customer2 = ecommerce_app.User(
                username="customer2",
                email="customer2@example.com",
                password=ecommerce_app.generate_password_hash("pass123"),
                is_admin=False,
                created_at=datetime.utcnow(),
            )
            # Create Admin
            self.admin = ecommerce_app.User(
                username="adminuser",
                email="admin@example.com",
                password=ecommerce_app.generate_password_hash("adminpass"),
                is_admin=True,
                created_at=datetime.utcnow(),
            )

            # Create Products
            self.product1 = ecommerce_app.Product(
                name="Gaming Laptop RTX",
                price=85000.0,
                image="laptop.png",
                category="Laptops",
                description="High performance flagship laptop.",
                stock=10,
            )
            self.product2 = ecommerce_app.Product(
                name="Wireless Headphones ANC",
                price=9500.0,
                image="headphone.png",
                category="Audio",
                description="Noise cancelling audio gear.",
                stock=15,
            )

            ecommerce_app.db.session.add_all([self.customer1, self.customer2, self.admin, self.product1, self.product2])
            ecommerce_app.db.session.commit()

            self.customer1_id = self.customer1.id
            self.customer2_id = self.customer2.id
            self.admin_id = self.admin.id
            self.product1_id = self.product1.id
            self.product2_id = self.product2.id

            # Customer 1 purchases Product 1 in an Order
            self.order1 = ecommerce_app.Order(
                user_id=self.customer1_id,
                order_number="ORD-TEST-001",
                status="Delivered",
                total_amount=85000.0,
                shipping_full_name="Customer One",
                shipping_email="customer1@example.com",
                shipping_phone="9876543210",
                shipping_address="123 Silicon Street",
                shipping_city="Bangalore",
                shipping_state="Karnataka",
                shipping_pin="560001",
                payment_method="UPI",
            )
            ecommerce_app.db.session.add(self.order1)
            ecommerce_app.db.session.commit()

            self.order_item1 = ecommerce_app.OrderItem(
                order_id=self.order1.id,
                product_id=self.product1_id,
                product_name="Gaming Laptop RTX",
                product_image="laptop.png",
                quantity=1,
                unit_price=85000.0,
                total_price=85000.0,
            )
            ecommerce_app.db.session.add(self.order_item1)
            ecommerce_app.db.session.commit()

    def login_as(self, user_id):
        with self.client.session_transaction() as sess:
            sess["user_id"] = user_id

    def test_guest_cannot_submit_review(self):
        response = self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "5", "comment": "Great product!"},
            follow_redirects=True,
        )
        self.assertIn(b"Please login", response.data)

    def test_non_purchaser_cannot_submit_review(self):
        # Customer 2 did not purchase Product 1
        self.login_as(self.customer2_id)
        response = self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "5", "comment": "Trying to review without purchase"},
            follow_redirects=True,
        )
        self.assertIn(b"You can only review products you have purchased", response.data)

        # Ensure review was not stored
        with ecommerce_app.app.app_context():
            review_count = ecommerce_app.Review.query.filter_by(product_id=self.product1_id).count()
            self.assertEqual(review_count, 0)

    def test_verified_purchaser_can_submit_valid_review(self):
        self.login_as(self.customer1_id)
        response = self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "5", "comment": "Superb performance and build quality!"},
            follow_redirects=True,
        )
        self.assertIn(b"submitted successfully", response.data)

        with ecommerce_app.app.app_context():
            review = ecommerce_app.Review.query.filter_by(user_id=self.customer1_id, product_id=self.product1_id).first()
            self.assertIsNotNone(review)
            self.assertEqual(review.rating, 5)
            self.assertEqual(review.comment, "Superb performance and build quality!")

            # Check Product dynamic rating calculation
            product = ecommerce_app.Product.query.get(self.product1_id)
            self.assertEqual(product.review_count, 1)
            self.assertEqual(product.average_rating, 5.0)

    def test_rating_validation_rejects_invalid_ratings(self):
        self.login_as(self.customer1_id)

        # Rating > 5
        response = self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "6", "comment": "Invalid high rating"},
            follow_redirects=True,
        )
        self.assertIn(b"Rating must be between 1 and 5", response.data)

        # Rating < 1
        response = self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "0", "comment": "Invalid low rating"},
            follow_redirects=True,
        )
        self.assertIn(b"Rating must be between 1 and 5", response.data)

        # Non-integer rating
        response = self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "abc", "comment": "Non-numeric rating"},
            follow_redirects=True,
        )
        self.assertIn(b"valid star rating", response.data)

    def test_comment_validation_rejects_empty_or_too_short(self):
        self.login_as(self.customer1_id)

        # Empty comment
        response = self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "5", "comment": "   "},
            follow_redirects=True,
        )
        self.assertIn(b"Review comment cannot be empty", response.data)

        # Less than 3 chars
        response = self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "5", "comment": "hi"},
            follow_redirects=True,
        )
        self.assertIn(b"at least 3 characters", response.data)

    def test_one_review_per_product_per_customer(self):
        self.login_as(self.customer1_id)

        # First review succeeds
        self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "4", "comment": "First review"},
            follow_redirects=True,
        )

        # Second review attempt for same product is rejected
        response = self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "5", "comment": "Duplicate review attempt"},
            follow_redirects=True,
        )
        self.assertIn(b"already reviewed this product", response.data)

        with ecommerce_app.app.app_context():
            reviews = ecommerce_app.Review.query.filter_by(user_id=self.customer1_id, product_id=self.product1_id).all()
            self.assertEqual(len(reviews), 1)
            self.assertEqual(reviews[0].comment, "First review")

    def test_customer_can_edit_own_review(self):
        self.login_as(self.customer1_id)

        # Create initial review
        self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "4", "comment": "Good laptop"},
            follow_redirects=True,
        )

        with ecommerce_app.app.app_context():
            review = ecommerce_app.Review.query.filter_by(user_id=self.customer1_id, product_id=self.product1_id).first()
            review_id = review.id

        # Edit review
        response = self.client.post(
            f"/review/{review_id}/edit",
            data={"rating": "5", "comment": "Updated: Actually this is the best laptop ever!"},
            follow_redirects=True,
        )
        self.assertIn(b"updated successfully", response.data)

        with ecommerce_app.app.app_context():
            updated_review = ecommerce_app.Review.query.get(review_id)
            self.assertEqual(updated_review.rating, 5)
            self.assertEqual(updated_review.comment, "Updated: Actually this is the best laptop ever!")

    def test_customer_cannot_edit_other_user_review(self):
        # Customer 1 creates review
        self.login_as(self.customer1_id)
        self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "4", "comment": "Customer 1 review"},
            follow_redirects=True,
        )

        with ecommerce_app.app.app_context():
            review = ecommerce_app.Review.query.filter_by(user_id=self.customer1_id).first()
            review_id = review.id

        # Customer 2 attempts to edit Customer 1's review
        self.login_as(self.customer2_id)
        response = self.client.post(
            f"/review/{review_id}/edit",
            data={"rating": "1", "comment": "Hacked review!"},
        )
        self.assertEqual(response.status_code, 403)

    def test_customer_can_delete_own_review(self):
        self.login_as(self.customer1_id)
        self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "4", "comment": "Review to delete"},
            follow_redirects=True,
        )

        with ecommerce_app.app.app_context():
            review = ecommerce_app.Review.query.filter_by(user_id=self.customer1_id).first()
            review_id = review.id

        response = self.client.post(
            f"/review/{review_id}/delete",
            follow_redirects=True,
        )
        self.assertIn(b"Review deleted successfully", response.data)

        with ecommerce_app.app.app_context():
            deleted_review = ecommerce_app.Review.query.get(review_id)
            self.assertIsNone(deleted_review)

    def test_customer_cannot_delete_other_user_review(self):
        self.login_as(self.customer1_id)
        self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "4", "comment": "Customer 1 review"},
            follow_redirects=True,
        )

        with ecommerce_app.app.app_context():
            review = ecommerce_app.Review.query.filter_by(user_id=self.customer1_id).first()
            review_id = review.id

        # Customer 2 attempts deletion
        self.login_as(self.customer2_id)
        response = self.client.post(f"/review/{review_id}/delete")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_delete_any_review(self):
        self.login_as(self.customer1_id)
        self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "1", "comment": "Inappropriate comment"},
            follow_redirects=True,
        )

        with ecommerce_app.app.app_context():
            review = ecommerce_app.Review.query.filter_by(user_id=self.customer1_id).first()
            review_id = review.id

        # Admin logs in and deletes the review
        self.login_as(self.admin_id)
        response = self.client.post(
            f"/review/{review_id}/delete",
            follow_redirects=True,
        )
        self.assertIn(b"Review deleted successfully", response.data)

        with ecommerce_app.app.app_context():
            deleted_review = ecommerce_app.Review.query.get(review_id)
            self.assertIsNone(deleted_review)

    def test_admin_reviews_dashboard_access_control(self):
        # Non-admin access rejected with 403 Forbidden
        self.login_as(self.customer1_id)
        response = self.client.get("/admin/reviews")
        self.assertEqual(response.status_code, 403)

        # Admin access accepted
        self.login_as(self.admin_id)
        response = self.client.get("/admin/reviews")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Customer Reviews", response.data)

    def test_dynamic_average_rating_and_count(self):
        # Order 2: Customer 2 buys Product 1
        with ecommerce_app.app.app_context():
            order2 = ecommerce_app.Order(
                user_id=self.customer2_id,
                order_number="ORD-TEST-002",
                status="Delivered",
                total_amount=85000.0,
            )
            ecommerce_app.db.session.add(order2)
            ecommerce_app.db.session.commit()
            item2 = ecommerce_app.OrderItem(
                order_id=order2.id,
                product_id=self.product1_id,
                product_name="Gaming Laptop RTX",
                product_image="laptop.png",
                quantity=1,
                unit_price=85000.0,
                total_price=85000.0,
            )
            ecommerce_app.db.session.add(item2)
            ecommerce_app.db.session.commit()

        # Customer 1 submits 5-star review
        self.login_as(self.customer1_id)
        self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "5", "comment": "Loved it!"},
        )

        # Customer 2 submits 3-star review
        self.login_as(self.customer2_id)
        self.client.post(
            f"/product/{self.product1_id}/review",
            data={"rating": "3", "comment": "Average experience"},
        )

        with ecommerce_app.app.app_context():
            product = ecommerce_app.Product.query.get(self.product1_id)
            self.assertEqual(product.review_count, 2)
            # (5 + 3) / 2 = 4.0
            self.assertEqual(product.average_rating, 4.0)


if __name__ == "__main__":
    unittest.main()
