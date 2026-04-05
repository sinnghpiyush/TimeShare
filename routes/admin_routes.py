from flask import Blueprint, render_template, session, redirect, flash, request
from config import get_db_connection
from werkzeug.utils import secure_filename
import os

admin = Blueprint("admin", __name__)

# ================= ADMIN PANEL =================

@admin.route("/admin")
def admin_panel():

    search_user = request.args.get("search_user")
    search_booking = request.args.get("search_booking")
    search_blog = request.args.get("search_blog")

    if "admin_secure" not in session:
        return redirect("/admin-secure-login")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    query = "SELECT * FROM users WHERE 1=1"
    params = []

    if search_user:
        query += " AND (name LIKE %s OR email LIKE %s)"
        params.append("%" + search_user + "%")
        params.append("%" + search_user + "%")

    cursor.execute(query, tuple(params))
    users = cursor.fetchall()

    query = "SELECT * FROM bookings WHERE 1=1"
    params = []

    if search_booking:
        query += " AND id = %s"
        params.append(search_booking)

    cursor.execute(query, tuple(params))
    bookings = cursor.fetchall()

    query = "SELECT * FROM blogs WHERE 1=1"
    params = []

    if search_blog:
        query += " AND title LIKE %s"
        params.append("%" + search_blog + "%")

    query += " ORDER BY created_at DESC"

    cursor.execute(query, tuple(params))
    blogs = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as total FROM users")
    total_users = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role='Mentor'")
    total_mentors = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role='Student'")
    total_students = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as total FROM bookings")
    total_bookings = cursor.fetchone()["total"]

    cursor.close()
    db.close()

    return render_template(
        "admin_panel.html",
        users=users,
        bookings=bookings,
        blogs=blogs,
        total_users=total_users,
        total_mentors=total_mentors,
        total_students=total_students,
        total_bookings=total_bookings
    )


# ================= ADD BLOG =================

@admin.route("/add-blog", methods=["POST"])
def add_blog():

    if "admin_secure" not in session:
        return redirect("/admin-secure-login")

    if session.get("role","").lower() != "admin":
        return redirect("/dashboard")

    title = request.form.get("title")
    content = request.form.get("content")
    category = request.form.get("category")

    featured_image = None

    if "featured_image" in request.files:
        file = request.files["featured_image"]

        if file and file.filename != "":
            filename = secure_filename(file.filename)

            upload_folder = os.path.join("static","uploads")
            os.makedirs(upload_folder, exist_ok=True)

            file_path = os.path.join(upload_folder, filename)
            file.save(file_path)

            featured_image = filename

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO blogs (title, content, featured_image, category)
        VALUES (%s,%s,%s,%s)
        """,
        (title,content,featured_image,category)
    )

    db.commit()
    cursor.close()
    db.close()

    flash("Blog Published Successfully","success")

    return redirect("/admin#blogs-section")

# ================= IMAGE UPLOAD FOR CKEDITOR =================

@admin.route("/upload-image", methods=["POST"])
def upload_image():

    if "upload" not in request.files:
        return {"error": {"message": "No file uploaded"}}, 400

    file = request.files["upload"]

    filename = secure_filename(file.filename)

    upload_folder = os.path.join("static", "uploads")
    os.makedirs(upload_folder, exist_ok=True)

    path = os.path.join(upload_folder, filename)
    file.save(path)

    return {
        "url": "/static/uploads/" + filename
    }

# ================= DELETE BLOG =================

@admin.route("/delete-blog/<int:blog_id>")
def delete_blog(blog_id):

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role", "").strip().lower() != "admin":
        flash("Access Denied!", "danger")
        return redirect("/dashboard")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("DELETE FROM blogs WHERE id=%s", (blog_id,))
    db.commit()

    cursor.close()
    db.close()

    flash("Blog deleted successfully!", "success")
    return redirect("/admin#blogs-section")


# ================= DELETE USER =================

@admin.route("/delete-user/<int:user_id>")
def delete_user(user_id):

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role", "").strip().lower() != "admin":
        flash("Access Denied!", "danger")
        return redirect("/dashboard")

    if user_id == session["user_id"]:
        flash("You cannot delete your own account!", "warning")
        return redirect("/admin#users-section")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("DELETE FROM bookings WHERE student_id=%s OR mentor_id=%s", (user_id, user_id))
    cursor.execute("DELETE FROM mentor_profile WHERE user_id=%s", (user_id,))
    cursor.execute("DELETE FROM users WHERE user_id=%s", (user_id,))

    db.commit()
    cursor.close()
    db.close()

    flash("User deleted successfully!", "success")
    return redirect("/admin#users-section")


# ================= DELETE BOOKING =================

@admin.route("/delete-booking/<int:booking_id>")
def delete_booking(booking_id):

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role", "").strip().lower() != "admin":
        flash("Access Denied!", "danger")
        return redirect("/dashboard")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("DELETE FROM bookings WHERE id=%s", (booking_id,))
    db.commit()

    cursor.close()
    db.close()

    flash("Booking deleted successfully!", "success")
    return redirect("/admin#bookings-section")


# ================= CHANGE ROLE =================

@admin.route("/change-role/<int:user_id>/<string:new_role>")
def change_role(user_id, new_role):

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role", "").strip().lower() != "admin":
        flash("Access Denied!", "danger")
        return redirect("/dashboard")

    if new_role not in ["Student", "Mentor", "Admin"]:
        flash("Invalid Role!", "danger")
        return redirect("/admin#users-section")

    db = get_db_connection()
    cursor = db.cursor()

    cursor.execute("UPDATE users SET role=%s WHERE user_id=%s", (new_role, user_id))

    db.commit()
    cursor.close()
    db.close()

    flash("User role updated successfully!", "success")
    return redirect("/admin#users-section")

    # ================= EDIT BLOG PAGE =================

@admin.route("/edit-blog/<int:blog_id>")
def edit_blog(blog_id):

    if "user_id" not in session:
        return redirect("/login")

    if session.get("role","").lower() != "admin":
        return redirect("/dashboard")

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM blogs WHERE id=%s",(blog_id,))
    blog = cursor.fetchone()

    cursor.close()
    db.close()

    return render_template("edit_blog.html", blog=blog)



# ================= UPDATE BLOG =================

@admin.route("/update-blog/<int:blog_id>", methods=["POST"])
def update_blog(blog_id):

    title = request.form.get("title")
    content = request.form.get("content")

    featured_image = None

    if "featured_image" in request.files:
        file = request.files["featured_image"]

        if file.filename != "":
            filename = secure_filename(file.filename)

            upload_folder = os.path.join("static","uploads")
            os.makedirs(upload_folder, exist_ok=True)

            path = os.path.join(upload_folder, filename)
            file.save(path)

            featured_image = filename

    db = get_db_connection()
    cursor = db.cursor()

    if featured_image:

        cursor.execute(
        """
        UPDATE blogs
        SET title=%s, content=%s, featured_image=%s
        WHERE id=%s
        """,
        (title,content,featured_image,blog_id)
        )

    else:

        cursor.execute(
        """
        UPDATE blogs
        SET title=%s, content=%s
        WHERE id=%s
        """,
        (title,content,blog_id)
        )

    db.commit()
    cursor.close()
    db.close()

    flash("Blog updated successfully","success")

    return redirect("/admin#blogs-section")