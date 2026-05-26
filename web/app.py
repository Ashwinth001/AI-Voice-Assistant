"""
ASTRA Web Portal
User registration, theme selection, and feature configuration.
"""
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
import sys
import json
import hashlib
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

app = Flask(__name__)
app.secret_key = os.environ.get("ASTRA_WEB_SECRET", secrets.token_hex(32))

# Data directory
DATA_DIR = ROOT / "data" / "users"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Available themes
THEMES = [
    {"id": "holographic", "name": "Holographic", "desc": "Sci-fi Iron Man style", "color": "#00c8ff"},
    {"id": "neon_glass", "name": "Neon Glass", "desc": "Modern purple gradient", "color": "#a855f7"},
    {"id": "minimal", "name": "Minimal Dark", "desc": "Clean Apple-style", "color": "#ffffff"},
]

# Available features
FEATURES = [
    {"id": "voice", "name": "Voice Commands", "desc": "Control your PC by voice", "default": True},
    {"id": "pc_control", "name": "PC Control", "desc": "Files, apps, restart, shutdown", "default": True},
    {"id": "research", "name": "Web Research", "desc": "Learn from Wikipedia, GitHub", "default": True},
    {"id": "screen", "name": "Screen Analysis", "desc": "OCR and vision AI", "default": False},
    {"id": "email", "name": "Email Integration", "desc": "Read/send via Outlook", "default": False},
    {"id": "teams", "name": "Teams Integration", "desc": "Create meetings by voice", "default": False},
    {"id": "code", "name": "Code Generation", "desc": "Write code in any language", "default": True},
    {"id": "training", "name": "Self-Learning", "desc": "Improve from your feedback", "default": True},
]


def hash_password(password: str, salt: str = None) -> tuple:
    """Hash password with salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return hashed.hex(), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verify password against hash."""
    check_hash, _ = hash_password(password, salt)
    return check_hash == hashed


def get_user(email: str) -> dict:
    """Get user by email."""
    user_id = hashlib.md5(email.lower().encode()).hexdigest()[:12]
    user_file = DATA_DIR / f"{user_id}.json"
    if user_file.exists():
        return json.loads(user_file.read_text())
    return None


def save_user(user_data: dict):
    """Save user data."""
    user_file = DATA_DIR / f"{user_data['user_id']}.json"
    user_file.write_text(json.dumps(user_data, indent=2))


@app.route("/")
def index():
    """Landing page."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """User registration page."""
    if request.method == "GET":
        return render_template("register.html", themes=THEMES, features=FEATURES)
    
    # Process registration
    email = request.form.get("email", "").lower().strip()
    password = request.form.get("password", "")
    ai_name = request.form.get("ai_name", "ASTRA").strip()
    ai_theme = request.form.get("ai_theme", "holographic")
    selected_features = request.form.getlist("features")
    
    # Validation
    if not email or "@" not in email:
        flash("Please enter a valid email address.", "error")
        return redirect(url_for("register"))
    
    if len(password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("register"))
    
    if not ai_name:
        flash("Please enter a name for your AI.", "error")
        return redirect(url_for("register"))
    
    # Check if user exists
    if get_user(email):
        flash("An account with this email already exists.", "error")
        return redirect(url_for("register"))
    
    # Create user
    user_id = hashlib.md5(email.encode()).hexdigest()[:12]
    password_hash, salt = hash_password(password)
    
    user_data = {
        "user_id": user_id,
        "email": email,
        "password_hash": password_hash,
        "password_salt": salt,
        "ai_name": ai_name,
        "ai_theme": ai_theme,
        "features": selected_features if selected_features else ["voice", "pc_control", "research"],
        "created": str(Path.ctime),
    }
    
    save_user(user_data)
    
    # Log in user
    session["user_id"] = user_id
    session["ai_name"] = ai_name
    
    flash(f"Welcome! {ai_name} is ready to serve you.", "success")
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """User login page."""
    if request.method == "GET":
        return render_template("login.html")
    
    email = request.form.get("email", "").lower().strip()
    password = request.form.get("password", "")
    
    user = get_user(email)
    if not user:
        flash("No account found with this email.", "error")
        return redirect(url_for("login"))
    
    if not verify_password(password, user["password_hash"], user["password_salt"]):
        flash("Incorrect password.", "error")
        return redirect(url_for("login"))
    
    session["user_id"] = user["user_id"]
    session["ai_name"] = user["ai_name"]
    
    flash(f"Welcome back! {user['ai_name']} is online.", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    """Log out user."""
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    """User dashboard."""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_file = DATA_DIR / f"{session['user_id']}.json"
    user = json.loads(user_file.read_text()) if user_file.exists() else {}
    
    return render_template("dashboard.html", user=user, themes=THEMES, features=FEATURES)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    """User settings page."""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_file = DATA_DIR / f"{session['user_id']}.json"
    user = json.loads(user_file.read_text())
    
    if request.method == "POST":
        user["ai_name"] = request.form.get("ai_name", user["ai_name"])
        user["ai_theme"] = request.form.get("ai_theme", user["ai_theme"])
        user["features"] = request.form.getlist("features")
        
        save_user(user)
        session["ai_name"] = user["ai_name"]
        
        flash("Settings saved successfully.", "success")
        return redirect(url_for("settings"))
    
    return render_template("settings.html", user=user, themes=THEMES, features=FEATURES)


@app.route("/download-config")
def download_config():
    """Download config.yaml for user."""
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user_file = DATA_DIR / f"{session['user_id']}.json"
    user = json.loads(user_file.read_text())
    
    config = f"""# ASTRA Configuration - Generated for {user['email']}
app:
  name: "{user['ai_name']}"
  version: "2.0.0"
  wake_word: "{user['ai_name'].lower()}"
  user_id: "{user['user_id']}"
  theme: "{user['ai_theme']}"
  wake_mode: "always"

voice:
  stt_model: "base.en"
  stt_device: "cpu"
  language: "en"
  vad_aggressiveness: 2
  silence_threshold_ms: 800
  noise_cancel: false

tts:
  engine: "piper"
  piper_voice: "en_US-amy-medium"
  piper_length_scale: 1.0
  filler_sounds: true

llm:
  provider: "groq"
  model: "llama-3.3-70b-versatile"
  fallback_model: "phi3.5"
  temperature: 0.7
  stream: true

memory:
  chroma_path: "./data/chroma"
  top_k_results: 3

cloud:
  provider: "oracle"
  sync_enabled: true
  api_endpoint: "{request.host_url.rstrip('/')}/api"
  user_id: "{user['user_id']}"
"""
    
    from flask import Response
    return Response(
        config,
        mimetype="text/yaml",
        headers={"Content-Disposition": f"attachment;filename=config.yaml"}
    )


# API endpoints for desktop app
@app.route("/api/auth/check", methods=["POST"])
def api_auth_check():
    """API authentication check for desktop app."""
    data = request.json
    email = data.get("email", "").lower()
    password = data.get("password", "")
    
    user = get_user(email)
    if not user:
        return jsonify({"success": False, "error": "User not found"})
    
    if not verify_password(password, user["password_hash"], user["password_salt"]):
        return jsonify({"success": False, "error": "Invalid password"})
    
    return jsonify({
        "success": True,
        "user_id": user["user_id"],
        "ai_name": user["ai_name"],
        "ai_theme": user["ai_theme"],
        "features": user["features"],
    })


@app.route("/api/user/<user_id>/config")
def api_user_config(user_id):
    """Get user configuration for desktop app."""
    user_file = DATA_DIR / f"{user_id}.json"
    if not user_file.exists():
        return jsonify({"error": "User not found"}), 404
    
    user = json.loads(user_file.read_text())
    
    return jsonify({
        "ai_name": user["ai_name"],
        "ai_theme": user["ai_theme"],
        "features": user["features"],
        "wake_word": user["ai_name"].lower(),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
