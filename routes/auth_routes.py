from flask import Blueprint, render_template, request, redirect, session, flash
from otp_system import otp_store, generate_otp
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import time
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
            # email check
            cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                flash("Email already registered! ⚠", "danger")
                return redirect("/register")

            import time

            # ✅ Rate limit check
            if email in otp_store:
                last_time = otp_store[email].get("time", 0)
                attempts = otp_store[email].get("attempts", 0)

                # 60 sec cooldown
                if time.time() - last_time < 60:
                    flash("Wait 60 seconds before requesting OTP again", "warning")
                    return redirect(request.url)

                # max 3 attempts
                if attempts >= 3:
                    flash("Too many OTP requests. Try later.", "danger")
                    return redirect(request.url)

            # ✅ Generate OTP (IMPORTANT - हमेशा बाहर)
            otp = generate_otp()

            # ✅ Store OTP + user data
            otp_store[email] = {
                "otp": otp,
                "name": name,
                "password": password,
                "role": role,
                "time": time.time(),
                "attempts": otp_store.get(email, {}).get("attempts", 0) + 1
            }

            # OTP send
            from app import send_email
            send_email(email, "OTP Verification - TimeShare", f"Your OTP is {otp}")

            flash("OTP sent to your email!", "info")
            return redirect(f"/verify-otp?email={email}")

        except Exception as e:
            print("REGISTER ERROR:", e)
            flash("Something went wrong!", "danger")
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