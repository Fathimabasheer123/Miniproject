import sqlite3
import os
from functools import wraps
from flask import session, redirect, url_for

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('instance/database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with all tables"""
    conn = get_db_connection()
    
    # Users table
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        preferences TEXT DEFAULT '{"theme": "light"}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Quizzes table
    conn.execute('''CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        context TEXT,
        difficulty TEXT DEFAULT 'medium',
        question_types TEXT DEFAULT '[]',
        topic TEXT DEFAULT 'General',
        generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # Questions table
    conn.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER NOT NULL,
        question_text TEXT NOT NULL,
        options TEXT NOT NULL,
        answer TEXT NOT NULL,
        question_type TEXT DEFAULT 'MCQ',
        explanation TEXT,
        difficulty TEXT DEFAULT 'medium',
        FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
    )''')
    
    # Quiz attempts table
    conn.execute('''CREATE TABLE IF NOT EXISTS quiz_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        quiz_id INTEGER NOT NULL,
        score INTEGER NOT NULL,
        total_questions INTEGER NOT NULL,
        answers TEXT NOT NULL,
        time_spent INTEGER DEFAULT 0,
        difficulty TEXT DEFAULT 'medium',
        question_types TEXT DEFAULT '[]',
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (quiz_id) REFERENCES quizzes (id)
    )''')
    
    # User progress table
    conn.execute('''CREATE TABLE IF NOT EXISTS user_progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date DATE NOT NULL,
        quizzes_taken INTEGER DEFAULT 0,
        average_score REAL DEFAULT 0,
        time_spent INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    conn.commit()
    conn.close()

def migrate_database():
    """Add new columns to existing tables without losing data"""
    conn = get_db_connection()
    
    try:
        conn.execute('ALTER TABLE quizzes ADD COLUMN topic TEXT DEFAULT "General"')
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute('ALTER TABLE questions ADD COLUMN explanation TEXT')
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute('ALTER TABLE questions ADD COLUMN difficulty TEXT DEFAULT "medium"')
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute('ALTER TABLE quiz_attempts ADD COLUMN time_spent INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    
    try:
        conn.execute('ALTER TABLE quiz_attempts ADD COLUMN question_types TEXT DEFAULT "[]"')
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

# Initialize database
init_db()
migrate_database()