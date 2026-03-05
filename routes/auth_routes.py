from flask import Blueprint, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from config import get_db_connection

auth = Blueprint("auth", __name__)


@auth.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = generate_password_hash(request.form["password"])
        role = request.form["role"]

        db = get_db_connection()
        cursor = db.cursor(buffered=True)

        try:
            sql = "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)"
            values = (name, email, password, role)
            cursor.execute(sql, values)
            db.commit()

            flash("Registration Successful! 🎉 Please login.", "success")
            return redirect("/login")

        except mysql.connector.Error:
            flash("Email already registered! ⚠", "danger")
            return redirect("/register")

        finally:
            cursor.close()
            db.close()

    return render_template("register.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        db = get_db_connection()
        cursor = db.cursor(buffered=True)

        sql = "SELECT * FROM users WHERE email = %s"
        cursor.execute(sql, (email,))
        user = cursor.fetchone()

        cursor.close()
        db.close()

        if user and check_password_hash(user[3], password):
            session["user_id"] = user[0]
            session["name"] = user[1]
            session["role"] = user[4]

            flash("Login Successful! 🚀", "success")

            if session.get("role", "").strip().lower() == "admin":
                return redirect("/admin")

            return redirect("/dashboard")

        else:
            flash("Invalid Email or Password ❌", "danger")
            return redirect("/login")

    return render_template("login.html")


@auth.route("/logout")
def logout():
    session.clear()
    flash("Logged Out Successfully 👋", "info")
    return redirect("/login")


@auth.route("/my-bookings")
def my_bookings():
    if "user_id" not in session:
        return redirect("/login")

    if session.get("role", "").strip().lower() != "student":
        flash("Access Denied!", "danger")
        return redirect("/dashboard")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    sql = """
    SELECT bookings.id,
           bookings.mentor_id,
           users.name as mentor_name,
           bookings.booking_time,
           bookings.status
    FROM bookings
    JOIN users ON bookings.mentor_id = users.user_id
    WHERE bookings.student_id = %s
    ORDER BY bookings.booking_time DESC
    """

    cursor.execute(sql, (session["user_id"],))
    bookings = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("my_bookings.html", bookings=bookings)