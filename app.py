import uuid
from functools import wraps
from datetime import datetime
import click
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, desc, func, text, inspect

from flask import Flask, flash, render_template, request, redirect, session, url_for, jsonify, abort
app = Flask(__name__)
app.config["SECRET_KEY"] = "zachify_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///zachify.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

DEFAULT_ADMIN_EMAILS = {
    "mhdshahal3182005@gmail.com",
}


def ensure_default_admins():
    """Ensures designated administrative accounts always exist and retain is_admin=True."""
    try:
        updated = False
        default_admin_accounts = [
            ("shahal", "mhdshahal3182005@gmail.com", "shahal123"),
        ]
        for uname, uemail, upass in default_admin_accounts:
            user = User.query.filter(User.email.ilike(uemail)).first()
            if not user:
                user = User(
                    username=uname,
                    email=uemail,
                    password=generate_password_hash(upass),
                    is_admin=True,
                )
                db.session.add(user)
                updated = True
            elif not user.is_admin:
                user.is_admin = True
                updated = True

        for admin_email in DEFAULT_ADMIN_EMAILS:
            user = User.query.filter(User.email.ilike(admin_email)).first()
            if user and not user.is_admin:
                user.is_admin = True
                updated = True

        if updated:
            db.session.commit()
    except Exception as e:
        print(f"Admin sync notice: {e}")



def get_current_user():
    user = None
    user_id = session.get("user_id")
    if user_id:
        user = User.query.get(user_id)
    else:
        username = session.get("username")
        if username:
            user = User.query.filter_by(username=username).first()

    if user and user.email and user.email.lower() in {e.lower() for e in DEFAULT_ADMIN_EMAILS} and not user.is_admin:
        user.is_admin = True
        try:
            db.session.commit()
        except Exception:
            pass

    return user


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = get_current_user()
        if not current_user:
            flash("Please login to access the admin area.", "danger")
            return redirect(url_for("login"))
        if not bool(current_user.is_admin):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def migrate_sqlite_schema():
    """Safely adds missing columns to existing SQLite database without losing data."""
    try:
        inspector = inspect(db.engine)
        if "user" in inspector.get_table_names():
            columns = [col["name"] for col in inspector.get_columns("user")]
            if "is_admin" not in columns:
                with db.engine.connect() as conn:
                    conn.execute(text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0;"))
                    conn.commit()
        ensure_default_admins()
    except Exception as e:
        print(f"Migration notice: {e}")



def get_user_wishlist_ids(user):
    if not user:
        return []
    return [item.product_id for item in Wishlist.query.filter_by(user_id=user.id).all()]


@app.context_processor
def cart_count():

    cart = session.get("cart", {})

    total_quantity = sum(cart.values())
    current_user = get_current_user()
    wishlist_count = 0
    if current_user:
        wishlist_count = Wishlist.query.filter_by(user_id=current_user.id).count()

    return {"cart_count": total_quantity, "wishlist_count": wishlist_count, "current_user": current_user}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    wishlists = db.relationship("Wishlist", backref="user", lazy=True, cascade="all, delete-orphan")
    orders = db.relationship("Order", backref="user", lazy=True, cascade="all, delete-orphan")


class Product(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200), nullable=False)

    price = db.Column(db.Float, nullable=False)

    image = db.Column(db.String(200), nullable=False)

    category = db.Column(db.String(100), nullable=False)

    description = db.Column(db.Text, nullable=False)

    stock = db.Column(db.Integer, default=0)

    wishlists = db.relationship("Wishlist", backref="product", lazy=True, cascade="all, delete-orphan")

    @property
    def effective_rating(self):
        base = 4.2
        if self.category.lower() == "electronics":
            base += 0.2
        if self.stock >= 8:
            base += 0.3
        elif self.stock >= 3:
            base += 0.1
        if self.price <= 20000:
            base += 0.1
        return round(min(5.0, base), 1)

    @property
    def is_in_stock(self):
        return self.stock > 0


class Wishlist(db.Model):
    __tablename__ = "wishlist"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "product_id", name="uq_wishlist_user_product"),
    )


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    status = db.Column(db.String(50), nullable=False, default="Processing")
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("OrderItem", backref="order", lazy=True, cascade="all, delete-orphan")


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("order.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=True)
    product_name = db.Column(db.String(200), nullable=False)
    product_image = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Float, nullable=False, default=0.0)
    total_price = db.Column(db.Float, nullable=False, default=0.0)


def seed_default_products():
    Product.query.filter(Product.name.ilike("%test laptop%")).delete(synchronize_session=False)
    db.session.commit()

    if Product.query.count() == 0:
        products = [
            Product(
                name="dell inspiron(2026 edition)",
                price=55000.00,
                image="laptop.jpg",
                category="electronics",
                description="Intel Core i5 Laptop with 16GB RAM",
                stock=10,
            ),
            Product(
                name="iphone 15 pro",
                price=66000.00,
                image="iphone.jpg",
                category="electronics",
                description="unused condition",
                stock=4,
            ),
            Product(
                name="converse",
                price=2999.00,
                image="shoe.jpg",
                category="fashion",
                description="premium quality shoe",
                stock=2,
            ),
            Product(
                name="Sony WH-CH520",
                price=4799.00,
                image="headphone.jpg",
                category="electronics",
                description="lightweight headphone",
                stock=5,
            ),
        ]
        db.session.add_all(products)
        db.session.commit()

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for("login"))

    if request.method == "POST" and request.form.get("profile_form") == "1":
        new_username = request.form.get("username", "").strip()
        new_email = request.form.get("email", "").strip()
        new_password = request.form.get("password", "").strip()

        if new_username:
            current_user.username = new_username
        if new_email:
            existing_user = User.query.filter(User.email == new_email, User.id != current_user.id).first()
            if existing_user:
                return "This email is already registered."
            current_user.email = new_email
        if new_password:
            current_user.password = generate_password_hash(new_password)

        db.session.commit()
        session["username"] = current_user.username
        return redirect(url_for("dashboard"))

    orders = (
        Order.query.filter_by(user_id=current_user.id)
        .order_by(Order.created_at.desc())
        .all()
    )

    order_items_map = {}
    for order in orders:
        order_items_map[order.id] = (
            OrderItem.query.filter_by(order_id=order.id)
            .order_by(OrderItem.id.asc())
            .all()
        )

    wishlist_count = Wishlist.query.filter_by(user_id=current_user.id).count()
    cart_data = session.get("cart", {})
    cart_count = sum(int(quantity) for quantity in cart_data.values() if str(quantity).isdigit())
    total_spent = sum(order.total_amount for order in orders)

    return render_template(
        "dashboard.html",
        user=current_user,
        orders=orders,
        order_items_map=order_items_map,
        wishlist_count=wishlist_count,
        cart_count=cart_count,
        total_spent=total_spent,
    )


@app.route("/")
def home():

    products = Product.query.all()

    wishlist_ids = get_user_wishlist_ids(get_current_user())
    return render_template("index.html", products=products, wishlist_ids=wishlist_ids)
@app.route("/about")
def about():
    return render_template("about.html")
@app.route("/search")
def search():
    query = request.args.get("q", "").strip()

    if not query:
        return redirect(url_for("products"))

    search_term = f"%{query}%"

    products = Product.query.filter(
        or_(
            Product.name.ilike(search_term),
            Product.category.ilike(search_term),
            Product.description.ilike(search_term)
        )
    ).all()

    categories = sorted({product.category for product in products if product.category})

    wishlist_ids = get_user_wishlist_ids(get_current_user())

    return render_template(
        "search_results.html",
        products=products,
        search_query=query,
        categories=categories,
        wishlist_ids=wishlist_ids
    )

@app.route("/search/suggestions")
def search_suggestions():
    query = request.args.get("q", "").strip()

    if not query:
        return jsonify([])

    search_term = f"%{query}%"

    products = Product.query.filter(
        or_(
            Product.name.ilike(search_term),
            Product.category.ilike(search_term),
            Product.description.ilike(search_term)
        )
    ).limit(6).all()

    suggestions = []
    for product in products:
        suggestions.append({
            "id": product.id,
            "name": product.name,
            "category": product.category,
            "description": product.description[:80]
        })

    return jsonify(suggestions)

def apply_product_filters(products):
    categories = request.args.getlist("category")
    if categories:
        normalized_categories = [category.strip().lower() for category in categories if category.strip()]
        if normalized_categories:
            products = [product for product in products if product.category.lower() in normalized_categories]

    price_min = request.args.get("price_min", type=float)
    price_max = request.args.get("price_max", type=float)
    if price_min is not None:
        products = [product for product in products if product.price >= price_min]
    if price_max is not None:
        products = [product for product in products if product.price <= price_max]

    availability = request.args.getlist("availability")
    if availability:
        if "in_stock" in availability and "out_of_stock" not in availability:
            products = [product for product in products if product.is_in_stock]
        elif "out_of_stock" in availability and "in_stock" not in availability:
            products = [product for product in products if not product.is_in_stock]

    rating_min = request.args.get("rating_min", type=float)
    if rating_min is not None:
        products = [product for product in products if product.effective_rating >= rating_min]

    sort_by = request.args.get("sort", "featured")
    if sort_by == "price_asc":
        products = sorted(products, key=lambda product: product.price)
    elif sort_by == "price_desc":
        products = sorted(products, key=lambda product: product.price, reverse=True)
    elif sort_by == "newest":
        products = sorted(products, key=lambda product: product.id, reverse=True)
    elif sort_by == "rating_desc":
        products = sorted(products, key=lambda product: (product.effective_rating, product.price), reverse=True)
    else:
        products = sorted(products, key=lambda product: (-product.effective_rating, product.price))

    return products


@app.route("/products")
def products():
    all_products = Product.query.all()
    wishlist_ids = get_user_wishlist_ids(get_current_user())

    filtered_products = apply_product_filters(all_products)

    categories = sorted({product.category.lower() for product in all_products if product.category})
    max_price = max((product.price for product in all_products), default=0)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render_template(
            "partials/product_cards.html",
            products=filtered_products,
            wishlist_ids=wishlist_ids,
        )

    return render_template(
        "products.html",
        products=filtered_products,
        wishlist_ids=wishlist_ids,
        categories=categories,
        max_price=max_price,
        selected_categories=request.args.getlist("category"),
        price_min=request.args.get("price_min", type=float),
        price_max=request.args.get("price_max", type=float),
        selected_availability=request.args.getlist("availability"),
        rating_min=request.args.get("rating_min", type=float),
        sort_by=request.args.get("sort", "featured"),
    )

@app.route("/product/<int:id>")
def product_detail(id):
    product = Product.query.get_or_404(id)
    return render_template("product_details.html", product=product)

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        identifier = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # Allow login by Email OR Username (case-insensitive)
        user = User.query.filter(
            or_(User.email.ilike(identifier), User.username.ilike(identifier))
        ).first()

        is_valid_password = False
        if user and password:
            try:
                if check_password_hash(user.password, password) or check_password_hash(user.password, password.strip()):
                    is_valid_password = True
            except Exception:
                pass

            # Fallback for plain-text legacy passwords
            if not is_valid_password and (user.password == password or user.password == password.strip()):
                is_valid_password = True
                user.password = generate_password_hash(password)
                db.session.commit()

        if user and is_valid_password:
            if user.email and user.email.lower() in {e.lower() for e in DEFAULT_ADMIN_EMAILS} and not user.is_admin:
                user.is_admin = True
                db.session.commit()

            session["username"] = user.username
            session["user_id"] = user.id
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(url_for("home"))
        else:
            flash("Invalid Email/Username or Password! If you don't have an account yet, please register first.", "danger")
            return render_template("login.html")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("register"))
        hashed_password = generate_password_hash(password)

        # Check if email already exists (case-insensitive)
        existing_user = User.query.filter(User.email.ilike(email)).first()

        if existing_user:
           flash("Email already registered.", "danger")
           return redirect(url_for("register"))

        is_admin_user = email.lower() in {e.lower() for e in DEFAULT_ADMIN_EMAILS}
        new_user = User(
            username=username,
            email=email,
            password=hashed_password,
            is_admin=is_admin_user
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")
@app.route("/logout")
def logout():

    session.pop("username", None)
    session.pop("user_id", None)

    return redirect(url_for("home"))


@app.route("/wishlist")
def wishlist_page():
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for("login"))

    wishlist_items = (
        Wishlist.query.filter_by(user_id=current_user.id)
        .order_by(Wishlist.created_at.desc())
        .all()
    )

    return render_template("wishlist.html", wishlist_items=wishlist_items)


@app.route("/wishlist/add/<int:product_id>", methods=["GET", "POST"])
def add_to_wishlist(product_id):
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for("login"))

    existing = Wishlist.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if not existing:
        db.session.add(Wishlist(user_id=current_user.id, product_id=product_id))
        db.session.commit()

    return redirect(request.referrer or url_for("products"))


@app.route("/wishlist/remove/<int:product_id>", methods=["GET", "POST"])
def remove_from_wishlist(product_id):
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for("login"))

    existing = Wishlist.query.filter_by(user_id=current_user.id, product_id=product_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()

    return redirect(request.referrer or url_for("wishlist_page"))


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        image = request.form.get("image", "").strip()
        description = request.form.get("description", "").strip()
        price_raw = request.form.get("price", "").strip()
        stock_raw = request.form.get("stock", "").strip()

        if not name or not category or not image or not description:
            flash("Please fill in all required product fields.", "danger")
        else:
            try:
                price = float(price_raw)
                stock = int(stock_raw)
                if price <= 0:
                    flash("Price must be greater than 0.", "danger")
                elif stock < 0:
                    flash("Stock quantity cannot be negative.", "danger")
                else:
                    new_product = Product(
                        name=name,
                        price=price,
                        image=image,
                        category=category,
                        description=description,
                        stock=stock,
                    )
                    db.session.add(new_product)
                    db.session.commit()
                    flash(f"Product '{new_product.name}' added successfully!", "success")
            except ValueError:
                flash("Invalid price or stock value entered.", "danger")

    # Fetch all products
    products = Product.query.order_by(Product.id.desc()).all()

    # Dashboard statistics
    total_products = Product.query.count()
    total_users = User.query.count()
    total_orders = Order.query.count()

    total_revenue = db.session.query(
        func.sum(Order.total_amount)
    ).scalar() or 0

    return render_template(
        "admin.html",
        products=products,
        total_products=total_products,
        total_users=total_users,
        total_orders=total_orders,
        total_revenue=total_revenue
    )


@app.route("/admin/products")
@admin_required
def admin_products():
    search_query = request.args.get("q", "").strip()
    selected_category = request.args.get("category", "").strip()

    query = Product.query
    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(
            or_(
                Product.name.ilike(search_term),
                Product.category.ilike(search_term),
                Product.description.ilike(search_term),
            )
        )
    if selected_category:
        query = query.filter(Product.category.ilike(selected_category))

    products = query.order_by(Product.id.desc()).all()

    all_products = Product.query.all()
    total_products = len(all_products)
    in_stock_count = sum(1 for p in all_products if p.stock > 3)
    low_stock_count = sum(1 for p in all_products if 0 < p.stock <= 3)
    out_of_stock_count = sum(1 for p in all_products if p.stock <= 0)
    categories = sorted({p.category for p in all_products if p.category})

    return render_template(
        "admin_products.html",
        products=products,
        total_products=total_products,
        in_stock_count=in_stock_count,
        low_stock_count=low_stock_count,
        out_of_stock_count=out_of_stock_count,
        categories=categories,
        search_query=search_query,
        selected_category=selected_category,
    )


@app.route("/admin/product/add", methods=["GET", "POST"])
@app.route("/admin/products/add", methods=["GET", "POST"])
@admin_required
def admin_add_product():
    all_products = Product.query.all()
    categories = sorted({p.category for p in all_products if p.category})

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        image = request.form.get("image", "").strip()
        description = request.form.get("description", "").strip()
        price_raw = request.form.get("price", "").strip()
        stock_raw = request.form.get("stock", "").strip()

        if not name or not category or not image or not description:
            flash("Please fill in all required product fields.", "danger")
            return render_template("admin_add_product.html", categories=categories, form_data=request.form)

        try:
            price = float(price_raw)
            if price <= 0:
                flash("Price must be greater than 0.", "danger")
                return render_template("admin_add_product.html", categories=categories, form_data=request.form)
        except ValueError:
            flash("Please enter a valid numeric price.", "danger")
            return render_template("admin_add_product.html", categories=categories, form_data=request.form)

        try:
            stock = int(stock_raw)
            if stock < 0:
                flash("Stock quantity cannot be negative.", "danger")
                return render_template("admin_add_product.html", categories=categories, form_data=request.form)
        except ValueError:
            flash("Please enter a valid numeric stock quantity.", "danger")
            return render_template("admin_add_product.html", categories=categories, form_data=request.form)

        new_product = Product(
            name=name,
            price=price,
            image=image,
            category=category,
            description=description,
            stock=stock,
        )

        db.session.add(new_product)
        db.session.commit()

        flash(f"Product '{new_product.name}' added successfully!", "success")
        return redirect(url_for("admin_products"))

    return render_template("admin_add_product.html", categories=categories, form_data={})


@app.route("/admin/orders")
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template(
        "admin_orders.html",
        orders=orders
    )


@app.route("/admin/order/<int:order_id>", methods=["GET", "POST"])
@app.route("/admin/orders/<int:order_id>", methods=["GET", "POST"])
@admin_required
def admin_order_details(order_id):
    order = Order.query.get_or_404(order_id)
    allowed_statuses = [
        "Processing",
        "Packed",
        "Confirmed",
        "Shipped",
        "Delivered",
        "Cancelled",
        "Pending",
    ]

    if request.method == "POST":
        new_status = request.form.get("status", "").strip()
        if new_status in allowed_statuses:
            order.status = new_status
            db.session.commit()
            flash(f"Order #{order.order_number} status updated to '{new_status}'!", "success")
            return redirect(url_for("admin_order_details", order_id=order.id))
        else:
            flash("Invalid status selected.", "danger")

    return render_template(
        "admin_order_details.html",
        order=order,
        status_options=allowed_statuses,
    )


@app.route("/admin/order/<int:order_id>/status")
@admin_required
def change_order_status(order_id):

    order = Order.query.get_or_404(order_id)

    status_flow = [
        "Processing",
        "Packed",
        "Shipped",
        "Delivered"
    ]

    if order.status in status_flow:

        current = status_flow.index(order.status)

        if current < len(status_flow) - 1:

            order.status = status_flow[current + 1]

            db.session.commit()

    return redirect(url_for("admin_orders"))



@app.route("/admin/users")
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()

    total_users = len(users)
    total_admins = sum(1 for u in users if u.is_admin)
    total_customers = total_users - total_admins

    return render_template(
        "admin_users.html",
        users=users,
        total_users=total_users,
        total_admins=total_admins,
        total_customers=total_customers,
    )


def get_cart_summary():
    cart = session.get("cart", {})
    product_ids = [int(pid) for pid in cart.keys() if str(pid).isdigit()]

    products = Product.query.filter(Product.id.in_(product_ids)).all() if product_ids else []
    product_lookup = {product.id: product for product in products}

    cart_products = []
    subtotal = 0.0

    for product_id in product_ids:
        product = product_lookup.get(product_id)
        if not product:
            continue

        quantity = int(cart.get(str(product_id), 0))
        if quantity <= 0:
            continue

        item_subtotal = product.price * quantity
        subtotal += item_subtotal
        cart_products.append({
            "product": product,
            "quantity": quantity,
            "item_subtotal": item_subtotal,
        })

    shipping = 0 if subtotal >= 50000 else (0 if subtotal == 0 else 299)
    discount = subtotal * 0.10 if subtotal >= 30000 else 0
    grand_total = subtotal + shipping - discount

    return {
        "cart": cart,
        "products": cart_products,
        "subtotal": subtotal,
        "shipping": shipping,
        "discount": discount,
        "grand_total": grand_total,
    }
@app.route("/cart")
def cart():
    summary = get_cart_summary()
    return render_template(
        "cart.html",
        products=[item["product"] for item in summary["products"]],
        cart=summary["cart"],
        total=summary["subtotal"],
        subtotal=summary["subtotal"],
        shipping=summary["shipping"],
        discount=summary["discount"],
        grand_total=summary["grand_total"],
        cart_items=summary["products"],
    )


@app.route("/checkout", methods=["GET", "POST"])
def checkout():

    summary = get_cart_summary()

    if not summary["products"]:
        return redirect(url_for("cart"))

    if request.method == "POST":

        if "user_id" not in session:
            flash("Please login before placing an order.", "danger")
            return redirect(url_for("login"))

        order = Order(
            user_id=session["user_id"],
            order_number="ZACH-" + uuid.uuid4().hex[:8].upper(),
            total_amount=summary["grand_total"],
            status="Processing"
        )

        db.session.add(order)
        db.session.flush()

        for item in summary["products"]:

            product = item["product"]
            quantity = item["quantity"]

            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                product_image=product.image,
                quantity=quantity,
                unit_price=product.price,
                total_price=product.price * quantity
            )

            db.session.add(order_item)

        db.session.commit()

        session["cart"] = {}
        session.modified = True

        flash("Order placed successfully!", "success")

        return redirect(url_for("dashboard"))

    return render_template(
        "checkout.html",
        products=[item["product"] for item in summary["products"]],
        cart=summary["cart"],
        subtotal=summary["subtotal"],
        shipping=summary["shipping"],
        discount=summary["discount"],
        grand_total=summary["grand_total"],
        cart_items=summary["products"],
    )
@app.route("/orders")
def orders():

    if "user_id" not in session:
        flash("Please login first.", "danger")
        return redirect(url_for("login"))

    orders = Order.query.filter_by(
        user_id=session["user_id"]
    ).order_by(Order.created_at.desc()).all()

    return render_template(
        "orders.html",
        orders=orders
    )
@app.route("/order/<int:order_id>")
def order_details(order_id):

    if "user_id" not in session:
        flash("Please login first.", "danger")
        return redirect(url_for("login"))

    order = Order.query.filter_by(
        id=order_id,
        user_id=session["user_id"]
    ).first_or_404()

    return render_template(
        "order_detials.html",
        order=order
    )
@app.route("/add_to_cart/<int:product_id>", methods=["GET", "POST"])
def add_to_cart(product_id):

    cart = session.get("cart", {})

    product_id = str(product_id)

    if product_id in cart:
        cart[product_id] += 1
    else:
        cart[product_id] = 1

    session["cart"] = cart
    session.modified = True

    return redirect(request.referrer or url_for("cart"))
@app.route("/remove_from_cart/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):

    cart = session.get("cart", {})

    product_id = str(product_id)

    if product_id in cart:
        del cart[product_id]

    session["cart"] = cart

    return redirect("/cart")

@app.route("/increase_quantity/<int:product_id>", methods=["POST"])
def increase_quantity(product_id):

    cart = session.get("cart", {})

    print("Before:", cart)

    product_id = str(product_id)

    if product_id in cart:
        cart[product_id] += 1

    session["cart"] = cart

    print("After:", cart)

    return redirect("/cart")

@app.route("/decrease_quantity/<int:product_id>", methods=["POST"])
def decrease_quantity(product_id):

    cart = session.get("cart", {})

    product_id = str(product_id)

    if product_id in cart:

        if cart[product_id] > 1:
            cart[product_id] -= 1
        else:
            del cart[product_id]

    session["cart"] = cart

    return redirect("/cart")
@app.route("/admin/product/<int:id>/delete", methods=["GET", "POST"])
@app.route("/delete_product/<int:id>", methods=["GET", "POST"])
@admin_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    product_name = product.name

    # Safely detach product from historical order items so orders & stats remain valid
    OrderItem.query.filter_by(product_id=id).update({"product_id": None})

    # Remove any wishlist entries referencing this product
    Wishlist.query.filter_by(product_id=id).delete()

    db.session.delete(product)
    db.session.commit()

    flash(f"Product '{product_name}' was deleted successfully.", "success")
    return redirect(request.referrer or url_for("admin_products"))


@app.route("/admin/product/<int:id>/edit", methods=["GET", "POST"])
@app.route("/edit_product/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    all_products = Product.query.all()
    categories = sorted({p.category for p in all_products if p.category})

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        image = request.form.get("image", "").strip()
        description = request.form.get("description", "").strip()
        price_raw = request.form.get("price", "").strip()
        stock_raw = request.form.get("stock", "").strip()

        if not name or not category or not image or not description:
            flash("Please fill in all required product fields.", "danger")
            return render_template("edit_product.html", product=product, categories=categories)

        try:
            price = float(price_raw)
            if price <= 0:
                flash("Price must be greater than 0.", "danger")
                return render_template("edit_product.html", product=product, categories=categories)
        except ValueError:
            flash("Please enter a valid numeric price.", "danger")
            return render_template("edit_product.html", product=product, categories=categories)

        try:
            stock = int(stock_raw)
            if stock < 0:
                flash("Stock quantity cannot be negative.", "danger")
                return render_template("edit_product.html", product=product, categories=categories)
        except ValueError:
            flash("Please enter a valid numeric stock quantity.", "danger")
            return render_template("edit_product.html", product=product, categories=categories)

        product.name = name
        product.price = price
        product.image = image
        product.category = category
        product.description = description
        product.stock = stock

        db.session.commit()
        flash(f"Product '{product.name}' updated successfully!", "success")
        return redirect(url_for("admin_products"))

    return render_template("edit_product.html", product=product, categories=categories)

@app.route("/clear_cart")
def clear_cart():
    session.clear()
    return "Session Cleared!"


@app.cli.command("make-admin")
@click.argument("email")
def make_admin_cli(email):
    """Grant administrator privileges to an existing user by email."""
    migrate_sqlite_schema()
    user = User.query.filter(User.email.ilike(email.strip())).first()
    if not user:
        click.echo(f"Error: User with email '{email}' not found.")
        return
    user.is_admin = True
    db.session.commit()
    click.echo(f"Success: User '{user.username}' ({user.email}) is now an administrator.")


@app.cli.command("set-password")
@click.argument("email")
@click.argument("new_password")
def set_password_cli(email, new_password):
    """Set or reset password for an existing user by email."""
    migrate_sqlite_schema()
    user = User.query.filter(User.email.ilike(email.strip())).first()
    if not user:
        click.echo(f"Error: User with email '{email}' not found.")
        return
    user.password = generate_password_hash(new_password)
    db.session.commit()
    click.echo(f"Success: Password updated successfully for '{user.username}' ({user.email}).")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        migrate_sqlite_schema()
        ensure_default_admins()
        seed_default_products()
    app.run(debug=True)
