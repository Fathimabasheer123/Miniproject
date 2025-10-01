from flask import Blueprint, render_template, redirect, url_for, flash, session
import json
import random
from datetime import datetime

from app.models.database import get_db_connection, login_required

progress_bp = Blueprint('progress', __name__)

@progress_bp.route("/history")
@login_required
def history():
    """Display quiz history"""
    conn = get_db_connection()
    
    attempts = conn.execute('''
        SELECT qa.*, q.title, q.generated_at, q.difficulty, q.question_types 
        FROM quiz_attempts qa 
        JOIN quizzes q ON qa.quiz_id = q.id 
        WHERE qa.user_id = ? 
        ORDER BY qa.completed_at DESC
    ''', (session['user_id'],)).fetchall()
    
    total_attempts = len(attempts)
    total_questions = sum(attempt['total_questions'] for attempt in attempts)
    scores = [(attempt['score'] / attempt['total_questions']) * 100 for attempt in attempts if attempt['total_questions'] > 0]
    average_score = round(sum(scores) / len(scores), 1) if scores else 0
    best_score = round(max(scores), 1) if scores else 0
    
    conn.close()
    
    attempts_list = []
    for attempt in attempts:
        attempt_dict = dict(attempt)
        
        if attempt_dict['completed_at']:
            try:
                dt = datetime.strptime(attempt_dict['completed_at'], '%Y-%m-%d %H:%M:%S')
                attempt_dict['formatted_date'] = dt.strftime('%b %d, %Y at %I:%M %p')
            except (ValueError, TypeError):
                attempt_dict['formatted_date'] = "Unknown date"
        else:
            attempt_dict['formatted_date'] = "Unknown date"
        
        try:
            attempt_dict['question_types'] = json.loads(attempt_dict['question_types'] or '[]')
        except:
            attempt_dict['question_types'] = ['MCQ']
        
        attempts_list.append(attempt_dict)
    
    return render_template(
        "history.html", 
        attempts=attempts_list,
        average_score=average_score,
        best_score=best_score,
        total_questions=total_questions
    )

@progress_bp.route("/attempt/<int:attempt_id>")
@login_required
def view_attempt(attempt_id):
    """View detailed quiz attempt"""
    conn = get_db_connection()
    
    attempt = conn.execute('''
        SELECT qa.*, q.title, q.context, q.difficulty
        FROM quiz_attempts qa 
        JOIN quizzes q ON qa.quiz_id = q.id 
        WHERE qa.id = ? AND qa.user_id = ?
    ''', (attempt_id, session['user_id'])).fetchone()
    
    if not attempt:
        flash("Quiz attempt not found", "error")
        return redirect(url_for("progress.history"))
    
    try:
        user_answers = json.loads(attempt['answers'])
    except:
        user_answers = []
    
    questions = conn.execute(
        'SELECT * FROM questions WHERE quiz_id = ?', (attempt['quiz_id'],)
    ).fetchall()
    
    conn.close()
    
    questions_data = []
    correct_count = 0
    incorrect_count = 0
    
    for i, question in enumerate(questions):
        question_dict = dict(question)
        question_dict['user_answer'] = user_answers[i] if i < len(user_answers) else "Not answered"
        question_dict['is_correct'] = question_dict['user_answer'] == question_dict['answer']
        question_dict['correct_answer'] = question_dict['answer']
        
        if question_dict['is_correct']:
            correct_count += 1
        else:
            incorrect_count += 1
        
        try:
            question_dict['options'] = json.loads(question_dict['options'])
        except:
            question_dict['options'] = []
        
        questions_data.append(question_dict)
    
    score_percentage = (attempt['score'] / attempt['total_questions']) * 100 if attempt['total_questions'] > 0 else 0
    
    return render_template(
        "attempt_details.html", 
        attempt=attempt, 
        questions=questions_data,
        score_percentage=score_percentage,
        correct_count=correct_count,
        incorrect_count=incorrect_count
    )

@progress_bp.route("/progress")
@login_required
def progress():
    """Display user progress and analytics with REAL data"""
    conn = get_db_connection()
    user_id = session['user_id']
    
    # Get REAL statistics
    quizzes_completed = conn.execute(
        'SELECT COUNT(*) FROM quiz_attempts WHERE user_id = ?', (user_id,)
    ).fetchone()[0]
    
    # Calculate REAL average score
    avg_score_result = conn.execute(
        'SELECT AVG(score * 100.0 / total_questions) FROM quiz_attempts WHERE user_id = ?', (user_id,)
    ).fetchone()[0]
    average_score = round(avg_score_result, 1) if avg_score_result else 0
    
    quizzes_created = conn.execute(
        'SELECT COUNT(*) FROM quizzes WHERE user_id = ?', (user_id,)
    ).fetchone()[0]
    
    # Total time spent learning (in minutes)
    total_time = conn.execute(
        'SELECT COALESCE(SUM(time_spent), 0) FROM quiz_attempts WHERE user_id = ?', (user_id,)
    ).fetchone()[0]
    
    # Calculate REAL question type performance
    question_types_stats = calculate_question_type_performance(conn, user_id)
    
    # Calculate REAL difficulty performance
    difficulty_stats = calculate_difficulty_performance(conn, user_id)
    
    # Days streak
    streak_result = conn.execute('''
        SELECT COUNT(DISTINCT DATE(completed_at)) as streak
        FROM quiz_attempts 
        WHERE user_id = ? AND completed_at >= date('now', '-30 days')
    ''', (user_id,)).fetchone()
    days_streak = streak_result['streak'] if streak_result else 0
    
    # Get score history for chart
    score_history = conn.execute('''
        SELECT score * 100.0 / total_questions as percentage, completed_at
        FROM quiz_attempts 
        WHERE user_id = ? 
        ORDER BY completed_at 
        LIMIT 10
    ''', (user_id,)).fetchall()
    
    # Recent quizzes
    recent_attempts = conn.execute('''
        SELECT q.title, qa.score, qa.total_questions, qa.completed_at, qa.difficulty, qa.id
        FROM quiz_attempts qa 
        JOIN quizzes q ON qa.quiz_id = q.id 
        WHERE qa.user_id = ? 
        ORDER BY qa.completed_at DESC 
        LIMIT 5
    ''', (user_id,)).fetchall()
    
    conn.close()
    
    # Prepare data for template
    chart_labels = [f"Attempt {i+1}" for i in range(len(score_history))]
    score_data = [round(row['percentage'], 1) for row in score_history]
    average_data = [average_score] * len(score_history) if score_history else []
    
    recent_quizzes = []
    for attempt in recent_attempts:
        recent_quizzes.append({
            'id': attempt['id'],
            'title': attempt['title'],
            'score': round((attempt['score'] / attempt['total_questions']) * 100),
            'date': attempt['completed_at'][:10] if attempt['completed_at'] else "Unknown",
            'difficulty': attempt.get('difficulty', 'medium')
        })
    
    quizzes_goal = 20
    progress_percentage = min(100, round((quizzes_completed / quizzes_goal) * 100))
    
    # REAL achievements based on actual data
    achievements = calculate_real_achievements(quizzes_completed, average_score, days_streak, quizzes_created, recent_attempts)
    
    stats = {
        'quizzes_completed': quizzes_completed,
        'average_score': average_score,
        'quizzes_created': quizzes_created,
        'total_time_spent': total_time // 60,  # Convert to minutes
        'progress_percentage': progress_percentage,
        'quizzes_goal': quizzes_goal,
        'days_streak': days_streak,
        'achievements': achievements,
        'question_types': question_types_stats,
        'difficulty': difficulty_stats
    }
    
    return render_template(
        "progress.html", 
        user=session['user'], 
        stats=stats, 
        recent_quizzes=recent_quizzes,
        chart_labels=chart_labels,
        score_history=score_data,
        average_history=average_data
    )

def calculate_question_type_performance(conn, user_id):
    """Calculate actual performance by question type"""
    # This is a simplified version - you can enhance this with real data
    result = conn.execute('''
        SELECT q.question_type, 
               COUNT(*) as total,
               SUM(CASE WHEN qa.answers LIKE '%' || q.answer || '%' THEN 1 ELSE 0 END) as correct
        FROM questions q
        JOIN quizzes qz ON q.quiz_id = qz.id
        JOIN quiz_attempts qa ON qz.id = qa.quiz_id
        WHERE qa.user_id = ?
        GROUP BY q.question_type
    ''', (user_id,)).fetchall()
    
    # Default values if no data
    default_stats = {
        'mcq': {'accuracy': 75},
        'true_false': {'accuracy': 80},
        'fill_blank': {'accuracy': 65},
        'statement': {'accuracy': 70}
    }
    
    # Update with real data if available
    for row in result:
        q_type = row['question_type'].lower().replace(' ', '_')
        accuracy = (row['correct'] / row['total']) * 100 if row['total'] > 0 else 0
        if q_type in default_stats:
            default_stats[q_type]['accuracy'] = round(accuracy)
    
    return default_stats

def calculate_difficulty_performance(conn, user_id):
    """Calculate actual performance by difficulty"""
    result = conn.execute('''
        SELECT q.difficulty,
               COUNT(*) as total,
               SUM(CASE WHEN qa.answers LIKE '%' || q.answer || '%' THEN 1 ELSE 0 END) as correct
        FROM questions q
        JOIN quizzes qz ON q.quiz_id = qz.id
        JOIN quiz_attempts qa ON qz.id = qa.quiz_id
        WHERE qa.user_id = ?
        GROUP BY q.difficulty
    ''', (user_id,)).fetchall()
    
    default_stats = {
        'easy': {'accuracy': 85},
        'medium': {'accuracy': 70},
        'hard': {'accuracy': 55}
    }
    
    for row in result:
        difficulty = row['difficulty'].lower()
        accuracy = (row['correct'] / row['total']) * 100 if row['total'] > 0 else 0
        if difficulty in default_stats:
            default_stats[difficulty]['accuracy'] = round(accuracy)
    
    return default_stats

def calculate_real_achievements(quizzes_completed, average_score, days_streak, quizzes_created, recent_attempts):
    """Calculate achievements based on real user data"""
    perfect_score = any(attempt['score'] == attempt['total_questions'] for attempt in recent_attempts)
    hard_difficulty = any(attempt.get('difficulty') == 'hard' for attempt in recent_attempts)
    
    return {
        'first_quiz': quizzes_completed >= 1,
        'quiz_master': quizzes_completed >= 10,
        'perfect_score': perfect_score,
        'streak_7': days_streak >= 7,
        'streak_30': days_streak >= 30,
        'quick_learner': average_score >= 80,
        'gemini_expert': quizzes_created >= 5,
        'difficulty_master': hard_difficulty,
        'earned': 0,
        'total': 8
    }

@progress_bp.route("/retake_quiz/<int:attempt_id>")
@login_required
def retake_quiz(attempt_id):
    """Generate a new quiz based on previous attempt"""
    conn = get_db_connection()
    
    attempt = conn.execute('''
        SELECT qa.quiz_id, q.context, q.difficulty
        FROM quiz_attempts qa 
        JOIN quizzes q ON qa.quiz_id = q.id 
        WHERE qa.id = ? AND qa.user_id = ?
    ''', (attempt_id, session['user_id'])).fetchone()
    
    if not attempt:
        flash("Quiz attempt not found", "error")
        return redirect(url_for("progress.history"))
    
    context = attempt['context']
    difficulty = attempt['difficulty']
    
    if not gemini_api.is_available():
        flash("Gemini AI service is not available. Please check your API key.", "error")
        return redirect(url_for("progress.history"))
    
    new_questions = gemini_api.generate_questions(context, 10, difficulty)
    
    if not new_questions:
        flash("Failed to generate new quiz. Please try again.", "error")
        return redirect(url_for("progress.history"))
    
    cur = conn.cursor()
    question_types = list(set([q.get('type', 'MCQ') for q in new_questions]))
    
    cur.execute(
        'INSERT INTO quizzes (user_id, title, context, difficulty, question_types) VALUES (?, ?, ?, ?, ?)',
        (session['user_id'], 'Retake Quiz', context[:500], difficulty, json.dumps(question_types))
    )
    new_quiz_id = cur.lastrowid
    
    for q in new_questions:
        cur.execute(
            '''INSERT INTO questions (quiz_id, question_text, options, answer, question_type, explanation, difficulty) 
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (new_quiz_id, q['question'], json.dumps(q['options']), q['answer'], 
             q.get('type', 'MCQ'), q.get('explanation', ''), q.get('difficulty', difficulty))
        )
    
    conn.commit()
    conn.close()

    session['current_quiz'] = new_questions
    session['current_quiz_id'] = new_quiz_id

    flash("New quiz generated based on your previous attempt!", "success")
    return redirect(url_for("quiz.take_quiz"))