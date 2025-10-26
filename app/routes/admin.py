from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from app.models.database import get_db_connection, login_required
from functools import wraps
import json
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_role') != 'admin':
            flash("Administrator access required", "error")
            return redirect(url_for('quiz.dashboard'))
        return f(*args, **kwargs)
    return decorated

@admin_bp.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    """Main admin dashboard"""
    conn = get_db_connection()
    
    # System Statistics - EXCLUDE admin users
    stats = {
        'total_users': conn.execute('SELECT COUNT(*) FROM users WHERE role != "admin"').fetchone()[0],
        'total_quizzes': conn.execute('SELECT COUNT(*) FROM quizzes').fetchone()[0],
        'total_attempts': conn.execute('SELECT COUNT(*) FROM quiz_attempts').fetchone()[0],
        'active_today': conn.execute('''
            SELECT COUNT(DISTINCT user_id) FROM quiz_attempts 
            WHERE DATE(completed_at) = DATE('now')
            AND user_id IN (SELECT id FROM users WHERE role != "admin")
        ''').fetchone()[0]
    }
    
    # Recent Activity - EXCLUDE admin activities
    recent_activity = conn.execute('''
        SELECT u.username, q.title, qa.score, qa.total_questions, qa.completed_at
        FROM quiz_attempts qa
        JOIN users u ON qa.user_id = u.id
        JOIN quizzes q ON qa.quiz_id = q.id
        WHERE u.role != "admin"
        ORDER BY qa.completed_at DESC
        LIMIT 10
    ''').fetchall()
    
    # Popular Topics
    popular_topics = conn.execute('''
        SELECT q.title, COUNT(qa.id) as attempt_count, 
               AVG(qa.score * 100.0 / qa.total_questions) as avg_score
        FROM quizzes q
        JOIN quiz_attempts qa ON q.id = qa.quiz_id
        JOIN users u ON qa.user_id = u.id
        WHERE u.role != "admin"
        GROUP BY q.id, q.title
        ORDER BY attempt_count DESC
        LIMIT 10
    ''').fetchall()
    
    # AI Usage Statistics
    ai_usage = conn.execute('''
        SELECT difficulty, COUNT(*) as count,
               AVG(LENGTH(context)) as avg_context_length
        FROM quizzes
        GROUP BY difficulty
    ''').fetchall()
    
    # Daily activity for charts - EXCLUDE admin activities
    daily_activity = conn.execute('''
        SELECT DATE(completed_at) as date, 
               COUNT(*) as attempts,
               COUNT(DISTINCT user_id) as active_users
        FROM quiz_attempts
        WHERE completed_at >= date('now', '-7 days')
        AND user_id IN (SELECT id FROM users WHERE role != "admin")
        GROUP BY DATE(completed_at)
        ORDER BY date
    ''').fetchall()
    
    conn.close()
    
    return render_template(
        "admin_dashboard.html",
        stats=stats,
        recent_activity=recent_activity,
        popular_topics=popular_topics,
        ai_usage=ai_usage,
        daily_activity=daily_activity
    )

@admin_bp.route("/admin/users")
@login_required
@admin_required
def manage_users():
    """User management interface - EXCLUDE admin users"""
    conn = get_db_connection()
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    users = conn.execute('''
        SELECT u.*, 
               COUNT(DISTINCT q.id) as quizzes_created,
               COUNT(DISTINCT qa.id) as quizzes_taken,
               COALESCE(AVG(qa.score * 100.0 / qa.total_questions), 0) as avg_score,
               MAX(qa.completed_at) as last_active
        FROM users u
        LEFT JOIN quizzes q ON u.id = q.user_id
        LEFT JOIN quiz_attempts qa ON u.id = qa.user_id
        WHERE u.role != "admin"  -- EXCLUDE admin users
        GROUP BY u.id
        ORDER BY u.created_at DESC
        LIMIT ? OFFSET ?
    ''', (per_page, offset)).fetchall()
    
    total_users = conn.execute('SELECT COUNT(*) FROM users WHERE role != "admin"').fetchone()[0]
    total_pages = (total_users + per_page - 1) // per_page
    
    conn.close()
    
    return render_template("admin_users.html", users=users, page=page, total_pages=total_pages)

@admin_bp.route("/admin/quizzes")
@login_required
@admin_required
def manage_quizzes():
    """Quiz management interface"""
    conn = get_db_connection()
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page
    
    quizzes = conn.execute('''
        SELECT q.*, u.username,
               COUNT(qa.id) as attempt_count,
               AVG(qa.score * 100.0 / qa.total_questions) as avg_score
        FROM quizzes q
        JOIN users u ON q.user_id = u.id
        LEFT JOIN quiz_attempts qa ON q.id = qa.quiz_id
        WHERE u.role != "admin"  -- EXCLUDE quizzes created by admin
        GROUP BY q.id
        ORDER BY q.generated_at DESC
        LIMIT ? OFFSET ?
    ''', (per_page, offset)).fetchall()
    
    total_quizzes = conn.execute('''
        SELECT COUNT(*) FROM quizzes q 
        JOIN users u ON q.user_id = u.id 
        WHERE u.role != "admin"
    ''').fetchone()[0]
    total_pages = (total_quizzes + per_page - 1) // per_page
    
    conn.close()
    
    return render_template("admin_quizzes.html", quizzes=quizzes, page=page, total_pages=total_pages)

@admin_bp.route("/admin/analytics")
@login_required
@admin_required
def analytics():
    """Advanced analytics dashboard - EXCLUDE admin data"""
    conn = get_db_connection()
    
    # Time-based analytics - EXCLUDE admin activities
    daily_activity = conn.execute('''
        SELECT DATE(completed_at) as date, 
               COUNT(*) as attempts,
               COUNT(DISTINCT user_id) as active_users,
               AVG(score * 100.0 / total_questions) as avg_score
        FROM quiz_attempts
        WHERE completed_at >= date('now', '-30 days')
        AND user_id IN (SELECT id FROM users WHERE role != "admin")
        GROUP BY DATE(completed_at)
        ORDER BY date
    ''').fetchall()
    
    # Performance analytics - EXCLUDE admin attempts
    performance_stats = conn.execute('''
        SELECT 
            difficulty,
            COUNT(*) as total_attempts,
            AVG(score * 100.0 / total_questions) as avg_score,
            AVG(time_spent) as avg_time_spent
        FROM quiz_attempts qa
        JOIN users u ON qa.user_id = u.id
        WHERE u.role != "admin"
        GROUP BY difficulty
    ''').fetchall()
    
    # User engagement - EXCLUDE admin users
    engagement_stats = conn.execute('''
        SELECT 
            CASE 
                WHEN quizzes_taken >= 10 THEN 'Power User'
                WHEN quizzes_taken >= 5 THEN 'Active User' 
                WHEN quizzes_taken >= 1 THEN 'Casual User'
                ELSE 'Inactive'
            END as user_type,
            COUNT(*) as user_count,
            AVG(avg_score) as avg_score
        FROM (
            SELECT 
                u.id,
                COUNT(qa.id) as quizzes_taken,
                AVG(qa.score * 100.0 / qa.total_questions) as avg_score
            FROM users u
            LEFT JOIN quiz_attempts qa ON u.id = qa.user_id
            WHERE u.role != "admin"
            GROUP BY u.id
        )
        GROUP BY user_type
    ''').fetchall()
    
    # AI Usage patterns
    ai_patterns = conn.execute('''
        SELECT 
            strftime('%H', generated_at) as hour,
            COUNT(*) as quiz_count,
            AVG(LENGTH(context)) as avg_context_length
        FROM quizzes q
        JOIN users u ON q.user_id = u.id
        WHERE u.role != "admin"
        GROUP BY strftime('%H', generated_at)
        ORDER BY hour
    ''').fetchall()
    
    conn.close()
    
    return render_template(
        "admin_analytics.html",
        daily_activity=daily_activity,
        performance_stats=performance_stats,
        engagement_stats=engagement_stats,
        ai_patterns=ai_patterns
    )

@admin_bp.route("/admin/exit")
@login_required
@admin_required
def exit_admin():
    """Exit admin mode and return to main dashboard"""
    flash("Exited admin mode", "info")
    session.pop('admin_mode', None)
    # Try different possible dashboard routes
    try:
        return redirect(url_for('auth.admin_login'))
    except:
        try:
            return redirect(url_for('/admin/login'))
        except:
            return redirect('/login')

@admin_bp.route("/admin/api/delete_user/<int:user_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_user(user_id):
    """Delete user (admin only) - Prevent admin self-deletion"""
    conn = get_db_connection()
    
    try:
        # Check if user is admin (prevent deleting admin accounts)
        user_role = conn.execute('SELECT role FROM users WHERE id = ?', (user_id,)).fetchone()
        if user_role and user_role[0] == 'admin':
            return jsonify({"error": "Cannot delete administrator accounts"}), 400
        
        conn.execute('DELETE FROM quiz_attempts WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM quizzes WHERE user_id = ?', (user_id,))
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        
        return jsonify({"success": True, "message": "User deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@admin_bp.route("/admin/api/delete_quiz/<int:quiz_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_quiz(quiz_id):
    """Delete quiz and associated data"""
    conn = get_db_connection()
    
    try:
        conn.execute('DELETE FROM quiz_attempts WHERE quiz_id = ?', (quiz_id,))
        conn.execute('DELETE FROM quizzes WHERE id = ?', (quiz_id,))
        conn.commit()
        
        return jsonify({"success": True, "message": "Quiz deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

@admin_bp.route("/admin/api/stats")
@login_required
@admin_required
def get_live_stats():
    """API endpoint for live statistics - EXCLUDE admin data"""
    conn = get_db_connection()
    
    stats = {
        'users_24h': conn.execute('''
            SELECT COUNT(*) FROM users 
            WHERE created_at >= datetime('now', '-1 day')
            AND role != "admin"
        ''').fetchone()[0],
        'quizzes_24h': conn.execute('''
            SELECT COUNT(*) FROM quizzes q
            JOIN users u ON q.user_id = u.id
            WHERE generated_at >= datetime('now', '-1 day')
            AND u.role != "admin"
        ''').fetchone()[0],
        'attempts_24h': conn.execute('''
            SELECT COUNT(*) FROM quiz_attempts qa
            JOIN users u ON qa.user_id = u.id
            WHERE completed_at >= datetime('now', '-1 day')
            AND u.role != "admin"
        ''').fetchone()[0],
        'active_sessions': conn.execute('''
            SELECT COUNT(DISTINCT user_id) FROM quiz_attempts 
            WHERE completed_at >= datetime('now', '-30 minutes')
            AND user_id IN (SELECT id FROM users WHERE role != "admin")
        ''').fetchone()[0]
    }
    
    conn.close()
    
    return jsonify(stats)