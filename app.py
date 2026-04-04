from flask_socketio import SocketIO, emit, join_room
from routes.api_routes import api
from routes.admin_routes import admin
from config import get_db_connection
from routes.auth_routes import auth
import os
import razorpay
import random

orders = []
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, session, redirect, flash
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
razorpay_client = razorpay.Client(auth=("rzp_test_SXE4YziLjpjNKg", "0wBEpp2w7GLaD0XRt19HdA43"))
socketio = SocketIO(app)
app.register_blueprint(auth)
app.register_blueprint(admin)
app.register_blueprint(api)
app.secret_key = "netpiyush847818"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB limit
EMAIL_ADDRESS = "timeshare.co@gmail.com"
EMAIL_PASSWORD = "hvonqjxwtjsgapyo"


def send_email(receiver_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = receiver_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, receiver_email, msg.as_string())
        server.quit()

    except Exception as e:
        print("Email sending failed:", e)


@app.route("/")
def home():

    search = request.args.get("search")
    category = request.args.get("category")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    query = "SELECT * FROM blogs WHERE 1=1"
    params = []

    if search:
        query += " AND title LIKE %s"
        params.append("%" + search + "%")

    if category:
        query += " AND category=%s"
        params.append(category)

    query += " ORDER BY created_at DESC"

    cursor.execute(query, tuple(params))
    blogs = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("index.html", blogs=blogs)

@app.route("/register", methods=["GET", "POST"])
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

@app.route("/login", methods=["GET", "POST"])
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
            session["email"] = user[2]

            flash("Login Successful! 🚀", "success")

            if session.get("role", "").strip().lower() == "admin":
                return redirect("/admin")

            return redirect("/dashboard")
        else:
            flash("Invalid Email or Password ❌", "danger")
            return redirect("/login")

    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    # Get profile image
    cursor.execute(
        "SELECT profile_image FROM users WHERE user_id=%s",
        (session["user_id"],)
    )
    user_data = cursor.fetchone()
    profile_image = user_data["profile_image"] if user_data else None

    # Statistics
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role='Mentor'")
    total_mentors = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role='Student'")
    total_students = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM bookings")
    total_bookings = cursor.fetchone()["total"]

    cursor.close()
    db.close()

    return render_template(
        "dashboard.html",
        name=session["name"],
        role=session["role"],
        total_mentors=total_mentors,
        total_students=total_students,
        total_bookings=total_bookings,
        profile_image=profile_image
    )

@app.route("/mentor-profile", methods=["GET", "POST"])
def mentor_profile():
    if "user_id" not in session:
        return redirect("/login")

    if session.get("role", "").strip().lower() != "mentor":
        return "Access Denied"

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    # Fetch existing profile data
    cursor.execute(
        "SELECT * FROM mentor_profile WHERE user_id=%s",
        (session["user_id"],)
    )
    existing_profile = cursor.fetchone()

    if request.method == "POST":
        degree = request.form.get("degree")
        skills = request.form.get("skills")
        college = request.form.get("college")
        experience = request.form.get("experience")
        profile_image = request.files.get("profile_image")

        if profile_image and profile_image.filename != "":
            import time
            filename = str(int(time.time())) + "_" + secure_filename(profile_image.filename)

            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            profile_image.save(file_path)

            cursor.execute(
            "UPDATE users SET profile_image=%s WHERE user_id=%s",
            (filename, session["user_id"])
        )

        if existing_profile:
            cursor.execute("""
                UPDATE mentor_profile
                SET degree=%s,
                    skills=%s,
                    college=%s,
                    experience=%s
                WHERE user_id=%s
            """, (
                degree or existing_profile["degree"],
                skills or existing_profile["skills"],
                college or existing_profile["college"],
                experience or existing_profile["experience"],
                session["user_id"]
            ))
        else:
            cursor.execute("""
                INSERT INTO mentor_profile
                (user_id, degree, skills, college, experience)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                session["user_id"],
                degree,
                skills,
                college,
                experience
            ))

        db.commit()
        cursor.close()
        db.close()

        flash("Profile Updated Successfully!", "success")
        return redirect("/dashboard")

    cursor.close()
    db.close()

    return render_template(
        "mentor_profile.html",
        profile=existing_profile
    )

@app.route("/view-mentors")
def view_mentors():
    if "user_id" not in session:
        return redirect("/login")

    if session.get("role", "").strip().lower() != "student":
        return "Access Denied"

    search = request.args.get("search")
    filter_field = request.args.get("filter", "name")
    offset = int(request.args.get("offset", 0))
    limit = 4

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    base_query = """
        SELECT users.user_id, users.name,
               mentor_profile.degree,
               mentor_profile.skills,
               mentor_profile.college,
               mentor_profile.experience
        FROM users
        LEFT JOIN mentor_profile
        ON mentor_profile.user_id = users.user_id
        WHERE users.role = 'Mentor'
    """

    params = []

    if search:
        allowed_filters = {
            "name": "users.name",
            "degree": "IFNULL(mentor_profile.degree, '')",
            "skills": "IFNULL(mentor_profile.skills, '')",
            "college": "IFNULL(mentor_profile.college, '')",
            "experience": "IFNULL(mentor_profile.experience, '')"
        }

        column = allowed_filters.get(filter_field, "users.name")
        base_query += f" AND {column} LIKE %s"
        params.append(f"%{search}%")

    base_query += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    cursor.execute(base_query, tuple(params))
    mentors = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("view_mentors.html", mentors=mentors, offset=offset)

@app.route("/book-session", methods=["POST"])
def book_session():
    if "user_id" not in session:
        return redirect("/login")

    if session.get("role", "").strip().lower() != "student":
        flash("Access Denied!", "danger")
        return redirect("/dashboard")

    mentor_id = request.form["mentor_id"]
    student_id = session["user_id"]

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    try:
        # Insert booking
        cursor.execute("""
            INSERT INTO bookings (student_id, mentor_id, status)
            VALUES (%s, %s, 'Pending')
        """, (student_id, mentor_id))
        db.commit()

        # Get mentor email
        cursor.execute(
            "SELECT email, name FROM users WHERE user_id=%s",
            (mentor_id,)
        )
        mentor = cursor.fetchone()

        # Get student name
        cursor.execute(
            "SELECT name FROM users WHERE user_id=%s",
            (student_id,)
        )
        student = cursor.fetchone()

        if mentor and student:
            subject = "New Booking Request - TimeShare"
            body = f"""
Hello {mentor['name']},

You have received a new session booking request from {student['name']}.

Please login to TimeShare dashboard to approve or reject the request.

Regards,
TimeShare Team
"""
            send_email(mentor["email"], subject, body)

        flash("Session request sent! Email notification delivered.", "success")

    except mysql.connector.Error:
        flash("You have already booked this mentor!", "warning")

    finally:
        cursor.close()
        db.close()

    return redirect("/view-mentors")

@app.route("/view-bookings")
def view_bookings():
    if "user_id" not in session:
        return redirect("/login")

    if session.get("role", "").strip().lower() != "mentor":
        return "Access Denied"

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    sql = """
        SELECT bookings.id,
               bookings.student_id,
               users.name,
               bookings.booking_time,
               bookings.status
        FROM bookings
        JOIN users ON bookings.student_id = users.user_id
        WHERE bookings.mentor_id = %s
    """

    cursor.execute(sql, (session["user_id"],))
    bookings = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("view_bookings.html", bookings=bookings)

@app.route("/update-booking/<int:booking_id>/<string:new_status>")
def update_booking(booking_id, new_status):
    if "user_id" not in session:
        return redirect("/login")

    if session.get("role", "").strip().lower() != "mentor":
        flash("Access Denied!", "danger")
        return redirect("/dashboard")

    if new_status not in ["Approved", "Rejected"]:
        return "Invalid Status"

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    # Update booking status (only if mentor owns it)
    cursor.execute("""
        UPDATE bookings
        SET status=%s
        WHERE id=%s AND mentor_id=%s
    """, (new_status, booking_id, session["user_id"]))
    db.commit()

    # Get student email
    cursor.execute("""
        SELECT users.email, users.name
        FROM bookings
        JOIN users ON bookings.student_id = users.user_id
        WHERE bookings.id=%s
    """, (booking_id,))
    student = cursor.fetchone()

    # Get mentor name
    cursor.execute(
        "SELECT name FROM users WHERE user_id=%s",
        (session["user_id"],)
    )
    mentor = cursor.fetchone()

    cursor.close()
    db.close()

    if student and mentor:
        subject = f"Your Booking has been {new_status} - TimeShare"
        body = f"""
Hello {student['name']},

Your booking request has been {new_status} by mentor {mentor['name']}.

Please login to TimeShare dashboard for more details.

Regards,
TimeShare Team
"""
        send_email(student["email"], subject, body)

    flash(f"Booking {new_status} successfully!", "success")
    return redirect("/view-bookings")

@app.route("/my-bookings")
def my_bookings():
    if "user_id" not in session:
        return redirect("/login")

    if session.get("role", "").strip().lower() != "student":
        flash("Access Denied!", "danger")
        return redirect("/dashboard")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

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

#================= PRIVATE CHAT SYSTEM =================

online_users = {}
# ================= PRIVATE CHAT SYSTEM =================

online_users = {}

@socketio.on("connect")
def handle_connect():
    if "user_id" in session:
        user_id = session["user_id"]
        online_users[user_id] = request.sid

        emit("user_status_change", {
            "user_id": user_id,
            "status": "online"
        }, broadcast=True)


@socketio.on("disconnect")
def handle_disconnect():
    if "user_id" in session:
        user_id = session["user_id"]
        online_users.pop(user_id, None)

        emit("user_status_change", {
            "user_id": user_id,
            "status": "offline"
        }, broadcast=True)


@socketio.on("join_room")
def handle_join(data):
    join_room(data.get("room"))


@socketio.on("check_user_status")
def handle_check_status(data):
    other_user_id = data.get("other_user_id")

    if other_user_id in online_users:
        emit("user_status_change", {
            "user_id": other_user_id,
            "status": "online"
        })
    else:
        emit("user_status_change", {
            "user_id": other_user_id,
            "status": "offline"
        })


@socketio.on("send_private_message")
def handle_private_message(data):
    if "user_id" not in session:
        return

    room = data.get("room")
    message = data.get("message")
    username = data.get("username")
    sender_id = session["user_id"]

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("""
        INSERT INTO messages (room, sender_id, message)
        VALUES (%s, %s, %s)
    """, (room, sender_id, message))

    db.commit()
    cursor.close()
    db.close()

    emit("receive_private_message", {
        "username": username,
        "message": message
    }, room=room)


@socketio.on("typing")
def handle_typing(data):
    emit("user_typing", data, room=data.get("room"), include_self=False)


@socketio.on("stop_typing")
def handle_stop_typing(data):
    emit("user_stop_typing", {}, room=data.get("room"), include_self=False)


@app.route("/chat/<int:other_user_id>")
def private_chat(other_user_id):
    if "user_id" not in session:
        return redirect("/login")

    current_user_id = session["user_id"]
    room = "_".join(map(str, sorted([current_user_id, other_user_id])))

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute(
        "SELECT name FROM users WHERE user_id=%s",
        (other_user_id,)
    )
    other_user = cursor.fetchone()

    cursor.execute("""
        SELECT sender_id, message, timestamp
        FROM messages
        WHERE room = %s
        ORDER BY timestamp ASC
    """, (room,))
    messages = cursor.fetchall()

    cursor.close()
    db.close()

    is_online = other_user_id in online_users

    return render_template(
        "private_chat.html",
        room=room,
        other_user=other_user["name"] if other_user else "Unknown",
        other_user_id=other_user_id,
        is_online=is_online,
        messages=messages
    )

@app.route("/debug-online")
def debug_online():
    return str(online_users)

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged Out Successfully 👋", "info")
    return redirect("/login")


# ================= BLOG DETAIL PAGE =================

@app.route("/blog/<int:blog_id>")
def blog_detail(blog_id):

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("SELECT * FROM blogs WHERE id=%s", (blog_id,))
    blog = cursor.fetchone()

    # increase view counter
    cursor.execute("UPDATE blogs SET views = views + 1 WHERE id=%s", (blog_id,))
    db.commit()

    cursor.close()
    db.close()

    return render_template("blog_detail.html", blog=blog)

# ================= FOR PRODUCT ADD =================

@app.route("/admin/add-product", methods=["GET", "POST"])
def add_product():

    if session.get("role", "").strip().lower() != "admin":
        return "Access Denied"

    if request.method == "POST":
        name = request.form.get("name")
        price = request.form.get("price")
        image = request.files.get("image")

        filename = None

        if image and image.filename != "":
            import time

            filename = str(int(time.time())) + "_" + secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute(
            "INSERT INTO products (name, price, image) VALUES (%s, %s, %s)",
            (name, price, filename)
        )

        db.commit()
        cursor.close()
        db.close()

        flash("Product added successfully!", "success")
        return redirect("/manage-products")

    return render_template("add_product.html")

@app.route("/products")
def products():

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("products.html", products=products)

@app.route("/admin-products")
def admin_products():

    if session.get("role", "").strip().lower() != "admin":
        return "Access Denied"

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("admin_products.html", products=products)

@app.route("/delete-product/<int:product_id>")
def delete_product(product_id):

    if session.get("role", "").strip().lower() != "admin":
        return "Access Denied"

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))

    db.commit()
    cursor.close()
    db.close()

    flash("Product deleted successfully!", "warning")
    return redirect("/products")

@app.route("/add-product-page", methods=["GET", "POST"])
def add_product_page():

    if session.get("role", "").strip().lower() != "admin":
        return "Access Denied"

    if request.method == "POST":
        name = request.form.get("name")
        price = request.form.get("price")
        description = request.form.get("description")
        image = request.files.get("image")

        filename = None

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute(
            "INSERT INTO products (name, description, price, image) VALUES (%s, %s, %s, %s)",
            (name, description, price, filename)
        )

        db.commit()
        cursor.close()
        db.close()

        flash("Product added successfully!", "success")
        return redirect("/products")

    return render_template("add_product.html")
    
@app.route("/add_to_cart/<product_name>")
def add_to_cart(product_name):

    if "cart" not in session:
        session["cart"] = []

    session["cart"].append(product_name)

    flash(f"{product_name} added to cart", "success")

    return redirect("/products")

@app.route("/cart")
def cart():
    return render_template("cart.html")

@app.route("/buy/<product_name>")
def buy(product_name):
    return render_template("buy.html", product_name=product_name)

@app.route("/remove_from_cart/<int:index>")
def remove_from_cart(index):

    if "cart" in session:
        if index < len(session["cart"]):
            session["cart"].pop(index)

    flash("Item removed from cart", "warning")
    return redirect("/cart")

@app.route("/place_order", methods=["POST"])
def place_order():
    name = request.form.get("name")
    product = request.form.get("product")

    order_id = random.randint(10000,99999)

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "INSERT INTO orders (id, name, product, status) VALUES (%s, %s, %s, %s)",
        (order_id, name, product, "Placed")
    )

    db.commit()
    cursor.close()
    db.close()

    # Send confirmation email
    user_email = session.get("email")

    if user_email:
        subject = "Order Confirmation - TimeShare"
        body = f"""
Hello {name},

Your order has been successfully placed!

Order ID: {order_id}
Product: {product}

You can track your order from your dashboard.

Thank you for using TimeShare!

Regards,
TimeShare Team
"""
        send_email(user_email, subject, body)   # ✅ अब सही जगह

    flash(f"Order ID {order_id} placed successfully!", "success")

    return redirect("/orders")

@app.route("/orders")
def orders_page():

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("SELECT * FROM orders")
    orders_data = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("orders.html", orders=orders_data)

@app.route("/admin/update_order/<int:order_id>/<string:new_status>")
def update_order_status(order_id, new_status):

    if "role" not in session or session["role"].lower() != "admin":
        flash("Access Denied!", "danger")
        return redirect("/dashboard")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "UPDATE orders SET status = %s WHERE id = %s",
        (new_status, order_id)
    )

    db.commit()
    cursor.close()
    db.close()

    flash(f"Order marked as {new_status}", "success")
    return redirect("/admin-orders")

@app.route("/admin-orders")
def admin_orders_page():

    if session.get("role", "").strip().lower() != "admin":
        return "Access Denied"
    
    search_order = request.args.get("search_order")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    if search_order:
        cursor.execute("SELECT * FROM orders WHERE id = %s", (search_order,))
    else:
        cursor.execute("SELECT * FROM orders")
        
    orders = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("admin_orders.html", orders=orders)

@app.route("/cancel/<int:order_id>")
def cancel_order(order_id):

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        "UPDATE orders SET status = %s WHERE id = %s",
        ("Cancelled", order_id)
    )

    db.commit()
    cursor.close()
    db.close()

    flash("Order cancelled successfully!", "warning")
    return redirect("/orders")

@app.route("/track/<int:order_id>")
def track_order(order_id):

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
    order = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template("track.html", order=order)

@app.route("/manage-products")
def manage_products():

    if session.get("role", "").strip().lower() != "admin":
        return "Access Denied"

    search = request.args.get("search")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    if search:
        cursor.execute(
            "SELECT * FROM products WHERE name LIKE %s",
            ("%" + search + "%",)
        )
    else:
        cursor.execute("SELECT * FROM products")

    products = cursor.fetchall()

    cursor.close()
    db.close()

    return render_template("manage_products.html", products=products)

@app.route("/edit-product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):

    if session.get("role", "").strip().lower() != "admin":
        return "Access Denied"

    db = get_db_connection()
    cursor = db.cursor(dictionary=True, buffered=True)

    # GET → show form
    if request.method == "GET":
        cursor.execute("SELECT * FROM products WHERE id=%s", (product_id,))
        product = cursor.fetchone()

        cursor.close()
        db.close()

        return render_template("edit_product.html", product=product)

    # POST → update
    name = request.form.get("name")
    price = request.form.get("price")
    image = request.files.get("image")

    if image and image.filename != "":
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cursor.execute(
            "UPDATE products SET name=%s, price=%s, image=%s WHERE id=%s",
            (name, price, filename, product_id)
        )
    else:
        cursor.execute(
            "UPDATE products SET name=%s, price=%s WHERE id=%s",
            (name, price, product_id)
        )
@app.route("/admin/update-order-status", methods=["POST"])
def update_order_status_new():

    if session.get("role", "").strip().lower() != "admin":
        return "Access Denied"

    order_id = request.form.get("order_id")
    status = request.form.get("status")
    location = request.form.get("location")

    db = get_db_connection()
    cursor = db.cursor()

    if location:
        cursor.execute("""
            UPDATE orders
            SET status=%s, current_location=%s
            WHERE id=%s
        """, (status, location, order_id))
    else:
        cursor.execute("""
            UPDATE orders
            SET status=%s
            WHERE id=%s
        """, (status, order_id))

    db.commit()
    cursor.close()
    db.close()

    return redirect("/admin-orders#orders-section")

@app.route("/privacy-policy")
def privacy_policy():
    return render_template("privacy_policy.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        mobile = request.form.get("mobile")
        message = request.form.get("message")

        full_message = f"""
New Contact Form Submission:

Name: {name}
Email: {email}
Mobile: {mobile}

Message:
{message}
"""

        send_email("timeshare.co@gmail.com", "New Contact Message", full_message)

        flash("Message sent successfully!", "success")
        return redirect("/contact")

    return render_template("contact.html")
# ================= SERVER START =================

if __name__ == "__main__":
    socketio.run(app, debug=True)