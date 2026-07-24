from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy

from flask import Flask, render_template, request, redirect, session
app = Flask(__name__)
app.config["SECRET_KEY"] = "zachify_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///zachify.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    password = db.Column(db.String(200), nullable=False)

class Product(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(200), nullable=False)

    price = db.Column(db.Float, nullable=False)

    image = db.Column(db.String(200), nullable=False)

    category = db.Column(db.String(100), nullable=False)

    description = db.Column(db.Text, nullable=False)

    stock = db.Column(db.Integer, default=0)

@app.route("/")
def home():

    products = Product.query.all()

    return render_template("index.html", products=products)
@app.route("/products")
def products():
    return render_template("products.html")
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

    return redirect(url_for("home"))
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

    return render_template("cart.html", products=products, cart=cart)

@app.route("/add_to_cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):

    cart = session.get("cart", {})

    product_id = str(product_id)

    if product_id in cart:
        cart[product_id] += 1
    else:
        cart[product_id] = 1

    session["cart"] = cart

    return redirect("/cart")
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
    app.run(debug=True)
