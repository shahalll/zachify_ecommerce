from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, desc

from flask import Flask, render_template, request, redirect, session, url_for, jsonify
app = Flask(__name__)
app.config["SECRET_KEY"] = "zachify_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///zachify.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


def get_current_user():
    user_id = session.get("user_id")
    if user_id:
        return User.query.get(user_id)

    username = session.get("username")
    if username:
        return User.query.filter_by(username=username).first()

    return None


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

    wishlists = db.relationship("Wishlist", backref="user", lazy=True, cascade="all, delete-orphan")


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


def seed_default_products():
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

@app.route("/")
def home():

    products = Product.query.all()

    wishlist_ids = get_user_wishlist_ids(get_current_user())
    return render_template("index.html", products=products, wishlist_ids=wishlist_ids)
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
@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            session["username"] = user.username
            session["user_id"] = user.id
            return redirect(url_for("home"))


        else:
            return "Invalid Email or Password!"

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)

        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            return "This email is already registered."

        new_user = User(
            username=username,
            email=email,
            password=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        return "Registration Successful!"

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
def admin():

    if request.method == "POST":

        name = request.form["name"]
        price = float(request.form["price"])
        image = request.form["image"]
        category = request.form["category"]
        description = request.form["description"]
        stock = int(request.form["stock"])

        new_product = Product(
            name=name,
            price=price,
            image=image,
            category=category,
            description=description,
            stock=stock
        )

        db.session.add(new_product)
        db.session.commit()

    products = Product.query.all()

    return render_template("admin.html", products=products)

@app.route("/cart")
def cart():

    cart = session.get("cart", {})

    product_ids = [int(pid) for pid in cart.keys()]

    products = Product.query.filter(Product.id.in_(product_ids)).all()

    total = 0

    for product in products:

        total += product.price * cart[str(product.id)]

    return render_template(
        "cart.html",
        products=products,
        cart=cart,
        total=total
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
@app.route("/delete_product/<int:id>")
def delete_product(id):

    product = Product.query.get_or_404(id)

    db.session.delete(product)

    db.session.commit()

    return redirect("/admin")
@app.route("/edit_product/<int:id>", methods=["GET", "POST"])
def edit_product(id):

    product = Product.query.get_or_404(id)

    if request.method == "POST":

        product.name = request.form["name"]
        product.price = float(request.form["price"])
        product.image = request.form["image"]
        product.category = request.form["category"]
        product.description = request.form["description"]
        product.stock = int(request.form["stock"])

        db.session.commit()

        return redirect("/admin")

    return render_template("edit_product.html", product=product)
@app.route("/clear_cart")
def clear_cart():
    session.clear()
    return "Session Cleared!"
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_default_products()
    app.run(debug=True)
