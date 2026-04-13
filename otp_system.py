import random
import time
from flask import Blueprint, request, render_template, redirect, flash
from config import get_db_connection
from werkzeug.security import generate_password_hash

# ✅ EMAIL FUNCTION (moved here to fix circular import)
import smtplib
from email.mime.text import MIMEText
import os

def send_email(receiver_email, subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = os.getenv("EMAIL_ADDRESS")
        msg["To"] = receiver_email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(os.getenv("EMAIL_ADDRESS"), os.getenv("EMAIL_PASSWORD"))
        server.sendmail(os.getenv("EMAIL_ADDRESS"), receiver_email, msg.as_string())
        server.quit()

        print("EMAIL SENT SUCCESS")
        return True

    except Exception as e:
        print("EMAIL ERROR:", e)
        return False


otp_bp = Blueprint("otp", __name__)

otp_store = {}

def generate_otp():
    return str(random.randint(100000, 999999))


@otp_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():

    email = request.args.get("email")

    if request.method == "POST":
        entered_otp = request.form.get("otp")

        if email in otp_store and otp_store[email]["otp"] == entered_otp:

            data = otp_store[email]

            db = get_db_connection()
            cursor = db.cursor()

            cursor.execute(
                "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                (data["name"], email, data["password"], data["role"])
            )

            db.commit()
            cursor.close()
            db.close()

            otp_store.pop(email)

            flash("Registration Successful! 🎉", "success")
            return redirect("/login")

        else:
            flash("Invalid OTP", "danger")

    return render_template("verify_otp.html", email=email)


@otp_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":
        email = request.form.get("email")

        # ✅ Rate limit check
        if email in otp_store:
            last_time = otp_store[email].get("time", 0)
            attempts = otp_store[email].get("attempts", 0)

            if time.time() - last_time < 60:
                flash("Wait 60 seconds before requesting OTP again", "warning")
                return redirect(request.url)

            if attempts >= 3:
                flash("Too many OTP requests. Try later.", "danger")
                return redirect(request.url)

        otp = generate_otp()

        print("FORGOT OTP:", otp)
        
        otp_store[email] = {
            "otp": otp,
            "time": time.time(),
            "attempts": otp_store.get(email, {}).get("attempts", 0) + 1
        }

        # ✅ EMAIL SEND
        send_email(email, "Password Reset OTP", f"Your OTP is {otp}")

        flash("OTP sent to your email!", "info")
        return redirect(f"/reset-password?email={email}")

    return render_template("forgot_password.html")


@otp_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():

    email = request.args.get("email")

    if request.method == "POST":
        entered_otp = request.form.get("otp")
        new_password = generate_password_hash(request.form.get("password"))

        if email in otp_store and otp_store[email]["otp"] == entered_otp:

            db = get_db_connection()
            cursor = db.cursor()

            cursor.execute(
                "UPDATE users SET password=%s WHERE email=%s",
                (new_password, email)
            )

            db.commit()
            cursor.close()
            db.close()

            otp_store.pop(email)

            flash("Password updated successfully!", "success")
            return redirect("/login")

        else:
            flash("Invalid OTP", "danger")

    return render_template("reset_password.html", email=email)


@otp_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    email = request.form.get("email")

    # rate limit
    if email in otp_store:
        last_time = otp_store[email].get("time", 0)

        if time.time() - last_time < 30:
            flash("Wait before resending OTP", "warning")
            return redirect(request.referrer)

    otp = generate_otp()

    old_data = otp_store.get(email, {})

    otp_store[email] = {
        **old_data,
        "otp": otp,
        "time": time.time()
    }

    # ✅ EMAIL SEND
    send_email(email, "Resent OTP - TimeShare", f"Your new OTP is {otp}")

    flash("OTP resent successfully!", "success")

    return redirect(request.referrer)