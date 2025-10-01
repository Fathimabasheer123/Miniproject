import re
from werkzeug.security import generate_password_hash, check_password_hash

def is_valid_username(username):
    """Validate username format"""
    return bool(re.match(r"^[A-Za-z0-9_]{3,}$", username))

def is_valid_email(email):
    """Validate email format"""
    return bool(re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email))

def is_valid_password(password):
    """Validate password strength"""
    return (len(password) >= 8 and
            re.search(r"[A-Z]", password) and
            re.search(r"[a-z]", password) and
            re.search(r"[0-9]", password) and
            re.search(r"[!@#$%^&*(),.?\":{}|<>]", password))