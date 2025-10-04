from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from app.models.database import get_db_connection, login_required
from app.routes.utils import is_valid_username, is_valid_email, is_valid_password
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/")
def index():
    """Home page"""
    return render_template("index.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """User login"""
    error = None
    if request.method == "POST":
        login_id = request.form.get("email")
        password = request.form.get("password")
        if not login_id or not password: 
            error = "Both fields are required"
        else:
            conn = get_db_connection()
            user = conn.execute(
                'SELECT * FROM users WHERE username=? OR email=?',
                (login_id, login_id)
            ).fetchone()
            conn.close()
            if user and check_password_hash(user['password_hash'], password):
                session.update({
                    'user_id': user['id'],
                    'user': user['username'],
                    'user_email': user['email']
                })
                return redirect(url_for("quiz.dashboard"))
            error = "Invalid login credentials"
    return render_template("login.html", error=error)

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """User registration"""
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        if not username or not email or not password:
            error = "All fields are required"
        elif not is_valid_username(username): 
            error = "Username must be at least 3 characters with only letters, numbers, and underscores"
        elif not is_valid_email(email): 
            error = "Invalid email format"
        elif not is_valid_password(password): 
            error = "Password must be 8+ characters with uppercase, lowercase, digit, and special character"
        else:
            conn = get_db_connection()
            if conn.execute(
                'SELECT * FROM users WHERE username=? OR email=?', 
                (username, email)
            ).fetchone():
                error = "Username or email already registered"
            else:
                conn.execute(
                    'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                    (username, email, generate_password_hash(password))
                )
                conn.commit()
                user = conn.execute(
                    'SELECT * FROM users WHERE username=?', (username,)
                ).fetchone()
                session.update({
                    'user_id': user['id'],
                    'user': user['username'],
                    'user_email': user['email']
                })
                conn.close()
                return redirect(url_for("quiz.dashboard"))
            conn.close()
    return render_template("register.html", error=error)
@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    """Admin-specific login route"""
    if request.method == "GET":
        return render_template("admin_login.html")
    
    username = request.form.get("username")
    password = request.form.get("password")
    
    conn = get_db_connection()
    
    # Only allow users with 'admin' role to login
    user = conn.execute(
        'SELECT * FROM users WHERE (username = ? OR email = ?) AND role = "admin"', 
        (username, username)
    ).fetchone()
    
    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        session['user'] = user['username']
        session['user_role'] = user['role']  # Store admin role in session
        
        flash("Admin login successful!", "success")
        conn.close()
        return redirect(url_for('admin.admin_dashboard'))
    
    flash("Invalid admin credentials or insufficient privileges", "error")
    conn.close()
    return render_template("admin_login.html")

@auth_bp.route("/logout")
def logout():
    """User logout"""
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("auth.login"))