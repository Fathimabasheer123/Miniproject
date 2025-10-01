from app import create_app
import os

app = create_app()

@app.context_processor
def inject_gemini_status():
    from app.services.gemini_api import gemini_api
    return {
        'gemini_available': gemini_api.is_available(),
        'gemini_api_key_set': bool(os.getenv('GEMINI_API_KEY'))
    }

if __name__ == "__main__":
    if not os.getenv('GEMINI_API_KEY'):
        print("⚠️  WARNING: GEMINI_API_KEY not set!")
    
    if app.secret_key == 'dev-secret-key-change-in-production':
        print("⚠️  WARNING: Using default secret key!")
    
    print("🚀 Starting QuizGen Application...")
    app.run(debug=True, host='0.0.0.0', port=5000)