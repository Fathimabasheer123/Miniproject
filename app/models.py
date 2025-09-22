from app import db
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import json

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    preferences = db.Column(db.Text, default='{"theme": "light"}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    quizzes = db.relationship('Quiz', backref='author', lazy=True)
    quiz_attempts = db.relationship('QuizAttempt', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_preferences(self):
        return json.loads(self.preferences)
    
    def set_preferences(self, preferences_dict):
        self.preferences = json.dumps(preferences_dict)

class Quiz(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, default="Generated Quiz")
    context = db.Column(db.Text)  # The original text used to generate the quiz
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Relationships
    questions = db.relationship('Question', backref='quiz', lazy=True, cascade='all, delete-orphan')
    attempts = db.relationship('QuizAttempt', backref='quiz', lazy=True, cascade='all, delete-orphan')

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text)  # JSON string of options
    answer = db.Column(db.String(200), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    
    def get_options(self):
        return json.loads(self.options)
    
    def set_options(self, options_list):
        self.options = json.dumps(options_list)

class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quiz.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    answers = db.Column(db.Text)  # JSON string of user's answers
    
    def get_answers(self):
        return json.loads(self.answers)
    
    def set_answers(self, answers_dict):
        self.answers = json.dumps(answers_dict)