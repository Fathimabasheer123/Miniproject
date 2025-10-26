import sqlite3
import os
from functools import wraps
from flask import session, redirect, url_for
from werkzeug.security import generate_password_hash

def get_db_connection():
    """Get database connection"""
    # Create instance directory if it doesn't exist
    os.makedirs('instance', exist_ok=True)
    conn = sqlite3.connect('instance/database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with all tables"""
    conn = get_db_connection()
    
    # Users table WITH role column
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
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
    
    # Run migrations first to ensure all columns exist
    migrate_database()
    
    # Then create default admin
    create_default_admin()

def create_default_admin():
    """Create a default admin user if none exists"""
    conn = get_db_connection()
    
    try:
        # Check if admin user already exists
        admin_exists = conn.execute(
            'SELECT COUNT(*) FROM users WHERE username = ? AND role = ?', 
            ('admin', 'admin')
        ).fetchone()[0]
        
        if not admin_exists:
            # Check if there's any user with admin username but wrong role
            existing_admin = conn.execute(
                'SELECT * FROM users WHERE username = ?', ('admin',)
            ).fetchone()
            
            if existing_admin:
                # Update existing admin user to have correct role
                conn.execute(
                    'UPDATE users SET role = ? WHERE username = ?',
                    ('admin', 'admin')
                )
                print("✅ Updated existing admin user with admin role")
            else:
                # Create new admin user with default password "admin123"
                password_hash = generate_password_hash('admin123')
                conn.execute(
                    'INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
                    ('admin', 'admin@quizgen.com', password_hash, 'admin')
                )
                print("✅ Created default admin user: admin / admin123")
        
        conn.commit()
        
    except sqlite3.OperationalError as e:
        print(f"⚠️ Database error in create_default_admin: {e}")
        # If there's an error, it means we need to run migrations first
        print("⚠️ Running emergency migration...")
        migrate_database()
        # Try again after migration
        create_default_admin()
    
    finally:
        conn.close()

def migrate_database():
    """Add new columns to existing tables without losing data"""
    conn = get_db_connection()
    
    # List of migrations to run
    migrations = [
        ('users', 'role', 'TEXT DEFAULT "user"'),
        ('quizzes', 'topic', 'TEXT DEFAULT "General"'),
        ('questions', 'explanation', 'TEXT'),
        ('questions', 'difficulty', 'TEXT DEFAULT "medium"'),
        ('quiz_attempts', 'time_spent', 'INTEGER DEFAULT 0'),
        ('quiz_attempts', 'question_types', 'TEXT DEFAULT "[]"')
    ]
    
    for table, column, column_type in migrations:
        try:
            # Check if column exists by trying to select it
            conn.execute(f'SELECT {column} FROM {table} LIMIT 1')
            print(f"✅ Column '{column}' already exists in '{table}' table")
        except sqlite3.OperationalError:
            # Column doesn't exist, so add it
            try:
                conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {column_type}')
                print(f"✅ Added column '{column}' to '{table}' table")
            except sqlite3.OperationalError as e:
                print(f"⚠️ Failed to add column '{column}' to '{table}': {e}")
    
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
try:
    init_db()
    print("✅ Database initialized successfully!")
except Exception as e:
    print(f"❌ Database initialization failed: {e}")