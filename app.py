from flask_sqlalchemy import SQLAlchemy

from flask import Flask, render_template, request

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///zachify.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False)

    password = db.Column(db.String(200), nullable=False)

@app.route("/")
def home():
    return render_template("index.html")
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

        print("Email:", email)
        print("Password:", password)

    return render_template("login.html")
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        new_user = User(
            username=username,
            email=email,
            password=password
        )

        db.session.add(new_user)
        db.session.commit()

        return "Registration Successful!"

    return render_template("register.html")
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
