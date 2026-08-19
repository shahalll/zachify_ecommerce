import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as ecommerce_app


class AdminProductManagementTests(unittest.TestCase):
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
                password=ecommerce_app.generate_password_hash("customer123"),
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
            # Initial Products
            self.product1 = ecommerce_app.Product(
                name="Dell Inspiron 15",
                price=55000.0,
                image="laptop.jpg",
                category="electronics",
                description="Core i5 16GB RAM laptop",
                stock=10,
            )
            self.product2 = ecommerce_app.Product(
                name="Converse Sneaker",
                price=2999.0,
                image="shoe.jpg",
                category="fashion",
                description="Comfortable daily sneakers",
                stock=2,
            )
            self.product3 = ecommerce_app.Product(
                name="Sold Out Headphones",
                price=1999.0,
                image="headphone.jpg",
                category="electronics",
                description="Bluetooth wireless headphones",
                stock=0,
            )

            ecommerce_app.db.session.add_all([
                self.customer,
                self.admin,
                self.product1,
                self.product2,
                self.product3,
            ])
            ecommerce_app.db.session.commit()

            self.customer_id = self.customer.id
            self.admin_id = self.admin.id
            self.p1_id = self.product1.id
            self.p2_id = self.product2.id
            self.p3_id = self.product3.id

    def test_security_guest_redirected_to_login(self):
        """Logged out users must be redirected to /login for all admin product management endpoints."""
        endpoints = [
            "/admin/products",
            "/admin/product/add",
            f"/admin/product/{self.p1_id}/edit",
            f"/edit_product/{self.p1_id}",
            f"/admin/product/{self.p1_id}/delete",
            f"/delete_product/{self.p1_id}",
        ]
        for url in endpoints:
            res = self.client.get(url, follow_redirects=False)
            self.assertEqual(res.status_code, 302, f"Failed for {url}")
            self.assertIn("/login", res.headers["Location"])

    def test_security_normal_customer_denied_access(self):
        """Non-admin logged in customer must receive 403 Forbidden on all admin product management routes."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.customer_id
                session["username"] = "customer_user"

            endpoints = [
                "/admin/products",
                "/admin/product/add",
                f"/admin/product/{self.p1_id}/edit",
                f"/edit_product/{self.p1_id}",
                f"/admin/product/{self.p1_id}/delete",
                f"/delete_product/{self.p1_id}",
            ]
            for url in endpoints:
                res = client.get(url)
                self.assertEqual(res.status_code, 403, f"Expected 403 Forbidden for {url}")

    def test_admin_can_view_products_page(self):
        """Admin can access /admin/products and view catalog metrics and products."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.admin_id
                session["username"] = "admin_user"

            res = client.get("/admin/products")
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Product Catalog", res.data)
            self.assertIn(b"Dell Inspiron 15", res.data)
            self.assertIn(b"Converse Sneaker", res.data)
            self.assertIn(b"Sold Out Headphones", res.data)
            self.assertIn(b"In Stock", res.data)
            self.assertIn(b"Low Stock", res.data)
            self.assertIn(b"Out of Stock", res.data)
            self.assertIn(b"Add New Product", res.data)
            self.assertIn(b"Edit", res.data)
            self.assertIn(b"Delete", res.data)

    def test_admin_search_and_filter_products(self):
        """Admin can search and filter products by keyword or category."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.admin_id
                session["username"] = "admin_user"

            # Search by keyword
            res = client.get("/admin/products?q=Sneaker")
            self.assertEqual(res.status_code, 200)
            self.assertIn(b"Converse Sneaker", res.data)
            self.assertNotIn(b"Dell Inspiron 15", res.data)

            # Filter by category
            res_cat = client.get("/admin/products?category=electronics")
            self.assertEqual(res_cat.status_code, 200)
            self.assertIn(b"Dell Inspiron 15", res_cat.data)
            self.assertIn(b"Sold Out Headphones", res_cat.data)
            self.assertNotIn(b"Converse Sneaker", res_cat.data)

    def test_admin_add_product_validation_and_creation(self):
        """Admin can create a new product with proper validation."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.admin_id
                session["username"] = "admin_user"

            # Test validation: missing required field
            res_invalid = client.post(
                "/admin/product/add",
                data={
                    "name": "",
                    "category": "electronics",
                    "price": "49999",
                    "stock": "5",
                    "image": "phone.jpg",
                    "description": "A new phone",
                },
                follow_redirects=True,
            )
            self.assertEqual(res_invalid.status_code, 200)
            self.assertIn(b"Please fill in all required product fields", res_invalid.data)

            # Test validation: invalid price
            res_bad_price = client.post(
                "/admin/product/add",
                data={
                    "name": "Invalid Price Phone",
                    "category": "electronics",
                    "price": "-100",
                    "stock": "5",
                    "image": "phone.jpg",
                    "description": "A new phone",
                },
                follow_redirects=True,
            )
            self.assertEqual(res_bad_price.status_code, 200)
            self.assertIn(b"Price must be greater than 0", res_bad_price.data)

            # Test successful product creation
            res_success = client.post(
                "/admin/product/add",
                data={
                    "name": "iPad Pro M4",
                    "category": "electronics",
                    "price": "89999.00",
                    "stock": "8",
                    "image": "ipad.jpg",
                    "description": "Ultra retina XDR display",
                },
                follow_redirects=False,
            )
            self.assertEqual(res_success.status_code, 302)
            self.assertIn("/admin/products", res_success.headers["Location"])

            with ecommerce_app.app.app_context():
                created = ecommerce_app.Product.query.filter_by(name="iPad Pro M4").first()
                self.assertIsNotNone(created)
                self.assertEqual(created.price, 89999.00)
                self.assertEqual(created.stock, 8)
                self.assertEqual(created.category, "electronics")

    def test_admin_edit_product(self):
        """Admin can load and edit product details."""
        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.admin_id
                session["username"] = "admin_user"

            # GET edit form
            get_res = client.get(f"/admin/product/{self.p1_id}/edit")
            self.assertEqual(get_res.status_code, 200)
            self.assertIn(b"Edit Product", get_res.data)
            self.assertIn(b"Dell Inspiron 15", get_res.data)

            # POST valid edit
            post_res = client.post(
                f"/admin/product/{self.p1_id}/edit",
                data={
                    "name": "Dell Inspiron 15 (2026 Edition)",
                    "category": "electronics",
                    "price": "59999.00",
                    "stock": "14",
                    "image": "laptop-new.jpg",
                    "description": "Updated specs with 32GB RAM",
                },
                follow_redirects=False,
            )
            self.assertEqual(post_res.status_code, 302)
            self.assertIn("/admin/products", post_res.headers["Location"])

            with ecommerce_app.app.app_context():
                updated = ecommerce_app.Product.query.get(self.p1_id)
                self.assertEqual(updated.name, "Dell Inspiron 15 (2026 Edition)")
                self.assertEqual(updated.price, 59999.00)
                self.assertEqual(updated.stock, 14)
                self.assertEqual(updated.image, "laptop-new.jpg")

    def test_admin_delete_product_safely_with_orders(self):
        """Deleting a product must safely preserve historical order items and not crash."""
        with ecommerce_app.app.app_context():
            # Create an order referencing product 1
            order = ecommerce_app.Order(
                user_id=self.customer_id,
                order_number="ZACH-HIST-001",
                total_amount=55000.0,
                status="Processing",
                created_at=datetime.utcnow(),
            )
            ecommerce_app.db.session.add(order)
            ecommerce_app.db.session.flush()

            order_item = ecommerce_app.OrderItem(
                order_id=order.id,
                product_id=self.p1_id,
                product_name="Dell Inspiron 15",
                product_image="laptop.jpg",
                quantity=1,
                unit_price=55000.0,
                total_price=55000.0,
            )
            wishlist_entry = ecommerce_app.Wishlist(
                user_id=self.customer_id,
                product_id=self.p1_id,
            )
            ecommerce_app.db.session.add_all([order_item, wishlist_entry])
            ecommerce_app.db.session.commit()
            order_id = order.id
            order_item_id = order_item.id

        with self.client as client:
            with client.session_transaction() as session:
                session["user_id"] = self.admin_id
                session["username"] = "admin_user"

            # Delete product 1
            del_res = client.post(f"/admin/product/{self.p1_id}/delete", follow_redirects=False)
            self.assertEqual(del_res.status_code, 302)

            with ecommerce_app.app.app_context():
                # Product is deleted from catalog
                deleted_product = ecommerce_app.Product.query.get(self.p1_id)
                self.assertIsNone(deleted_product)

                # Wishlist reference is cleanly removed
                wishlist_item = ecommerce_app.Wishlist.query.filter_by(product_id=self.p1_id).first()
                self.assertIsNone(wishlist_item)

                # Order and OrderItem historical snapshot remain completely intact
                hist_order = ecommerce_app.Order.query.get(order_id)
                self.assertIsNotNone(hist_order)
                self.assertEqual(hist_order.total_amount, 55000.0)

                hist_item = ecommerce_app.OrderItem.query.get(order_item_id)
                self.assertIsNotNone(hist_item)
                self.assertEqual(hist_item.product_name, "Dell Inspiron 15")
                self.assertEqual(hist_item.total_price, 55000.0)
                self.assertIsNone(hist_item.product_id)


if __name__ == "__main__":
    unittest.main()
