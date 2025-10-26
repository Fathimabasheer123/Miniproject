from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import json

from app.models.database import get_db_connection, login_required
from app.routes.utils import is_valid_username, is_valid_password
from werkzeug.security import generate_password_hash, check_password_hash

settings_bp = Blueprint('settings', __name__)

@settings_bp.route("/settings")
@login_required
def settings():
    """User settings page"""
    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE id = ?', (session['user_id'],)
    ).fetchone()
    conn.close()
    
    preferences = json.loads(user['preferences'])
    current_theme = preferences.get('theme', 'light')
    
    return render_template("settings.html", user=user, current_theme=current_theme)

@settings_bp.route("/update_profile", methods=["POST"])
@login_required
def update_profile():
    """Update user profile"""
    new_username = request.form.get("username")
    
    if not new_username or not is_valid_username(new_username):
        flash("Invalid username", "error")
        return redirect(url_for("settings.settings"))
    
    conn = get_db_connection()
    
    existing_user = conn.execute(
        'SELECT * FROM users WHERE username = ? AND id != ?', 
        (new_username, session['user_id'])
    ).fetchone()
    
    if existing_user:
        flash("Username already taken", "error")
        conn.close()
        return redirect(url_for("settings.settings"))
    
    conn.execute(
        'UPDATE users SET username = ? WHERE id = ?',
        (new_username, session['user_id'])
    )
    conn.commit()
    conn.close()
    
    session['user'] = new_username
    flash("Profile updated successfully", "success")
    return redirect(url_for("settings.settings"))

@settings_bp.route("/change_password", methods=["POST"])
@login_required
def change_password():
    """Change user password"""
    current_password = request.form.get("current_password")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    
    if not current_password or not new_password or not confirm_password:
        flash("All fields are required", "error")
        return redirect(url_for("settings.settings"))
    
    conn = get_db_connection()
    user = conn.execute(
        'SELECT * FROM users WHERE id = ?', (session['user_id'],)
    ).fetchone()
    
    if not check_password_hash(user['password_hash'], current_password):
        flash("Current password is incorrect", "error")
        conn.close()
        return redirect(url_for("settings.settings"))
    
    if new_password != confirm_password:
        flash("New passwords do not match", "error")
        conn.close()
        return redirect(url_for("settings.settings"))
    
    if not is_valid_password(new_password):
        flash("Password must be 8+ characters with uppercase, lowercase, digit, and special character", "error")
        conn.close()
        return redirect(url_for("settings.settings"))
    
    new_password_hash = generate_password_hash(new_password)
    conn.execute(
        'UPDATE users SET password_hash = ? WHERE id = ?',
        (new_password_hash, session['user_id'])
    )
    conn.commit()
    conn.close()
    
    flash("Password updated successfully", "success")
    return redirect(url_for("settings.settings"))

@settings_bp.route("/update_preferences", methods=["POST"])
@login_required
def update_preferences():
    """Update user preferences"""
    theme = request.form.get("theme", "light")
    
    if theme not in ["light", "dark", "purple"]:
        theme = "light"
    
    conn = get_db_connection()
    
    user = conn.execute(
        'SELECT * FROM users WHERE id = ?', (session['user_id'],)
    ).fetchone()
    
    preferences = json.loads(user['preferences'])
    preferences['theme'] = theme
    
    conn.execute(
        'UPDATE users SET preferences = ? WHERE id = ?',
        (json.dumps(preferences), session['user_id'])
    )
    conn.commit()
    conn.close()
    
    flash("Preferences updated successfully", "success")
    return jsonify({'success': True})

@settings_bp.route("/update_theme_ajax", methods=["POST"])
@login_required
def update_theme_ajax():
    """Update theme via AJAX - for instant switching"""
    theme = request.json.get('theme', 'light')
    
    if theme not in ["light", "dark", "purple"]:
        return jsonify({'success': False})
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    preferences = json.loads(user['preferences'])
    preferences['theme'] = theme
    
    conn.execute(
        'UPDATE users SET preferences = ? WHERE id = ?',
        (json.dumps(preferences), session['user_id'])
    )
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@settings_bp.route("/delete_account", methods=["POST"])
@login_required
def delete_account():
    """Delete user account"""
    conn = get_db_connection()
    
    conn.execute('DELETE FROM quiz_attempts WHERE user_id = ?', (session['user_id'],))
    conn.execute('DELETE FROM questions WHERE quiz_id IN (SELECT id FROM quizzes WHERE user_id = ?)', (session['user_id'],))
    conn.execute('DELETE FROM quizzes WHERE user_id = ?', (session['user_id'],))
    conn.execute('DELETE FROM users WHERE id = ?', (session['user_id'],))
    
    conn.commit()
    conn.close()
    
    session.clear()
    
    flash("Your account has been deleted", "info")
    return redirect(url_for("auth.index"))