from flask import Blueprint, render_template, request, jsonify, session, flash, send_file, url_for, redirect
import PyPDF2
import json
import os
import re
import tempfile
import io
from pptx import Presentation
from docx import Document
from fpdf import FPDF
from datetime import datetime
from werkzeug.utils import secure_filename

# OCR imports with path configuration
try:
    import pytesseract
    from PIL import Image
    
    # Set Tesseract path explicitly
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    # Test if Tesseract is accessible
    try:
        version = pytesseract.get_tesseract_version()
        OCR_AVAILABLE = True
        print(f"✅ OCR configured successfully! Tesseract version: {version}")
    except Exception as e:
        print(f"❌ Tesseract not accessible: {e}")
        OCR_AVAILABLE = False
        
except ImportError as e:
    OCR_AVAILABLE = False
    print(f"⚠️ OCR dependencies not installed: {e}")

# PDF processing imports
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
    print("✅ pdfplumber available for enhanced PDF processing")
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    print("⚠️ pdfplumber not available, using PyPDF2 only")

# pdf2image for scanned PDFs
try:
    from pdf2image import convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
    print("✅ pdf2image available for scanned PDF processing")
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    print("⚠️ pdf2image not available")

from app.models.database import get_db_connection, login_required
from app.services.gemini_api import gemini_api

quiz_bp = Blueprint('quiz', __name__)

def extract_text_from_scanned_pdf(pdf_file):
    """Extract text from scanned PDF using OCR"""
    try:
        # Method 1: Use pdf2image + pytesseract
        if PDF2IMAGE_AVAILABLE:
            try:
                images = convert_from_bytes(pdf_file.read())
                text = ""
                for i, image in enumerate(images):
                    page_text = pytesseract.image_to_string(image)
                    text += f"Page {i+1}:\n{page_text}\n\n"
                print(f"✅ Extracted {len(text)} characters from scanned PDF via pdf2image OCR")
                return text
            except Exception as e:
                print(f"pdf2image OCR failed: {e}")
        
        # Method 2: Fallback - provide user instructions
        print("⚠️ Advanced scanned PDF processing not fully available")
        return ""
        
    except Exception as e:
        print(f"Scanned PDF extraction error: {e}")
        return ""

def enhanced_pdf_extraction(pdf_file):
    """Try multiple methods to extract text from PDF"""
    best_text = ""
    best_method = ""
    
    # Reset file pointer
    pdf_file.seek(0)
    
    # Method 1: Try pdfplumber (best for text PDFs)
    if PDFPLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(pdf_file) as pdf:
                text = "".join(page.extract_text() or "" for page in pdf.pages)
                if len(text.strip()) > len(best_text.strip()):
                    best_text = text
                    best_method = "pdfplumber"
                    print(f"📄 pdfplumber extracted {len(text)} characters")
        except Exception as e:
            print(f"pdfplumber failed: {e}")
    
    # Method 2: Try PyPDF2 (fallback)
    pdf_file.seek(0)
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = "".join(page.extract_text() or "" for page in reader.pages)
        if len(text.strip()) > len(best_text.strip()):
            best_text = text
            best_method = "PyPDF2"
            print(f"📄 PyPDF2 extracted {len(text)} characters")
    except Exception as e:
        print(f"PyPDF2 failed: {e}")
    
    if best_text:
        print(f"✅ Best PDF extraction: {best_method} with {len(best_text)} characters")
    
    return best_text, best_method

@quiz_bp.route("/dashboard")
@login_required
def dashboard():
    """User dashboard"""
    conn = get_db_connection()
    uid = session['user_id']
    
    # Get basic stats
    quizzes_completed = conn.execute(
        'SELECT COUNT(*) FROM quiz_attempts WHERE user_id=?', (uid,)
    ).fetchone()[0]
    
    avg_score = conn.execute(
        'SELECT AVG(score * 100.0 / total_questions) FROM quiz_attempts WHERE user_id=?', (uid,)
    ).fetchone()[0]
    average_score = round(avg_score, 1) if avg_score else 0
    
    quizzes_created = conn.execute(
        'SELECT COUNT(*) FROM quizzes WHERE user_id=?', (uid,)
    ).fetchone()[0]
    
    total_time = conn.execute(
        'SELECT COALESCE(SUM(time_spent), 0) FROM quiz_attempts WHERE user_id=?', (uid,)
    ).fetchone()[0]
    
    streak_result = conn.execute('''
        SELECT COUNT(DISTINCT DATE(completed_at)) as streak
        FROM quiz_attempts 
        WHERE user_id = ? AND completed_at >= date('now', '-30 days')
        ORDER BY completed_at DESC
    ''', (uid,)).fetchone()
    days_streak = streak_result['streak'] if streak_result else 0
    
    recent = conn.execute('''
        SELECT q.title, qa.score, qa.total_questions, qa.completed_at, qa.difficulty
        FROM quiz_attempts qa
        JOIN quizzes q ON qa.quiz_id = q.id
        WHERE qa.user_id = ?
        ORDER BY qa.completed_at DESC
        LIMIT 5
    ''', (uid,)).fetchall()
    conn.close()

    stats = {
        'quizzes_completed': quizzes_completed,
        'average_score': average_score,
        'quizzes_created': quizzes_created,
        'total_time_spent': total_time // 60,
        'progress_percentage': min(100, round((quizzes_completed / 20) * 100)),
        'quizzes_goal': 20,
        'days_streak': days_streak
    }

    achievements = {
        'first_quiz': quizzes_completed >= 1,
        'quiz_master': quizzes_completed >= 10,
        'perfect_score': any(r['score'] == r['total_questions'] for r in recent),
        'streak_7': days_streak >= 7,
        'gemini_expert': quizzes_created >= 5,
        'difficulty_master': any(r.get('difficulty') == 'hard' for r in recent),
        'earned': 0,
        'total': 6
    }
    achievements['earned'] = sum(
        1 for k, v in achievements.items()
        if v and k not in ['earned', 'total']
    )
    stats['achievements'] = achievements

    return render_template(
        "dashboard.html",
        user=session['user'],
        stats=stats,
        recent_quizzes=[{
            'title': r['title'],
            'score': round((r['score'] / r['total_questions']) * 100),
            'date': r['completed_at'][:10],
            'difficulty': r.get('difficulty', 'medium')
        } for r in recent]
    )

@quiz_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload_file():
    """Handle file upload and text extraction"""
    if request.method == "GET":
        return render_template("upload.html")
    
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    f = request.files["file"]
    if f.filename == '':
        return jsonify({"error": "No file selected"}), 400
    
    filename = secure_filename(f.filename)
    context = ""
    
    try:
        if filename.endswith(".pdf"):
            # Use enhanced PDF extraction
            context, method = enhanced_pdf_extraction(f)
            
            # If little/no text found, it's probably a scanned PDF
            if len(context.strip()) < 100:
                print("🔍 PDF appears to be scanned/handwritten - attempting OCR...")
                
                if not OCR_AVAILABLE:
                    return jsonify({
                        "error": "Scanned PDF detected but OCR not available. Please upload individual image files instead."
                    }), 400
                
                if not PDF2IMAGE_AVAILABLE:
                    return jsonify({
                        "error": "Scanned PDF detected. For best results, please save each page as an image (PNG/JPG) and upload separately.",
                        "suggestion": "Use 'Save as Image' in your PDF viewer or take screenshots of each page"
                    }), 400
                
                # Reset file pointer and try OCR
                f.seek(0)
                scanned_text = extract_text_from_scanned_pdf(f)
                
                if scanned_text and len(scanned_text.strip()) > 50:
                    context = scanned_text
                    print(f"✅ Successfully extracted {len(context)} characters from scanned PDF")
                else:
                    return jsonify({
                        "error": "Could not extract sufficient text from scanned PDF.",
                        "suggestions": [
                            "Ensure the PDF contains clear, readable text",
                            "Try uploading individual page images instead",
                            "Use a higher quality scan with better contrast"
                        ]
                    }), 400
            
        elif filename.endswith(".txt"):
            context = f.read().decode("utf-8")
            print(f"📝 Text file extracted {len(context)} characters")
            
        elif filename.endswith(".pptx"):
            prs = Presentation(f)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        context += shape.text + "\n"
            print(f"📊 PowerPoint extracted {len(context)} characters")
        
        elif filename.endswith(".docx"):
            doc = Document(f)
            context = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            print(f"📄 Word document extracted {len(context)} characters")
            
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif')):
            if not OCR_AVAILABLE:
                return jsonify({"error": "OCR not available. Please use text-based files (PDF, TXT, DOCX, PPTX)."}), 400
                
            try:
                f.seek(0)
                image_data = f.read()
                print(f"🖼️ Processing image: {filename}, Size: {len(image_data)} bytes")
                
                image = Image.open(io.BytesIO(image_data))
                context = pytesseract.image_to_string(image)
                
                print(f"📝 OCR extracted {len(context)} characters from image")
                
                if not context.strip():
                    return jsonify({"error": "No text detected in image. Please ensure the image is clear and contains readable text."}), 400
                    
            except Exception as ocr_error:
                print(f"❌ OCR Error: {str(ocr_error)}")
                return jsonify({"error": f"OCR processing failed: {str(ocr_error)}"}), 400
                
        else:
            supported_formats = "PDF, TXT, PPTX, DOCX"
            if OCR_AVAILABLE:
                supported_formats += ", PNG, JPG, JPEG"
            return jsonify({"error": f"Unsupported file format. Please upload {supported_formats}."}), 400
        
        # Clean and limit context
        original_length = len(context)
        context = re.sub(r'\s+', ' ', context).strip()
        context = context[:10000]
        
        print(f"✅ Final context: {len(context)} characters (from {original_length} original)")
        
        if len(context) < 100:
            return jsonify({"error": "Not enough text extracted from file. Please try a different file or ensure it contains sufficient readable content."}), 400
            
        return jsonify({"context": context})
        
    except Exception as e:
        print(f"❌ Upload Error: {e}")
        return jsonify({"error": f"Error processing file: {str(e)}"}), 500

@quiz_bp.route("/generate", methods=["POST"])
@login_required
def generate_questions():
    """Generate questions using Gemini API"""
    try:
        data = request.get_json()
        num_questions = int(data.get("num_questions", 10))
        difficulty = data.get("difficulty", "medium")
        context = data.get("context", "").strip()
        
        print(f"🧠 Generating {num_questions} {difficulty} questions from {len(context)} chars of context")
        
        if not context:
            return jsonify({"error": "Empty context"}), 400

        if not gemini_api.is_available():
            return jsonify({"error": "Gemini AI service is not available. Please check your API key configuration."}), 500

        gemini_questions = gemini_api.generate_questions(context, num_questions, difficulty)
        
        if not gemini_questions:
            return jsonify({"error": "Failed to generate questions with Gemini AI. Please try again with different content."}), 500

        question_types = list(set([q.get('type', 'MCQ') for q in gemini_questions]))
        print(f"✅ Generated {len(gemini_questions)} questions of types: {question_types}")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO quizzes (user_id, title, context, difficulty, question_types) VALUES (?, ?, ?, ?, ?)',
            (session['user_id'], 'Generated Quiz', context[:500], difficulty, json.dumps(question_types))
        )
        quiz_id = cur.lastrowid
        
        for q in gemini_questions:
            cur.execute(
                '''INSERT INTO questions (quiz_id, question_text, options, answer, question_type, explanation, difficulty) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (quiz_id, q['question'], json.dumps(q['options']), q['answer'], 
                 q.get('type', 'MCQ'), q.get('explanation', ''), q.get('difficulty', difficulty))
            )
        conn.commit()
        conn.close()

        session['current_quiz'] = gemini_questions
        session['current_quiz_id'] = quiz_id

        return jsonify({
            "source": "Gemini AI",
            "questions": gemini_questions,
            "message": f"Successfully generated {len(gemini_questions)} questions with explanations",
            "redirect": url_for("quiz.take_quiz")
        })

    except Exception as e:
        print(f"❌ Question generation failed: {e}")
        return jsonify({"error": f"Question generation failed: {str(e)}"}), 500

@quiz_bp.route("/take_quiz")
@login_required
def take_quiz():
    """Display the generated quiz"""
    quiz = session.get('current_quiz', [])
    if not quiz:
        flash("No quiz available. Please generate a quiz first.", "warning")
        return redirect(url_for("quiz.dashboard"))
    return render_template("quiz.html", questions=quiz)

@quiz_bp.route("/save_attempt", methods=["POST"])
@login_required
def save_attempt():
    """Save quiz attempt results"""
    data = request.get_json()
    quiz_id = session.get('current_quiz_id')
    
    if not quiz_id:
        return jsonify({"error": "No quiz id found"}), 400
    
    conn = get_db_connection()
    
    quiz = conn.execute(
        'SELECT difficulty, question_types FROM quizzes WHERE id = ?', (quiz_id,)
    ).fetchone()
    
    conn.execute(
        '''INSERT INTO quiz_attempts (user_id, quiz_id, score, total_questions, answers, time_spent, difficulty, question_types) 
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (session['user_id'], quiz_id, data['score'], data['total'], 
         json.dumps(data.get('answers', [])), data.get('time_spent', 0),
         quiz['difficulty'] if quiz else 'medium', 
         quiz['question_types'] if quiz else '[]')
    )
    conn.commit()
    conn.close()
    
    session.pop('current_quiz', None)
    session.pop('current_quiz_id', None)
    
    return jsonify({"success": True})

@quiz_bp.route("/download_pdf", methods=["POST"])
@login_required
def download_pdf():
    """Download quiz as PDF"""
    try:
        topic = request.form.get("topic", "Generated Quiz")
        questions_data = request.form.get("questions", "[]")
        
        try:
            questions = json.loads(questions_data)
        except Exception as e:
            flash("Invalid questions data", "error")
            return redirect(url_for("quiz.dashboard"))

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt=f"Quiz: {topic}", ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Total Questions: {len(questions)}", ln=True)
        pdf.cell(200, 10, txt=f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
        pdf.ln(10)
        
        for i, q in enumerate(questions, 1):
            pdf.set_font("Arial", 'B', 12)
            pdf.multi_cell(0, 10, f"{i}. {q.get('question', 'Question')}")
            pdf.set_font("Arial", size=12)
            
            if isinstance(q.get('options'), list) and q['options']:
                for j, opt in enumerate(q['options']):
                    pdf.cell(10)
                    pdf.multi_cell(0, 8, f"{chr(65 + j)}. {opt}")
            
            pdf.set_font("Arial", 'I', 12)
            pdf.multi_cell(0, 10, f"Answer: {q.get('answer', 'Not provided')}")
            
            if q.get('explanation'):
                pdf.multi_cell(0, 10, f"Explanation: {q.get('explanation')}")
            
            pdf.set_font("Arial", size=12)
            pdf.ln(5)

        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            pdf.output(tmp.name)
            tmp_path = tmp.name

        response = send_file(
            tmp_path,
            as_attachment=True,
            download_name=f"QuizGen_{topic.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mimetype='application/pdf'
        )
        
        @response.call_on_close
        def remove_temp_file():
            try:
                os.unlink(tmp_path)
            except:
                pass
                
        return response

    except Exception as e:
        print(f"❌ PDF Generation Error: {str(e)}")
        flash("Failed to generate PDF", "error")
        return redirect(url_for("quiz.dashboard"))