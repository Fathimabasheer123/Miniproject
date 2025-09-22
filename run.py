from flask import Flask
from app.routes import routes
import nltk

app = Flask(__name__)

# ---------------- SECRET KEY ----------------
app.secret_key = "your_secret_key_here_change_this_to_random_string"  # Change this!

# ---------------- FILE UPLOAD LIMIT ----------------
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload size

# ---------------- NLTK DOWNLOADS ----------------
try:
    nltk.data.find("corpora/wordnet")
except LookupError:
    nltk.download("wordnet")

# Register blueprint
app.register_blueprint(routes)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)