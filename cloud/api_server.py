"""
ASTRA Cloud API Server
Handles user authentication, model sync, and training coordination.
Deploy to Oracle Cloud / any cloud provider.
"""
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import os
import json
import hashlib
import secrets
import datetime
from pathlib import Path
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("ASTRA_SECRET_KEY", secrets.token_hex(32))
CORS(app)

# Data directories
DATA_DIR = Path(os.environ.get("ASTRA_DATA_DIR", "/data/astra"))
USERS_DIR = DATA_DIR / "users"
MODELS_DIR = DATA_DIR / "models"
TRAINING_DIR = DATA_DIR / "training"

for d in [USERS_DIR, MODELS_DIR, TRAINING_DIR]:
    d.mkdir(parents=True, exist_ok=True)


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


def token_required(f):
    """Decorator to require valid API token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({"error": "No token provided"}), 401
        
        # Verify token
        user_id = verify_token(token)
        if not user_id:
            return jsonify({"error": "Invalid token"}), 401
        
        return f(user_id, *args, **kwargs)
    return decorated


def generate_token(user_id: str) -> str:
    """Generate API token for user."""
    payload = f"{user_id}:{secrets.token_hex(16)}:{datetime.datetime.now().isoformat()}"
    token = hashlib.sha256(payload.encode()).hexdigest()
    
    # Store token
    tokens_file = DATA_DIR / "tokens.json"
    tokens = {}
    if tokens_file.exists():
        tokens = json.loads(tokens_file.read_text())
    tokens[token] = {
        "user_id": user_id,
        "created": datetime.datetime.now().isoformat(),
        "expires": (datetime.datetime.now() + datetime.timedelta(days=30)).isoformat()
    }
    tokens_file.write_text(json.dumps(tokens, indent=2))
    return token


def verify_token(token: str) -> str:
    """Verify token and return user_id."""
    tokens_file = DATA_DIR / "tokens.json"
    if not tokens_file.exists():
        return None
    tokens = json.loads(tokens_file.read_text())
    if token not in tokens:
        return None
    
    token_data = tokens[token]
    if datetime.datetime.fromisoformat(token_data["expires"]) < datetime.datetime.now():
        return None
    
    return token_data["user_id"]


# ============== User Registration & Auth ==============

@app.route("/api/register", methods=["POST"])
def register():
    """Register new user."""
    data = request.json
    
    required = ["email", "password", "ai_name", "ai_theme"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400
    
    email = data["email"].lower().strip()
    user_id = hashlib.md5(email.encode()).hexdigest()[:12]
    user_file = USERS_DIR / f"{user_id}.json"
    
    if user_file.exists():
        return jsonify({"error": "User already exists"}), 400
    
    # Hash password
    password_hash, salt = hash_password(data["password"])
    
    # Create user profile
    user_data = {
        "user_id": user_id,
        "email": email,
        "password_hash": password_hash,
        "password_salt": salt,
        "ai_name": data["ai_name"],
        "ai_theme": data["ai_theme"],
        "features": data.get("features", ["voice", "pc_control", "research"]),
        "created": datetime.datetime.now().isoformat(),
        "devices": [],
        "training_enabled": True,
    }
    
    user_file.write_text(json.dumps(user_data, indent=2))
    
    # Generate token
    token = generate_token(user_id)
    
    return jsonify({
        "success": True,
        "user_id": user_id,
        "token": token,
        "ai_name": data["ai_name"],
        "ai_theme": data["ai_theme"],
    })


@app.route("/api/login", methods=["POST"])
def login():
    """Login existing user."""
    data = request.json
    
    email = data.get("email", "").lower().strip()
    password = data.get("password", "")
    
    user_id = hashlib.md5(email.encode()).hexdigest()[:12]
    user_file = USERS_DIR / f"{user_id}.json"
    
    if not user_file.exists():
        return jsonify({"error": "User not found"}), 404
    
    user_data = json.loads(user_file.read_text())
    
    if not verify_password(password, user_data["password_hash"], user_data["password_salt"]):
        return jsonify({"error": "Invalid password"}), 401
    
    # Generate new token
    token = generate_token(user_id)
    
    return jsonify({
        "success": True,
        "user_id": user_id,
        "token": token,
        "ai_name": user_data["ai_name"],
        "ai_theme": user_data["ai_theme"],
        "features": user_data["features"],
    })


@app.route("/api/profile", methods=["GET"])
@token_required
def get_profile(user_id):
    """Get user profile."""
    user_file = USERS_DIR / f"{user_id}.json"
    if not user_file.exists():
        return jsonify({"error": "User not found"}), 404
    
    user_data = json.loads(user_file.read_text())
    # Don't return sensitive fields
    safe_data = {k: v for k, v in user_data.items() 
                 if k not in ["password_hash", "password_salt"]}
    return jsonify(safe_data)


@app.route("/api/profile", methods=["PUT"])
@token_required
def update_profile(user_id):
    """Update user profile."""
    user_file = USERS_DIR / f"{user_id}.json"
    if not user_file.exists():
        return jsonify({"error": "User not found"}), 404
    
    user_data = json.loads(user_file.read_text())
    data = request.json
    
    # Update allowed fields
    for field in ["ai_name", "ai_theme", "features"]:
        if field in data:
            user_data[field] = data[field]
    
    user_data["updated"] = datetime.datetime.now().isoformat()
    user_file.write_text(json.dumps(user_data, indent=2))
    
    return jsonify({"success": True})


# ============== Device Sync ==============

@app.route("/api/devices/register", methods=["POST"])
@token_required
def register_device(user_id):
    """Register a new device for user."""
    data = request.json
    device_id = data.get("device_id", secrets.token_hex(8))
    device_name = data.get("device_name", "Unknown Device")
    
    user_file = USERS_DIR / f"{user_id}.json"
    user_data = json.loads(user_file.read_text())
    
    device_info = {
        "device_id": device_id,
        "name": device_name,
        "registered": datetime.datetime.now().isoformat(),
        "last_sync": datetime.datetime.now().isoformat(),
    }
    
    # Update or add device
    devices = user_data.get("devices", [])
    existing = [d for d in devices if d["device_id"] == device_id]
    if existing:
        existing[0].update(device_info)
    else:
        devices.append(device_info)
    
    user_data["devices"] = devices
    user_file.write_text(json.dumps(user_data, indent=2))
    
    return jsonify({"success": True, "device_id": device_id})


# ============== Memory Sync ==============

@app.route("/api/memory/upload", methods=["POST"])
@token_required
def upload_memory(user_id):
    """Upload memory/training data from device."""
    data = request.json
    device_id = data.get("device_id", "unknown")
    memory_data = data.get("memory", {})
    
    # Save to user's training directory
    user_train_dir = TRAINING_DIR / user_id
    user_train_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    memory_file = user_train_dir / f"memory_{device_id}_{timestamp}.json"
    memory_file.write_text(json.dumps(memory_data, indent=2))
    
    return jsonify({"success": True, "file": str(memory_file.name)})


@app.route("/api/memory/download", methods=["GET"])
@token_required
def download_memory(user_id):
    """Download aggregated memory for user."""
    user_train_dir = TRAINING_DIR / user_id
    
    if not user_train_dir.exists():
        return jsonify({"memory": {}, "sessions": [], "knowledge": []})
    
    # Aggregate all memory files
    sessions = []
    knowledge = []
    
    for f in user_train_dir.glob("memory_*.json"):
        try:
            data = json.loads(f.read_text())
            sessions.extend(data.get("sessions", []))
            knowledge.extend(data.get("knowledge", []))
        except Exception:
            continue
    
    return jsonify({
        "sessions": sessions[-1000:],  # Last 1000 sessions
        "knowledge": knowledge,
    })


# ============== Model Management ==============

@app.route("/api/models/list", methods=["GET"])
@token_required
def list_models(user_id):
    """List available models for user."""
    user_models_dir = MODELS_DIR / user_id
    
    models = []
    if user_models_dir.exists():
        for f in user_models_dir.glob("*.json"):
            try:
                model_info = json.loads(f.read_text())
                models.append(model_info)
            except Exception:
                continue
    
    return jsonify({"models": models})


@app.route("/api/models/upload", methods=["POST"])
@token_required
def upload_model(user_id):
    """Upload trained model adapter."""
    if "model" not in request.files:
        return jsonify({"error": "No model file"}), 400
    
    model_file = request.files["model"]
    model_name = request.form.get("name", "adapter")
    version = request.form.get("version", "1")
    
    user_models_dir = MODELS_DIR / user_id
    user_models_dir.mkdir(exist_ok=True)
    
    # Save model file
    filename = f"{model_name}_v{version}.zip"
    model_path = user_models_dir / filename
    model_file.save(model_path)
    
    # Save metadata
    meta_path = user_models_dir / f"{model_name}_v{version}.json"
    meta_path.write_text(json.dumps({
        "name": model_name,
        "version": version,
        "filename": filename,
        "uploaded": datetime.datetime.now().isoformat(),
        "size": model_path.stat().st_size,
    }, indent=2))
    
    return jsonify({"success": True, "filename": filename})


# ============== Training Coordination ==============

@app.route("/api/training/status", methods=["GET"])
@token_required
def training_status(user_id):
    """Get training status for user."""
    status_file = TRAINING_DIR / user_id / "status.json"
    
    if not status_file.exists():
        return jsonify({
            "status": "idle",
            "last_trained": None,
            "next_scheduled": None,
        })
    
    return jsonify(json.loads(status_file.read_text()))


@app.route("/api/training/trigger", methods=["POST"])
@token_required
def trigger_training(user_id):
    """Trigger training job for user (Kaggle GPU/TPU)."""
    user_train_dir = TRAINING_DIR / user_id
    user_train_dir.mkdir(exist_ok=True)
    
    # Queue training job
    job_file = user_train_dir / "pending_job.json"
    job_file.write_text(json.dumps({
        "user_id": user_id,
        "requested": datetime.datetime.now().isoformat(),
        "status": "queued",
    }, indent=2))
    
    return jsonify({
        "success": True,
        "message": "Training job queued. Will run on next available GPU slot.",
    })


# ============== Config Sync ==============

@app.route("/api/config", methods=["GET"])
@token_required
def get_config(user_id):
    """Get user's ASTRA configuration."""
    user_file = USERS_DIR / f"{user_id}.json"
    user_data = json.loads(user_file.read_text())
    
    config = {
        "app": {
            "name": user_data["ai_name"],
            "wake_word": user_data["ai_name"].lower(),
            "theme": user_data["ai_theme"],
            "user_id": user_id,
        },
        "features": user_data.get("features", []),
        "cloud": {
            "sync_enabled": True,
            "api_endpoint": request.host_url.rstrip("/"),
        }
    }
    
    return jsonify(config)


# ============== Health Check ==============

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "version": "2.0.0"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
