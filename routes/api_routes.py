from flask import Blueprint, jsonify, request
from config import get_db_connection

api = Blueprint("api", __name__, url_prefix="/api")

# ================= USERS API =================

@api.route("/users", methods=["GET"])
def get_users():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT user_id, name, email, role FROM users")
    users = cursor.fetchall()

    cursor.close()
    db.close()

    return jsonify(users)


# ================= BOOKINGS API =================

@api.route("/bookings", methods=["GET"])
def get_bookings():
    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM bookings")
    bookings = cursor.fetchall()

    cursor.close()
    db.close()

    return jsonify(bookings)


# ================= CREATE BOOKING API =================

@api.route("/bookings", methods=["POST"])
def create_booking():
    data = request.json

    student_id = data.get("student_id")
    mentor_id = data.get("mentor_id")

    if not student_id or not mentor_id:
        return jsonify({"error": "Missing required fields"}), 400

    db = get_db_connection()
    cursor = db.cursor()

    try:
        cursor.execute(
            "INSERT INTO bookings (student_id, mentor_id, status) VALUES (%s, %s, 'Pending')",
            (student_id, mentor_id)
        )
        db.commit()
        return jsonify({"message": "Booking created successfully"}), 201

    except Exception:
        return jsonify({"error": "Booking failed"}), 400

    finally:
        cursor.close()
        db.close()