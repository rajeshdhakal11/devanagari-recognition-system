import os
import json
import secrets
import smtplib
import base64
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
import cv2
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import jwt
from gtts import gTTS
from keras.models import load_model #ignore
from scipy.signal import find_peaks
import logging
from logging.handlers import RotatingFileHandler
import re
import hashlib
from werkzeug.utils import secure_filename
from io import BytesIO
from collections import Counter, defaultdict
from sqlalchemy import inspect, text
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from email.message import EmailMessage

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# App Configuration
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY'),
    SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    UPLOAD_FOLDER=os.getenv('UPLOAD_FOLDER', 'uploads'),
    AUDIO_FOLDER='audio',
    MODEL_PATH=os.getenv('MODEL_PATH', 'models/devanagari.h5'),
    JWT_EXPIRATION_HOURS=int(os.getenv('JWT_EXPIRATION_HOURS', 24)),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024,
    SIGNUP_OTP_EXPIRATION_MINUTES=int(os.getenv('SIGNUP_OTP_EXPIRATION_MINUTES', 10)),
    SIGNUP_OTP_RESEND_COOLDOWN_SECONDS=int(os.getenv('SIGNUP_OTP_RESEND_COOLDOWN_SECONDS', 0)),
    LOW_CONFIDENCE_THRESHOLD=float(os.getenv('LOW_CONFIDENCE_THRESHOLD', 0.70)),
    FACE_MATCH_THRESHOLD=float(os.getenv('FACE_MATCH_THRESHOLD', 0.84)),
    UPLOADER_IMAGE_RETENTION_DAYS=int(os.getenv('UPLOADER_IMAGE_RETENTION_DAYS', 30)),
    ADMIN_ANALYTICS_LOOKBACK_DAYS=int(os.getenv('ADMIN_ANALYTICS_LOOKBACK_DAYS', 30))
)

# File upload configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Ensure required directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['AUDIO_FOLDER'], exist_ok=True)

# Initialize database
db = SQLAlchemy(app)

# Configure logging
if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/devanagari.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Devanagari Recognition startup')

# Load the model
try:
    model = load_model(app.config['MODEL_PATH'])
    app.logger.info('Model loaded successfully')
except Exception as e:
    app.logger.error(f'Error loading model: {str(e)}')
    model = None

# Character mapping
letter_map = {
    0: 'CHECK', 1: 'क', 2: 'ख', 3: 'ग', 4: 'घ', 5: 'ङ', 6: 'च',
    7: 'छ', 8: 'ज', 9: 'झ', 10: 'ञ', 11: 'ट', 12: 'ठ', 13: 'ड',
    14: 'ढ', 15: 'ण', 16: 'त', 17: 'थ', 18: 'द', 19: 'ध', 20: 'न',
    21: 'प', 22: 'फ', 23: 'ब', 24: 'भ', 25: 'म', 26: 'य', 27: 'र',
    28: 'ल', 29: 'व', 30: 'श', 31: 'ष', 32: 'स', 33: 'ह',
    34: 'क्ष', 35: 'त्र', 36: 'ज्ञ'
}

english_transliteration_map = {
    'CHECK': 'check',
    'क': 'ka',
    'ख': 'kha',
    'ग': 'ga',
    'घ': 'gha',
    'ङ': 'nga',
    'च': 'cha',
    'छ': 'chha',
    'ज': 'ja',
    'झ': 'jha',
    'ञ': 'nya',
    'ट': 'ta',
    'ठ': 'tha',
    'ड': 'da',
    'ढ': 'dha',
    'ण': 'na',
    'त': 'ta',
    'थ': 'tha',
    'द': 'da',
    'ध': 'dha',
    'न': 'na',
    'प': 'pa',
    'फ': 'pha',
    'ब': 'ba',
    'भ': 'bha',
    'म': 'ma',
    'य': 'ya',
    'र': 'ra',
    'ल': 'la',
    'व': 'wa',
    'श': 'sha',
    'ष': 'ssha',
    'स': 'sa',
    'ह': 'ha',
    'क्ष': 'ksha',
    'त्र': 'tra',
    'ज्ञ': 'gya'
}

character_to_class_map = {value: key for key, value in letter_map.items()}

# Basic writing guidance for commonly predicted Devanagari characters.
character_formation_map = {
    'क': [
        'Start with a short vertical stroke downward.',
        'Add the right-curving lower arm from the middle.',
        'Draw the horizontal headline across the top.'
    ],
    'ख': [
        'Draw the left vertical base stroke.',
        'Add the open curved right arm and lower extension.',
        'Finish with the top horizontal headline.'
    ],
    'ग': [
        'Make a curved open bowl shape on the right.',
        'Add a short downward tail at the lower end.',
        'Complete with the top horizontal headline.'
    ],
    'च': [
        'Create a downward curved stroke from left to right.',
        'Hook the lower end inward lightly.',
        'Add the top horizontal headline.'
    ],
    'ज': [
        'Begin with the main curved body stroke.',
        'Add a small inward hook in the lower section.',
        'Draw the top horizontal headline.'
    ],
    'त': [
        'Draw the central stem with a slight right curve.',
        'Add the lower finishing arm.',
        'Close with the top horizontal headline.'
    ],
    'द': [
        'Start with a right-facing curved body.',
        'Add the lower connecting stroke.',
        'Draw the horizontal headline on top.'
    ],
    'न': [
        'Make the left stem and curved right body.',
        'Connect the lower section smoothly.',
        'Finish with the horizontal headline.'
    ],
    'प': [
        'Draw a vertical base stroke.',
        'Add the rounded right loop/body.',
        'Complete with the top horizontal headline.'
    ],
    'म': [
        'Create the left and middle downward strokes.',
        'Add the right rounded closing stroke.',
        'Finish with the top horizontal headline.'
    ],
    'य': [
        'Draw the upper curved form first.',
        'Add the lower descending stroke.',
        'Complete with the top headline.'
    ],
    'र': [
        'Draw a short descending main stroke.',
        'Add a slight rightward tail/curve.',
        'Finish with the top horizontal headline.'
    ],
    'ल': [
        'Start with a descending curved stem.',
        'Add the lower loop/turn.',
        'Close with the top headline.'
    ],
    'व': [
        'Draw the initial curved left-to-right stroke.',
        'Add the lower inward hook.',
        'Finish with the top horizontal headline.'
    ],
    'श': [
        'Build the left and middle downward strokes.',
        'Add the right curved component.',
        'Draw the top horizontal headline.'
    ],
    'स': [
        'Create the main rounded body.',
        'Add the lower inward finishing hook.',
        'Complete with the top horizontal headline.'
    ],
    'ह': [
        'Draw the left main descending stroke.',
        'Add the right curved companion stroke.',
        'Finish with the top horizontal headline.'
    ]
}


def build_character_formation_guide(predictions):
    unique_characters = []
    for char in predictions:
        if char not in unique_characters:
            unique_characters.append(char)

    guide = []
    for char in unique_characters:
        if char in character_formation_map:
            steps = character_formation_map[char]
        else:
            steps = [
                'Draw the base character shape with balanced proportions.',
                'Refine the curves/hooks specific to this letter.',
                'Add the horizontal headline (shirorekha) last.'
            ]
        guide.append({
            'character': char,
            'steps': steps
        })

    return guide


def get_character_class_number(character):
    class_number = character_to_class_map.get(character)
    if class_number is None:
        return None
    if class_number == 0:
        return None
    return int(class_number)


def transliterate_character(character):
    return english_transliteration_map.get(character, character)


def transliterate_prediction_tokens(tokens):
    if not tokens:
        return ''
    return ' '.join(transliterate_character(token) for token in tokens if token)


def is_low_confidence_score(confidence):
    threshold = float(app.config.get('LOW_CONFIDENCE_THRESHOLD', 0.70))
    return float(confidence) < threshold

# Validation helpers
USER_ROLE = 'user'
ADMIN_ROLE = 'admin'


def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def normalize_phone_number(phone_number):
    if not phone_number:
        return ''
    cleaned = re.sub(r'[^0-9+]', '', str(phone_number).strip())
    if cleaned.startswith('00'):
        cleaned = '+' + cleaned[2:]
    return cleaned


def is_valid_phone_number(phone_number):
    candidate = normalize_phone_number(phone_number)
    return bool(re.fullmatch(r'^\+?[0-9]{7,15}$', candidate))


def build_internal_email_from_phone(phone_number):
    digits = re.sub(r'\D', '', normalize_phone_number(phone_number))
    if not digits:
        digits = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    return f"mobile{digits}@local.signup"

def is_strong_password(password):
    return len(password) >= 8


SHA256_PATTERN = re.compile(r'^[a-f0-9]{64}$', re.IGNORECASE)


def normalize_password(password):
    """Ensure incoming password is hashed consistently before storage/checks."""
    if not isinstance(password, str):
        password = '' if password is None else str(password)
    candidate = password.strip()
    if not candidate:
        return ''
    if SHA256_PATTERN.fullmatch(candidate):
        return candidate.lower()
    return hashlib.sha256(candidate.encode('utf-8')).hexdigest()


def sanitize_username_source(value):
    """Normalize names to lowercase alphanumeric chunks for username generation."""
    if not value:
        return ''
    return re.sub(r'[^a-z0-9]', '', value.lower())

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def ensure_user_role_column():
    """Add role column for existing databases that predate role support."""
    inspector = inspect(db.engine)
    user_columns = {column['name'] for column in inspector.get_columns('users')}
    if 'role' in user_columns:
        return

    with db.engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"))


def ensure_user_phone_column():
    """Add phone_number column for existing databases."""
    inspector = inspect(db.engine)
    user_columns = {column['name'] for column in inspector.get_columns('users')}
    if 'phone_number' in user_columns:
        return

    with db.engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN phone_number VARCHAR(20)"))


def ensure_user_face_columns():
    """Add face authentication columns for existing databases."""
    inspector = inspect(db.engine)
    user_columns = {column['name'] for column in inspector.get_columns('users')}

    statements = []
    if 'face_embedding' not in user_columns:
        statements.append("ALTER TABLE users ADD COLUMN face_embedding TEXT")
    if 'face_login_enabled' not in user_columns:
        statements.append("ALTER TABLE users ADD COLUMN face_login_enabled BOOLEAN NOT NULL DEFAULT FALSE")

    if not statements:
        return

    with db.engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def ensure_prediction_location_column():
    """Add processing_location column for existing databases."""
    inspector = inspect(db.engine)
    prediction_columns = {column['name'] for column in inspector.get_columns('predictions')}
    if 'processing_location' in prediction_columns:
        return

    with db.engine.begin() as connection:
        connection.execute(text("ALTER TABLE predictions ADD COLUMN processing_location VARCHAR(255)"))


def ensure_signup_otp_phone_column():
    """Add phone_number column for existing signup OTP records."""
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if 'signup_otps' not in tables:
        return

    otp_columns = {column['name'] for column in inspector.get_columns('signup_otps')}
    if 'phone_number' in otp_columns:
        return

    with db.engine.begin() as connection:
        connection.execute(text("ALTER TABLE signup_otps ADD COLUMN phone_number VARCHAR(20)"))


def ensure_scan_image_uploader_columns():
    """Add uploader image columns for existing scan image records."""
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if 'scan_images' not in tables:
        return

    scan_image_columns = {column['name'] for column in inspector.get_columns('scan_images')}

    statements = []
    if 'uploader_mime_type' not in scan_image_columns:
        statements.append("ALTER TABLE scan_images ADD COLUMN uploader_mime_type VARCHAR(50)")
    if 'uploader_image_data' not in scan_image_columns:
        statements.append("ALTER TABLE scan_images ADD COLUMN uploader_image_data BYTEA")

    if not statements:
        return

    with db.engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def reverse_geocode_coordinates(latitude, longitude):
    """Resolve latitude/longitude to a readable address when possible."""
    query = urlencode({
        'lat': latitude,
        'lon': longitude,
        'format': 'jsonv2',
        'addressdetails': 1,
        'zoom': 18
    })
    request = Request(
        f"https://nominatim.openstreetmap.org/reverse?{query}",
        headers={
            'User-Agent': 'DevanagariRecognitionSystem/1.0'
        }
    )

    try:
        with urlopen(request, timeout=5) as response:
            payload = response.read().decode('utf-8')
        data = json.loads(payload)
        address = data.get('address') or {}

        street_parts = [
            address.get('house_number'),
            address.get('road') or address.get('pedestrian') or address.get('street')
        ]
        locality_parts = [
            address.get('suburb') or address.get('neighbourhood') or address.get('hamlet'),
            address.get('city') or address.get('town') or address.get('village') or address.get('county'),
            address.get('state')
        ]

        concise_parts = [part.strip() for part in street_parts + locality_parts if part and str(part).strip()]
        if concise_parts:
            return ', '.join(dict.fromkeys(concise_parts))

        display_name = (data.get('display_name') or '').strip()
        if display_name:
            return ', '.join(segment.strip() for segment in display_name.split(',')[:4] if segment.strip())
    except Exception as exc:
        app.logger.warning(f'Unable to reverse geocode coordinates: {exc}')

    return f"{latitude}, {longitude}"


def get_processing_location():
    explicit_location = (request.form.get('location') or '').strip()
    latitude = (request.form.get('latitude') or '').strip()
    longitude = (request.form.get('longitude') or '').strip()

    if latitude and longitude:
        return reverse_geocode_coordinates(latitude, longitude)

    if explicit_location:
        return explicit_location

    forwarded_for = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    real_ip = (request.headers.get('X-Real-IP') or '').strip()
    remote_ip = (request.remote_addr or '').strip()
    ip_address = forwarded_for or real_ip or remote_ip or ''
    if not ip_address:
        return 'Location unavailable'

    if ip_address in {'127.0.0.1', '::1', 'localhost'}:
        return 'Local device (localhost)'

    return f"IP:{ip_address}"


def find_user_by_identifier(identifier):
    candidate = (identifier or '').strip()
    if not candidate:
        return None
    if is_valid_email(candidate):
        return User.query.filter_by(email=candidate.lower()).first()
    return User.query.filter_by(username=candidate).first()


def create_auth_token(user):
    return jwt.encode({
        'user_id': user.id,
        'role': user.role,
        'exp': datetime.utcnow() + timedelta(hours=app.config['JWT_EXPIRATION_HOURS'])
    }, app.config['SECRET_KEY'])


def decode_image_payload_to_bytes(image_payload):
    if not image_payload:
        return None

    if isinstance(image_payload, bytes):
        return image_payload

    candidate = str(image_payload).strip()
    if not candidate:
        return None

    if ',' in candidate and 'base64' in candidate[:40].lower():
        candidate = candidate.split(',', 1)[1]

    try:
        return base64.b64decode(candidate)
    except Exception:
        return None


def extract_face_embedding(image_bytes):
    if not image_bytes:
        return None, 'Face image is empty'

    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        return None, 'Unable to decode face image'

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(64, 64))

    if len(faces) == 0:
        return None, 'No face detected. Use a clear front-facing image.'

    # Use the largest detected face to avoid background detections.
    x, y, w, h = max(faces, key=lambda item: item[2] * item[3])
    face_region = gray[y:y + h, x:x + w]
    face_region = cv2.resize(face_region, (64, 64), interpolation=cv2.INTER_AREA)
    face_region = cv2.equalizeHist(face_region)

    vector = (face_region.astype(np.float32) / 255.0).flatten()
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-8:
        return None, 'Face embedding generation failed'

    vector = vector / norm
    return vector.tolist(), None


def deserialize_face_embedding(embedding_text):
    if not embedding_text:
        return None

    try:
        values = json.loads(embedding_text)
        if not isinstance(values, list) or not values:
            return None
        return np.array(values, dtype=np.float32)
    except Exception:
        return None


def calculate_face_similarity(embedding_a, embedding_b):
    if embedding_a is None or embedding_b is None:
        return 0.0

    if embedding_a.shape != embedding_b.shape:
        return 0.0

    return float(np.dot(embedding_a, embedding_b))

# Database Models
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), unique=True, nullable=True)
    date_of_birth = db.Column(db.Date, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=USER_ROLE)
    face_embedding = db.Column(db.Text, nullable=True)
    face_login_enabled = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    predictions = db.relationship('Prediction', backref='user', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'username': self.username,
            'email': self.email,
            'phone_number': self.phone_number,
            'role': self.role,
            'face_login_enabled': bool(self.face_login_enabled and self.face_embedding),
            'date_of_birth': self.date_of_birth.isoformat(),
            'created_at': self.created_at.isoformat()
        }

class Prediction(db.Model):
    __tablename__ = 'predictions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    prediction = db.Column(db.String(10), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    processing_location = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'prediction': self.prediction,
            'confidence': self.confidence,
            'processing_location': self.processing_location,
            'created_at': self.created_at.isoformat()
        }


class ScanImage(db.Model):
    __tablename__ = 'scan_images'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), unique=True, nullable=False)
    mime_type = db.Column(db.String(50), default='application/octet-stream')
    image_data = db.Column(db.LargeBinary, nullable=False)
    uploader_mime_type = db.Column(db.String(50), nullable=True)
    uploader_image_data = db.Column(db.LargeBinary, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'filename': self.filename,
            'mime_type': self.mime_type,
            'uploader_mime_type': self.uploader_mime_type,
            'created_at': self.created_at.isoformat()
        }


class SignupOTP(db.Model):
    __tablename__ = 'signup_otps'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    phone_number = db.Column(db.String(20), nullable=True, index=True)
    otp_hash = db.Column(db.String(64), nullable=False)
    attempts = db.Column(db.Integer, default=0)
    verified = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def serialize_history(predictions, available_images=None, available_uploader_images=None):
    """Create grouped history entries from prediction rows."""
    history_map = {}
    order = []
    available_images = available_images or set()
    available_uploader_images = available_uploader_images or set()

    for pred in predictions:
        entry = history_map.get(pred.filename)
        if not entry:
            entry = {
                'filename': pred.filename,
                'created_at': pred.created_at,
                'processing_location': pred.processing_location,
                'characters': []
            }
            history_map[pred.filename] = entry
            order.append(pred.filename)

        if not entry.get('processing_location') and pred.processing_location:
            entry['processing_location'] = pred.processing_location

        entry['characters'].append({
            'id': pred.id,
            'character': pred.prediction,
            'confidence': float(pred.confidence),
            'class_number': get_character_class_number(pred.prediction),
            'is_low_confidence': is_low_confidence_score(pred.confidence)
        })

    history_entries = [history_map[filename] for filename in order]
    for entry in history_entries:
        entry['text'] = ''.join(char['character'] for char in entry['characters'])
        entry['english_text'] = transliterate_prediction_tokens([
            char['character'] for char in entry['characters']
        ])

    history_entries.sort(key=lambda item: item['created_at'], reverse=True)

    serialized = []
    for entry in history_entries:
        serialized.append({
            'filename': entry['filename'],
            'created_at': entry['created_at'].isoformat(),
            'characters': entry['characters'],
            'text': entry['text'],
            'english_text': entry['english_text'],
            'processing_location': entry.get('processing_location'),
            'image_available': entry['filename'] in available_images,
            'uploader_image_available': entry['filename'] in available_uploader_images
        })

    return serialized

# Create tables
with app.app_context():
    db.create_all()
    ensure_user_role_column()
    ensure_user_phone_column()
    ensure_user_face_columns()
    ensure_prediction_location_column()
    ensure_signup_otp_phone_column()
    ensure_scan_image_uploader_columns()
    db.session.execute(text("UPDATE users SET role = 'user' WHERE role IS NULL OR role = ''"))
    db.session.execute(text("UPDATE users SET face_login_enabled = FALSE WHERE face_login_enabled IS NULL"))
    db.session.execute(text("UPDATE predictions SET processing_location = 'Legacy record (location unavailable)' WHERE processing_location IS NULL OR processing_location = ''"))
    retention_days = max(0, int(app.config.get('UPLOADER_IMAGE_RETENTION_DAYS', 30)))
    if retention_days > 0:
        retention_cutoff = datetime.utcnow() - timedelta(days=retention_days)
        purged_rows = (ScanImage.query
            .filter(
                ScanImage.uploader_image_data.isnot(None),
                ScanImage.created_at < retention_cutoff
            )
            .update({
                ScanImage.uploader_image_data: None,
                ScanImage.uploader_mime_type: None
            }, synchronize_session=False))
        if purged_rows:
            app.logger.info('Purged uploader photos older than %s days: %s', retention_days, purged_rows)
    db.session.commit()
    app.logger.info('Database tables created')

# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({
                'status': 'error',
                'message': 'Invalid Authorization header format',
                'code': 'INVALID_AUTH_HEADER'
            }), 401
            
        try:
            token = auth_header.split(' ')[1]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            
            if not current_user:
                return jsonify({
                    'status': 'error',
                    'message': 'User not found',
                    'code': 'USER_NOT_FOUND'
                }), 401
                
        except jwt.ExpiredSignatureError:
            return jsonify({
                'status': 'error',
                'message': 'Token has expired',
                'code': 'TOKEN_EXPIRED'
            }), 401
        except (jwt.InvalidTokenError, IndexError):
            return jsonify({
                'status': 'error',
                'message': 'Invalid token',
                'code': 'INVALID_TOKEN'
            }), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated


def admin_required(f):
    @wraps(f)
    @token_required
    def decorated(current_user, *args, **kwargs):
        if current_user.role != ADMIN_ROLE:
            return jsonify({
                'status': 'error',
                'message': 'Admin access required',
                'code': 'ADMIN_REQUIRED'
            }), 403

        return f(current_user, *args, **kwargs)

    return decorated


def resolve_signup_role(payload):
    requested_role = str(payload.get('role', USER_ROLE)).strip().lower()
    if requested_role != ADMIN_ROLE:
        return USER_ROLE

    configured_signup_key = str(os.getenv('ADMIN_SIGNUP_KEY', '')).strip()
    provided_signup_key = str(payload.get('admin_signup_key', '')).strip()

    if not configured_signup_key or configured_signup_key != provided_signup_key:
        return None

    return ADMIN_ROLE


def hash_signup_otp(otp_code):
    return hashlib.sha256(str(otp_code).encode('utf-8')).hexdigest()


def generate_signup_otp_code():
    return f"{secrets.randbelow(1000000):06d}"


def send_signup_otp_email(recipient_email, otp_code):
    smtp_host = os.getenv('SMTP_HOST', '').strip()
    smtp_port = int(os.getenv('SMTP_PORT', 587))
    smtp_username = os.getenv('SMTP_USERNAME', '').strip()
    smtp_password = os.getenv('SMTP_PASSWORD', '').strip()
    smtp_use_tls = str(os.getenv('SMTP_USE_TLS', 'true')).strip().lower() != 'false'
    from_email = os.getenv('SMTP_FROM_EMAIL', smtp_username or 'no-reply@example.com').strip()

    if not smtp_host or not smtp_username or not smtp_password:
        return False, 'SMTP email settings are not configured'

    message = EmailMessage()
    message['Subject'] = 'Your Devanagari Signup OTP Code'
    message['From'] = from_email
    message['To'] = recipient_email
    message.set_content(
        f"Your signup verification code is: {otp_code}\n\n"
        f"This code will expire in {app.config['SIGNUP_OTP_EXPIRATION_MINUTES']} minutes."
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
            if smtp_use_tls:
                smtp.starttls()
            smtp.login(smtp_username, smtp_password)
            smtp.send_message(message)
        return True, None
    except Exception as exc:
        app.logger.error(f'Failed to send signup OTP email: {exc}')
        return False, 'Unable to send OTP email right now'


def send_signup_otp_sms(recipient_phone, otp_code):
    def env_first(*names):
        for name in names:
            value = os.getenv(name, '').strip()
            if value:
                return value
        return ''

    twilio_sid = env_first('TWILIO_ACCOUNT_SID')
    twilio_token = env_first('TWILIO_AUTH_TOKEN')
    twilio_from = env_first('TWILIO_FROM_NUMBER', 'TWILIO_PHONE_NUMBER')
    twilio_service_sid = env_first('TWILIO_MESSAGING_SERVICE_SID')

    missing = []
    if not twilio_sid:
        missing.append('TWILIO_ACCOUNT_SID')
    if not twilio_token:
        missing.append('TWILIO_AUTH_TOKEN')
    if not twilio_from and not twilio_service_sid:
        missing.append('TWILIO_FROM_NUMBER or TWILIO_MESSAGING_SERVICE_SID')

    if missing:
        app.logger.warning('Missing Twilio SMS settings: %s', ', '.join(missing))
        return False, 'SMS provider settings are not configured'

    sms_payload = {
        'To': recipient_phone,
        'Body': (
            f"Your Devanagari signup OTP is {otp_code}. "
            f"It expires in {app.config['SIGNUP_OTP_EXPIRATION_MINUTES']} minutes."
        )
    }
    if twilio_service_sid:
        sms_payload['MessagingServiceSid'] = twilio_service_sid
    else:
        sms_payload['From'] = twilio_from

    payload = urlencode(sms_payload).encode('utf-8')

    auth_token = base64.b64encode(f"{twilio_sid}:{twilio_token}".encode('utf-8')).decode('utf-8')
    request_obj = Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
        data=payload,
        method='POST',
        headers={
            'Authorization': f"Basic {auth_token}",
            'Content-Type': 'application/x-www-form-urlencoded'
        }
    )

    try:
        with urlopen(request_obj, timeout=10) as response:
            _ = response.read()
        return True, None
    except Exception as exc:
        app.logger.error(f'Failed to send signup OTP SMS: {exc}')
        return False, 'Unable to send OTP SMS right now'

# Routes
@app.route('/api/signup/request-otp', methods=['POST'])
def request_signup_otp():
    try:
        data = request.get_json() or {}
        phone_number = normalize_phone_number(data.get('phone_number'))

        if not phone_number:
            return jsonify({
                'status': 'error',
                'message': 'Phone number is required',
                'code': 'MISSING_PHONE_NUMBER'
            }), 400

        if phone_number and not is_valid_phone_number(phone_number):
            return jsonify({
                'status': 'error',
                'message': 'Invalid phone number format',
                'code': 'INVALID_PHONE_NUMBER'
            }), 400

        latest = SignupOTP.query.filter_by(phone_number=phone_number).order_by(SignupOTP.created_at.desc()).first()

        resend_cooldown_seconds = max(0, app.config.get('SIGNUP_OTP_RESEND_COOLDOWN_SECONDS', 0))
        if latest and resend_cooldown_seconds > 0 and (datetime.utcnow() - latest.created_at).total_seconds() < resend_cooldown_seconds:
            return jsonify({
                'status': 'error',
                'message': 'Please wait before requesting another OTP',
                'code': 'OTP_RATE_LIMIT'
            }), 429

        otp_code = generate_signup_otp_code()
        otp_record = SignupOTP(
            email='',
            phone_number=phone_number,
            otp_hash=hash_signup_otp(otp_code),
            attempts=0,
            verified=False,
            expires_at=datetime.utcnow() + timedelta(minutes=app.config['SIGNUP_OTP_EXPIRATION_MINUTES'])
        )

        db.session.add(otp_record)
        db.session.commit()

        delivery_channel = None
        sent = False
        send_error = None

        if phone_number:
            sent, send_error = send_signup_otp_sms(phone_number, otp_code)
            if sent:
                delivery_channel = 'mobile number'

        if not sent:
            allow_dev_fallback = (
                str(os.getenv('OTP_ALLOW_DEV_FALLBACK', '')).strip().lower() in {'1', 'true', 'yes'}
                or app.debug
                or str(os.getenv('FLASK_ENV', '')).strip().lower() == 'development'
            )

            if allow_dev_fallback:
                app.logger.warning(
                    'OTP provider unavailable. Using development fallback for contact %s',
                    phone_number
                )
                return jsonify({
                    'status': 'success',
                    'message': 'OTP generated in development mode (provider not configured)',
                    'data': {
                        'delivery_channel': 'development-fallback',
                        'dev_otp': otp_code
                    }
                }), 200

            db.session.delete(otp_record)
            db.session.commit()
            return jsonify({
                'status': 'error',
                'message': send_error or 'Unable to send OTP SMS right now',
                'code': 'OTP_SEND_FAILED'
            }), 500

        return jsonify({
            'status': 'success',
            'message': f'OTP sent to your {delivery_channel}'
        }), 200

    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error requesting signup OTP: {e}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'code': 'SERVER_ERROR'
        }), 500


@app.route('/api/signup/verify-otp', methods=['POST'])
def verify_signup_otp():
    try:
        data = request.get_json() or {}
        phone_number = normalize_phone_number(data.get('phone_number'))
        otp = (data.get('otp') or '').strip()

        if not phone_number or not otp:
            return jsonify({
                'status': 'error',
                'message': 'Phone number and OTP are required',
                'code': 'MISSING_OTP_DATA'
            }), 400

        if phone_number and not is_valid_phone_number(phone_number):
            return jsonify({
                'status': 'error',
                'message': 'Invalid phone number format',
                'code': 'INVALID_PHONE_NUMBER'
            }), 400

        otp_record = SignupOTP.query.filter_by(phone_number=phone_number).order_by(SignupOTP.created_at.desc()).first()

        if not otp_record or otp_record.verified:
            return jsonify({
                'status': 'error',
                'message': 'No pending OTP request found',
                'code': 'OTP_NOT_FOUND'
            }), 404

        if otp_record.expires_at < datetime.utcnow():
            return jsonify({
                'status': 'error',
                'message': 'OTP has expired',
                'code': 'OTP_EXPIRED'
            }), 400

        if otp_record.attempts >= 5:
            return jsonify({
                'status': 'error',
                'message': 'Too many invalid attempts. Request a new OTP',
                'code': 'OTP_ATTEMPTS_EXCEEDED'
            }), 400

        if otp_record.otp_hash != hash_signup_otp(otp):
            otp_record.attempts += 1
            db.session.commit()
            return jsonify({
                'status': 'error',
                'message': 'Invalid OTP',
                'code': 'INVALID_OTP'
            }), 400

        otp_record.verified = True
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'OTP verified successfully'
        }), 200

    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error verifying signup OTP: {e}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'code': 'SERVER_ERROR'
        }), 500


@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'username', 
                 'password', 'date_of_birth', 'email']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}',
                    'code': 'MISSING_FIELD'
                }), 400

        email_value = (data.get('email') or '').strip().lower()
        if not is_valid_email(email_value):
            return jsonify({
                'status': 'error',
                'message': 'Invalid email format',
                'code': 'INVALID_EMAIL'
            }), 400

        normalized_phone_number = normalize_phone_number(data.get('phone_number'))
        if normalized_phone_number and not is_valid_phone_number(normalized_phone_number):
            return jsonify({
                'status': 'error',
                'message': 'Invalid phone number format',
                'code': 'INVALID_PHONE_NUMBER'
            }), 400

        # Validate password strength using raw input
        raw_password = data['password']
        if not is_strong_password(raw_password):
            return jsonify({
                'status': 'error',
                'message': 'Password must be at least 8 characters long',
                'code': 'WEAK_PASSWORD'
            }), 400
        normalized_password = normalize_password(raw_password)

        # Check existing username/email
        if User.query.filter_by(username=data['username']).first():
            return jsonify({
                'status': 'error',
                'message': 'Username already exists',
                'code': 'USERNAME_EXISTS'
            }), 400
        if User.query.filter_by(email=email_value).first():
            return jsonify({
                'status': 'error',
                'message': 'Email already exists',
                'code': 'EMAIL_EXISTS'
            }), 400
        if User.query.filter_by(phone_number=normalized_phone_number).first():
            return jsonify({
                'status': 'error',
                'message': 'Phone number already exists. Please sign in instead.',
                'code': 'PHONE_EXISTS'
            }), 400
        
        assigned_role = resolve_signup_role(data)
        if assigned_role is None:
            return jsonify({
                'status': 'error',
                'message': 'Invalid admin signup key',
                'code': 'INVALID_ADMIN_SIGNUP_KEY'
            }), 403

        otp_record = (SignupOTP.query
            .filter_by(phone_number=normalized_phone_number, verified=True)
            .order_by(SignupOTP.created_at.desc())
            .first())

        if not otp_record or otp_record.expires_at < datetime.utcnow():
            return jsonify({
                'status': 'error',
                'message': 'Please verify OTP before creating account',
                'code': 'OTP_VERIFICATION_REQUIRED'
            }), 400

        face_embedding_payload = None
        face_login_enabled = False
        if data.get('face_image'):
            face_image_bytes = decode_image_payload_to_bytes(data.get('face_image'))
            face_vector, face_error = extract_face_embedding(face_image_bytes)
            if face_error:
                return jsonify({
                    'status': 'error',
                    'message': face_error,
                    'code': 'FACE_ENROLLMENT_FAILED'
                }), 400
            face_embedding_payload = json.dumps(face_vector)
            face_login_enabled = True

        # Create new user
        new_user = User(
            first_name=data['first_name'],
            last_name=data['last_name'],
            username=data['username'],
            email=email_value,
            phone_number=normalized_phone_number,
            date_of_birth=datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date(),
            password=generate_password_hash(normalized_password),
            role=assigned_role,
            face_embedding=face_embedding_payload,
            face_login_enabled=face_login_enabled
        )
        
        db.session.add(new_user)
        db.session.commit()

        SignupOTP.query.filter_by(phone_number=normalized_phone_number).delete()
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'User created successfully',
            'data': new_user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error in signup: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'code': 'SERVER_ERROR'
        }), 500

@app.route('/api/signin', methods=['POST'])
def signin():
    try:
        data = request.get_json()

        identifier = (data.get('identifier') or data.get('email') or data.get('username') or '').strip()
        password_input = data.get('password')

        if not identifier or not password_input:
            return jsonify({
                'status': 'error',
                'message': 'Username/email and password are required',
                'code': 'MISSING_CREDENTIALS'
            }), 400

        user = find_user_by_identifier(identifier)

        normalized_password = normalize_password(password_input)
        
        if not user or not check_password_hash(user.password, normalized_password):
            return jsonify({
                'status': 'error',
                'message': 'Invalid username/email or password',
                'code': 'INVALID_CREDENTIALS'
            }), 401

        if not user.role:
            user.role = USER_ROLE
            db.session.commit()
            
        token = create_auth_token(user)
        
        return jsonify({
            'status': 'success',
            'data': {
                'token': token,
                'user': user.to_dict()
            }
        }), 200
        
    except Exception as e:
        app.logger.error(f'Error in signin: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'code': 'SERVER_ERROR'
        }), 500


@app.route('/api/face/setup', methods=['POST'])
def setup_face_login():
    try:
        data = request.get_json() or {}
        identifier = (data.get('identifier') or '').strip()
        password_input = data.get('password')
        image_bytes = decode_image_payload_to_bytes(data.get('image'))

        if not identifier or not password_input or not image_bytes:
            return jsonify({
                'status': 'error',
                'message': 'Identifier, password, and face image are required',
                'code': 'MISSING_FACE_SETUP_DATA'
            }), 400

        user = find_user_by_identifier(identifier)
        normalized_password = normalize_password(password_input)
        if not user or not check_password_hash(user.password, normalized_password):
            return jsonify({
                'status': 'error',
                'message': 'Invalid username/email or password',
                'code': 'INVALID_CREDENTIALS'
            }), 401

        face_vector, face_error = extract_face_embedding(image_bytes)
        if face_error:
            return jsonify({
                'status': 'error',
                'message': face_error,
                'code': 'FACE_ENROLLMENT_FAILED'
            }), 400

        user.face_embedding = json.dumps(face_vector)
        user.face_login_enabled = True
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Face login enabled successfully',
            'data': {
                'face_login_enabled': True
            }
        }), 200

    except Exception as exc:
        db.session.rollback()
        app.logger.error(f'Error in face setup: {exc}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'code': 'SERVER_ERROR'
        }), 500


@app.route('/api/face/enroll', methods=['POST'])
@token_required
def enroll_face_login(current_user):
    try:
        data = request.get_json() or {}
        image_bytes = decode_image_payload_to_bytes(data.get('image'))

        if not image_bytes:
            return jsonify({
                'status': 'error',
                'message': 'Face image is required',
                'code': 'MISSING_FACE_IMAGE'
            }), 400

        face_vector, face_error = extract_face_embedding(image_bytes)
        if face_error:
            return jsonify({
                'status': 'error',
                'message': face_error,
                'code': 'FACE_ENROLLMENT_FAILED'
            }), 400

        current_user.face_embedding = json.dumps(face_vector)
        current_user.face_login_enabled = True
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Face login enrolled successfully',
            'data': {
                'face_login_enabled': True
            }
        }), 200

    except Exception as exc:
        db.session.rollback()
        app.logger.error(f'Error in face enrollment: {exc}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'code': 'SERVER_ERROR'
        }), 500


@app.route('/api/face/signin', methods=['POST'])
def signin_with_face():
    try:
        data = request.get_json() or {}
        identifier = (data.get('identifier') or '').strip()
        image_bytes = decode_image_payload_to_bytes(data.get('image'))

        if not identifier or not image_bytes:
            return jsonify({
                'status': 'error',
                'message': 'Identifier and face image are required',
                'code': 'MISSING_FACE_SIGNIN_DATA'
            }), 400

        user = find_user_by_identifier(identifier)
        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found',
                'code': 'USER_NOT_FOUND'
            }), 404

        if not user.face_login_enabled or not user.face_embedding:
            return jsonify({
                'status': 'error',
                'message': 'Face login is not set up for this account',
                'code': 'FACE_NOT_ENROLLED'
            }), 400

        probe_vector, face_error = extract_face_embedding(image_bytes)
        if face_error:
            return jsonify({
                'status': 'error',
                'message': face_error,
                'code': 'FACE_EXTRACTION_FAILED'
            }), 400

        enrolled_embedding = deserialize_face_embedding(user.face_embedding)
        probe_embedding = np.array(probe_vector, dtype=np.float32)
        similarity = calculate_face_similarity(enrolled_embedding, probe_embedding)
        threshold = float(app.config.get('FACE_MATCH_THRESHOLD', 0.84))

        if similarity < threshold:
            return jsonify({
                'status': 'error',
                'message': 'Face does not match this account',
                'code': 'FACE_MISMATCH',
                'data': {
                    'similarity': round(similarity, 4),
                    'threshold': threshold
                }
            }), 401

        if not user.role:
            user.role = USER_ROLE
            db.session.commit()

        token = create_auth_token(user)

        return jsonify({
            'status': 'success',
            'data': {
                'token': token,
                'user': user.to_dict(),
                'face_similarity': round(similarity, 4)
            }
        }), 200

    except Exception as exc:
        app.logger.error(f'Error in face signin: {exc}')
        return jsonify({
            'status': 'error',
            'message': 'Internal server error',
            'code': 'SERVER_ERROR'
        }), 500


@app.route('/api/username-suggestions', methods=['GET'])
def username_suggestions():
    try:
        first_name = request.args.get('first_name', '').strip()
        last_name = request.args.get('last_name', '').strip()

        if not first_name or not last_name:
            return jsonify({
                'status': 'error',
                'message': 'First name and last name are required',
                'code': 'MISSING_NAME_DATA'
            }), 400

        base_first = sanitize_username_source(first_name) or 'user'
        base_last = sanitize_username_source(last_name) or 'member'

        candidate_pool = []
        combos = [
            f"{base_first}{base_last}",
            f"{base_first}.{base_last}",
            f"{base_first}_{base_last}",
            f"{base_first}{base_last[:1]}",
            f"{base_first[:1]}{base_last}",
            base_first,
        ]

        seen = set()
        for candidate in combos:
            if candidate and candidate not in seen:
                candidate_pool.append(candidate)
                seen.add(candidate)

        for i in range(1, 100):
            candidate = f"{base_first}{base_last}{i}"
            if candidate not in seen:
                candidate_pool.append(candidate)
                seen.add(candidate)

        suggestions = []
        for candidate in candidate_pool:
            if not User.query.filter(User.username.ilike(candidate)).first():
                suggestions.append(candidate)
            if len(suggestions) == 5:
                break

        if not suggestions:
            fallback = f"{base_first}{datetime.utcnow().strftime('%f')}"
            suggestions.append(fallback)

        return jsonify({
            'status': 'success',
            'data': {
                'suggestions': suggestions
            }
        }), 200

    except Exception as exc:
        app.logger.error(f'Error generating username suggestions: {exc}')
        return jsonify({
            'status': 'error',
            'message': 'Unable to generate username suggestions',
            'code': 'USERNAME_SUGGEST_ERROR'
        }), 500

@app.route('/api/predict', methods=['POST'])
@token_required
def predict(current_user):
    if not model:
        return jsonify({
            'status': 'error',
            'message': 'Model not loaded',
            'code': 'MODEL_NOT_LOADED'
        }), 500
        
    if 'image' not in request.files:
        return jsonify({
            'status': 'error',
            'message': 'No image file provided',
            'code': 'NO_IMAGE'
        }), 400
        
    try:
        image_file = request.files['image']
        
        if image_file.filename == '':
            return jsonify({
                'status': 'error',
                'message': 'No selected file',
                'code': 'NO_FILE_SELECTED'
            }), 400
            
        if not allowed_file(image_file.filename):
            return jsonify({
                'status': 'error',
                'message': 'Invalid file type',
                'code': 'INVALID_FILE_TYPE'
            }), 400
        
        uploader_file = request.files.get('uploader_image')
        uploader_image_consent = str(request.form.get('uploader_image_consent', '')).strip().lower()
        uploader_image_data = None
        uploader_mime_type = None

        if uploader_file and uploader_file.filename:
            if not allowed_file(uploader_file.filename):
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid uploader image type',
                    'code': 'INVALID_UPLOADER_IMAGE_TYPE'
                }), 400
            uploader_image_data = uploader_file.read()
            if not uploader_image_data:
                return jsonify({
                    'status': 'error',
                    'message': 'Uploader image is empty',
                    'code': 'EMPTY_UPLOADER_IMAGE'
                }), 400
            if uploader_image_consent not in {'1', 'true', 'yes', 'on'}:
                return jsonify({
                    'status': 'error',
                    'message': 'Consent is required to upload person photo',
                    'code': 'MISSING_UPLOADER_IMAGE_CONSENT'
                }), 400
            uploader_mime_type = uploader_file.mimetype or 'application/octet-stream'

        # Read image data first
        image_data = image_file.read()
        
        # Process and get predictions
        segments = process_image(image_data)
        
        if not segments:
            return jsonify({
                'status': 'error',
                'message': 'No characters detected in the image',
                'code': 'NO_CHARACTERS_DETECTED'
            }), 400
        
        # Get predictions
        predictions, confidences, class_numbers, top_predictions = predict_segments(segments)
        processing_location = get_processing_location()
        
        # Save file after successful processing
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image_file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(filepath, 'wb') as f:
            f.write(image_data)
        
        # Store image bytes in database for preview
        scan_image = ScanImage.query.filter_by(user_id=current_user.id, filename=filename).first()
        if scan_image:
            scan_image.image_data = image_data
            scan_image.mime_type = image_file.mimetype or 'application/octet-stream'
            scan_image.uploader_image_data = uploader_image_data
            scan_image.uploader_mime_type = uploader_mime_type
            scan_image.created_at = datetime.now()
        else:
            scan_image = ScanImage(
                user_id=current_user.id,
                filename=filename,
                mime_type=image_file.mimetype or 'application/octet-stream',
                image_data=image_data,
                uploader_mime_type=uploader_mime_type,
                uploader_image_data=uploader_image_data
            )
            db.session.add(scan_image)

        formation_guide = build_character_formation_guide(predictions)
        english_text = transliterate_prediction_tokens(predictions)

        # Save predictions to database
        saved_predictions = []
        for pred, conf in zip(predictions, confidences):
            prediction = Prediction(
                user_id=current_user.id,
                filename=filename,
                prediction=pred,
                confidence=conf,
                processing_location=processing_location
            )
            db.session.add(prediction)
            saved_predictions.append(prediction)

        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'data': {
                'text': ''.join(predictions),
                'english_text': english_text,
                'location': processing_location,
                'formation_guide': formation_guide,
                'uploader_image_uploaded': bool(uploader_image_data),
                'characters': [{
                    'id': pred.id,
                    'character': pred.prediction,
                    'english_label': transliterate_character(pred.prediction),
                    'confidence': pred.confidence,
                    'class_number': class_number,
                    'is_low_confidence': is_low_confidence_score(pred.confidence),
                    'top_predictions': candidate_list,
                    'processing_location': pred.processing_location
                } for pred, class_number, candidate_list in zip(saved_predictions, class_numbers, top_predictions)]
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error in prediction: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Error processing image',
            'code': 'PROCESSING_ERROR'
        }), 500

@app.route('/api/generate-audio', methods=['POST'])
@token_required
def generate_audio(current_user):
    filepath = None
    try:
        data = request.get_json()
        if not data or not data.get('text'):
            return jsonify({
                'status': 'error',
                'message': 'No text provided',
                'code': 'NO_TEXT'
            }), 400

        text = data['text']
        language = str(data.get('language', 'ne')).strip().lower()
        tts_language = 'en' if language == 'en' else 'ne'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_prefix = secure_filename(text) or 'audio'
        filename = f"{safe_prefix}_{tts_language}_{timestamp}.mp3"
        filepath = os.path.join(app.config['AUDIO_FOLDER'], filename)
        
        # Find existing file without timestamp
        existing_files = [f for f in os.listdir(app.config['AUDIO_FOLDER']) 
                         if f.startswith(f"{safe_prefix}_{tts_language}_") and f.endswith('.mp3')]
        
        if existing_files:
            existing_file = os.path.join(app.config['AUDIO_FOLDER'], existing_files[0])
            return send_file(
                existing_file,
                mimetype='audio/mpeg',
                as_attachment=True,
                download_name=existing_files[0]
            )
            
        tts = gTTS(text=text, lang=tts_language)
        tts.save(filepath)
        
        return send_file(
            filepath,
            mimetype='audio/mpeg',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        app.logger.error(f'Error generating audio: {str(e)}')
        if filepath and os.path.exists(filepath):
            os.remove(filepath)  # Clean up partial file if there was an error
        return jsonify({
            'status': 'error',
            'message': 'Error generating audio',
            'code': 'AUDIO_GENERATION_ERROR'
        }), 500

@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    return jsonify({
        'status': 'success',
        'data': current_user.to_dict()
    }), 200


@app.route('/api/admin/users', methods=['GET'])
@admin_required
def list_users_for_admin(current_user):
    try:
        users = User.query.order_by(User.created_at.desc()).all()
        data = []
        for user in users:
            prediction_count = Prediction.query.filter_by(user_id=user.id).count()
            item = user.to_dict()
            item['prediction_count'] = prediction_count
            data.append(item)

        return jsonify({
            'status': 'success',
            'data': data
        }), 200

    except Exception as e:
        app.logger.error(f'Error listing users for admin: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Error retrieving users',
            'code': 'ADMIN_USERS_ERROR'
        }), 500


@app.route('/api/admin/users/<int:user_id>/role', methods=['PUT'])
@admin_required
def update_user_role(current_user, user_id):
    try:
        data = request.get_json() or {}
        new_role = str(data.get('role', '')).strip().lower()

        if new_role not in {USER_ROLE, ADMIN_ROLE}:
            return jsonify({
                'status': 'error',
                'message': 'Role must be user or admin',
                'code': 'INVALID_ROLE'
            }), 400

        target_user = User.query.get(user_id)
        if not target_user:
            return jsonify({
                'status': 'error',
                'message': 'User not found',
                'code': 'USER_NOT_FOUND'
            }), 404

        if current_user.id == target_user.id and new_role != ADMIN_ROLE:
            return jsonify({
                'status': 'error',
                'message': 'Cannot remove your own admin role',
                'code': 'SELF_ROLE_CHANGE_BLOCKED'
            }), 400

        target_user.role = new_role
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Role updated successfully',
            'data': target_user.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error updating user role: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Error updating user role',
            'code': 'ADMIN_ROLE_UPDATE_ERROR'
        }), 500


@app.route('/api/admin/bootstrap', methods=['POST'])
def bootstrap_admin():
    try:
        data = request.get_json() or {}
        bootstrap_key = str(data.get('bootstrap_key', '')).strip()
        configured_key = str(os.getenv('ADMIN_BOOTSTRAP_KEY', '')).strip()

        if not configured_key or bootstrap_key != configured_key:
            return jsonify({
                'status': 'error',
                'message': 'Invalid bootstrap key',
                'code': 'INVALID_BOOTSTRAP_KEY'
            }), 403

        if User.query.filter_by(role=ADMIN_ROLE).first():
            return jsonify({
                'status': 'error',
                'message': 'An admin account already exists',
                'code': 'ADMIN_ALREADY_EXISTS'
            }), 409

        identifier = str(data.get('identifier', '')).strip()
        if not identifier:
            return jsonify({
                'status': 'error',
                'message': 'Identifier is required',
                'code': 'MISSING_IDENTIFIER'
            }), 400

        if is_valid_email(identifier):
            user = User.query.filter_by(email=identifier).first()
        else:
            user = User.query.filter_by(username=identifier).first()

        if not user:
            return jsonify({
                'status': 'error',
                'message': 'User not found',
                'code': 'USER_NOT_FOUND'
            }), 404

        user.role = ADMIN_ROLE
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Admin role assigned successfully',
            'data': user.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error bootstrapping admin: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Error bootstrapping admin account',
            'code': 'ADMIN_BOOTSTRAP_ERROR'
        }), 500


@app.route('/api/admin/analytics/prediction-quality', methods=['GET'])
@admin_required
def get_admin_prediction_quality(current_user):
    try:
        lookback_days = max(1, int(request.args.get('lookback_days') or app.config.get('ADMIN_ANALYTICS_LOOKBACK_DAYS', 30)))
        threshold = float(request.args.get('threshold') or app.config.get('LOW_CONFIDENCE_THRESHOLD', 0.70))
        threshold = min(max(threshold, 0.0), 1.0)

        cutoff = datetime.utcnow() - timedelta(days=lookback_days)
        predictions = (Prediction.query
            .filter(Prediction.created_at >= cutoff)
            .order_by(Prediction.created_at.desc())
            .all())

        total_predictions = len(predictions)
        low_confidence_predictions = [pred for pred in predictions if float(pred.confidence) < threshold]
        low_confidence_count = len(low_confidence_predictions)
        low_confidence_rate = round((low_confidence_count / total_predictions) * 100, 2) if total_predictions else 0.0

        low_conf_char_counter = Counter(pred.prediction for pred in low_confidence_predictions)
        low_conf_by_character = [
            {
                'character': char,
                'count': count
            }
            for char, count in low_conf_char_counter.most_common(10)
        ]

        users = User.query.all()
        user_map = {user.id: user for user in users}
        user_low_conf_counter = Counter(pred.user_id for pred in low_confidence_predictions)
        user_total_counter = Counter(pred.user_id for pred in predictions)

        user_risk_summary = []
        for user_id, low_count in user_low_conf_counter.items():
            total_count = user_total_counter.get(user_id, 0)
            user_obj = user_map.get(user_id)
            user_risk_summary.append({
                'user_id': user_id,
                'username': user_obj.username if user_obj else f'user-{user_id}',
                'email': user_obj.email if user_obj else None,
                'low_confidence_count': low_count,
                'total_predictions': total_count,
                'low_confidence_rate': round((low_count / total_count) * 100, 2) if total_count else 0.0
            })

        user_risk_summary.sort(key=lambda item: (item['low_confidence_count'], item['low_confidence_rate']), reverse=True)

        return jsonify({
            'status': 'success',
            'data': {
                'lookback_days': lookback_days,
                'threshold': threshold,
                'total_predictions': total_predictions,
                'low_confidence_count': low_confidence_count,
                'low_confidence_rate': low_confidence_rate,
                'low_confidence_by_character': low_conf_by_character,
                'user_risk_summary': user_risk_summary[:10],
                'notes': 'Low-confidence data is a proxy signal for potential misclassifications.'
            }
        }), 200
    except Exception as e:
        app.logger.error(f'Error fetching admin prediction quality analytics: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Error retrieving admin analytics',
            'code': 'ADMIN_ANALYTICS_ERROR'
        }), 500

@app.route('/api/user/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    try:
        data = request.get_json()
        
        # Validate input data
        if 'first_name' in data and (not data['first_name'] or len(data['first_name']) > 50):
            return jsonify({
                'status': 'error',
                'message': 'Invalid first name',
                'code': 'INVALID_FIRST_NAME'
            }), 400
            
        if 'last_name' in data and (not data['last_name'] or len(data['last_name']) > 50):
            return jsonify({
                'status': 'error',
                'message': 'Invalid last name',
                'code': 'INVALID_LAST_NAME'
            }), 400
            
        if 'date_of_birth' in data:
            try:
                date_of_birth = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
                if date_of_birth > datetime.now().date():
                    raise ValueError('Future date not allowed')
            except ValueError:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid date of birth',
                    'code': 'INVALID_DATE'
                }), 400
        
        # Update allowed fields
        allowed_fields = ['first_name', 'last_name', 'date_of_birth']
        for field in allowed_fields:
            if field in data:
                if field == 'date_of_birth':
                    setattr(current_user, field, 
                           datetime.strptime(data[field], '%Y-%m-%d').date())
                else:
                    setattr(current_user, field, data[field])
        
        db.session.commit()
        return jsonify({
            'status': 'success',
            'data': current_user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error updating profile: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Error updating profile',
            'code': 'PROFILE_UPDATE_ERROR'
        }), 500


@app.route('/api/history', methods=['GET'])
@token_required
def get_history(current_user):
    try:
        predictions = (Prediction.query
                        .filter_by(user_id=current_user.id)
                        .order_by(Prediction.created_at.asc())
                        .all())

        image_filenames = {
            image.filename for image in ScanImage.query
                .filter_by(user_id=current_user.id)
                .all()
        }

        uploader_image_filenames = {
            image.filename for image in ScanImage.query
                .filter(
                    ScanImage.user_id == current_user.id,
                    ScanImage.uploader_image_data.isnot(None)
                )
                .all()
        }

        history_entries = serialize_history(predictions, image_filenames, uploader_image_filenames)

        return jsonify({
            'status': 'success',
            'data': history_entries
        }), 200

    except Exception as e:
        app.logger.error(f'Error fetching history: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Error retrieving history',
            'code': 'HISTORY_ERROR'
        }), 500


@app.route('/api/insights', methods=['GET'])
@token_required
def get_insights(current_user):
    try:
        predictions = (Prediction.query
                        .filter_by(user_id=current_user.id)
                        .order_by(Prediction.created_at.asc())
                        .all())

        image_filenames = {
            image.filename for image in ScanImage.query
                .filter_by(user_id=current_user.id)
                .all()
        }

        uploader_image_filenames = {
            image.filename for image in ScanImage.query
                .filter(
                    ScanImage.user_id == current_user.id,
                    ScanImage.uploader_image_data.isnot(None)
                )
                .all()
        }

        history_entries = serialize_history(predictions, image_filenames, uploader_image_filenames)

        char_counter = Counter()
        date_counter = defaultdict(int)
        total_confidence = 0.0

        for pred in predictions:
            char_counter[pred.prediction] += 1
            total_confidence += pred.confidence
            date_key = pred.created_at.date().isoformat()
            date_counter[date_key] += 1

        total_characters = len(predictions)
        average_confidence = round(total_confidence / total_characters, 4) if total_characters else 0
        top_characters = [
            {'character': char, 'english_label': transliterate_character(char), 'count': count}
            for char, count in char_counter.most_common(5)
        ]

        today = datetime.now().date()
        activity = []
        for days_ago in range(6, -1, -1):
            day = today - timedelta(days=days_ago)
            date_str = day.isoformat()
            activity.append({
                'date': date_str,
                'count': date_counter.get(date_str, 0)
            })

        recent_texts = [{
            'text': entry['text'],
            'english_text': entry.get('english_text', ''),
            'created_at': entry['created_at']
        } for entry in history_entries[:5]]

        confidence_distribution = [
            {'label': '90-100%', 'count': 0},
            {'label': '75-89%', 'count': 0},
            {'label': '60-74%', 'count': 0},
            {'label': 'Below 60%', 'count': 0}
        ]

        for pred in predictions:
            confidence_pct = pred.confidence * 100
            if confidence_pct >= 90:
                confidence_distribution[0]['count'] += 1
            elif confidence_pct >= 75:
                confidence_distribution[1]['count'] += 1
            elif confidence_pct >= 60:
                confidence_distribution[2]['count'] += 1
            else:
                confidence_distribution[3]['count'] += 1

        accuracy_trend = []
        recent_history = list(reversed(history_entries[:7]))
        for index, entry in enumerate(recent_history, start=1):
            characters = entry.get('characters') or []
            if characters:
                avg_confidence = sum(character['confidence'] for character in characters) / len(characters)
            else:
                avg_confidence = 0

            accuracy_trend.append({
                'label': f"Scan {index}",
                'created_at': entry['created_at'],
                'value': round(avg_confidence * 100, 1),
                'text': entry.get('text') or '—',
                'english_text': entry.get('english_text') or '—'
            })

        data = {
            'total_scans': len(history_entries),
            'total_characters': total_characters,
            'average_confidence': average_confidence,
            'last_scan_at': history_entries[0]['created_at'] if history_entries else None,
            'top_characters': top_characters,
            'activity': activity,
            'recent_texts': recent_texts,
            'accuracy_trend': accuracy_trend,
            'confidence_distribution': confidence_distribution
        }

        return jsonify({
            'status': 'success',
            'data': data
        }), 200

    except Exception as e:
        app.logger.error(f'Error fetching insights: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Error retrieving insights',
            'code': 'INSIGHTS_ERROR'
        }), 500


@app.route('/api/history/<path:filename>/image', methods=['GET'])
@token_required
def get_history_image(current_user, filename):
    try:
        scan_image = ScanImage.query.filter_by(user_id=current_user.id, filename=filename).first()

        if not scan_image:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    data = f.read()
                buffer = BytesIO(data)
                return send_file(
                    buffer,
                    mimetype='image/png',
                    as_attachment=False,
                    download_name=filename
                )
            return jsonify({
                'status': 'error',
                'message': 'Image not found',
                'code': 'IMAGE_NOT_FOUND'
            }), 404

        buffer = BytesIO(scan_image.image_data)
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype=scan_image.mime_type,
            as_attachment=False,
            download_name=scan_image.filename
        )

    except Exception as e:
        app.logger.error(f'Error fetching image preview: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Error retrieving image',
            'code': 'IMAGE_ERROR'
        }), 500


@app.route('/api/history/<path:filename>/uploader-image', methods=['GET'])
@token_required
def get_history_uploader_image(current_user, filename):
    try:
        scan_image = ScanImage.query.filter_by(user_id=current_user.id, filename=filename).first()

        if not scan_image or not scan_image.uploader_image_data:
            return jsonify({
                'status': 'error',
                'message': 'Uploader image not found',
                'code': 'UPLOADER_IMAGE_NOT_FOUND'
            }), 404

        buffer = BytesIO(scan_image.uploader_image_data)
        buffer.seek(0)
        return send_file(
            buffer,
            mimetype=scan_image.uploader_mime_type or 'application/octet-stream',
            as_attachment=False,
            download_name=f"uploader_{scan_image.filename}"
        )

    except Exception as e:
        app.logger.error(f'Error fetching uploader image preview: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Error retrieving uploader image',
            'code': 'UPLOADER_IMAGE_ERROR'
        }), 500


# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        'status': 'error',
        'message': 'Resource not found',
        'code': 'NOT_FOUND'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    app.logger.error(f'Server Error: {str(error)}')
    return jsonify({
        'status': 'error',
        'message': 'Internal server error',
        'code': 'SERVER_ERROR'
    }), 500

# Image processing functions
def remove_header_line(img):
    """Remove a strong shirorekha only when it spans most of the image width."""
    height, width = img.shape
    if height == 0 or width == 0:
        return img

    # Convert row projection from pixel sum to foreground coverage ratio.
    foreground = (img > 0).astype(np.uint8)
    row_coverage = np.mean(foreground, axis=1)
    upper_half = row_coverage[:max(1, height // 2)]
    header_position = int(np.argmax(upper_half))
    header_strength = float(upper_half[header_position])

    # Avoid removing regular strokes from isolated characters.
    if header_strength < 0.65:
        return img

    header_thickness = max(1, height // 20)
    cleaned = img.copy()
    cleaned[max(0, header_position - header_thickness):min(height, header_position + header_thickness + 1), :] = 0
    return cleaned

def get_connected_components(binary_img):
    """Get connected components with their bounding boxes and centroids."""
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_img, connectivity=8)
    stats = stats[1:]
    centroids = centroids[1:]
    img_area = max(1, binary_img.shape[0] * binary_img.shape[1])
    min_area = max(18, int(img_area * 0.00035))
    
    components = []
    for i, (stat, centroid) in enumerate(zip(stats, centroids)):
        x, y, w, h, area = stat
        if area >= min_area and w >= 2 and h >= 2:
            components.append({
                'label': i + 1,
                'x': x,
                'y': y,
                'w': w,
                'h': h,
                'area': area,
                'centroid': centroid
            })
    return components

def merge_components(components, img_width):
    """Merge components into character groups based on spatial relationships."""
    if not components:
        return []
        
    components = sorted(components, key=lambda c: c['x'])
    total_width = components[-1]['x'] + components[-1]['w'] - components[0]['x']
    avg_char_width = total_width / 3
    
    char_groups = []
    current_group = [components[0]]
    
    for i in range(1, len(components)):
        curr_comp = components[i]
        prev_comp = current_group[-1]
        distance = curr_comp['x'] - (prev_comp['x'] + prev_comp['w'])
        
        should_merge = (
            distance < avg_char_width * 0.3 or
            curr_comp['x'] < prev_comp['x'] + prev_comp['w'] or
            len(char_groups) == 2
        )
        
        if should_merge:
            current_group.append(curr_comp)
        else:
            char_groups.append(current_group)
            current_group = [curr_comp]
    
    char_groups.append(current_group)

    return char_groups

def extract_character_from_group(group, binary_img):
    """Extract character image from a group of components."""
    if not group:
        return None
        
    min_x = min(comp['x'] for comp in group)
    min_y = min(comp['y'] for comp in group)
    max_x = max(comp['x'] + comp['w'] for comp in group)
    max_y = max(comp['y'] + comp['h'] for comp in group)
    
    char_img = binary_img[min_y:max_y, min_x:max_x]
    
    padding = 5
    char_img = cv2.copyMakeBorder(
        char_img,
        padding, padding, padding, padding,
        cv2.BORDER_CONSTANT,
        value=0
    )
    
    return char_img

def extract_single_character_fallback(binary_img):
    """Fallback extractor for single-character drawings when component grouping is weak."""
    coords = cv2.findNonZero(binary_img)
    if coords is None:
        return []

    x, y, w, h = cv2.boundingRect(coords)
    if w < 2 or h < 2:
        return []

    char_img = binary_img[y:y + h, x:x + w]
    padding = max(4, int(round(max(w, h) * 0.1)))
    char_img = cv2.copyMakeBorder(
        char_img,
        padding,
        padding,
        padding,
        padding,
        cv2.BORDER_CONSTANT,
        value=0
    )
    return [char_img]

def process_image(image_data):
    """Process image data for prediction."""
    nparr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return []
    
    target_height = 150
    aspect_ratio = img.shape[1] / img.shape[0]
    target_width = int(target_height * aspect_ratio)
    img = cv2.resize(img, (target_width, target_height))
    
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    img = clahe.apply(img)
    
    _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    binary_no_header = remove_header_line(binary)
    
    kernel = np.ones((2,2), np.uint8)
    binary_clean = cv2.morphologyEx(binary_no_header, cv2.MORPH_CLOSE, kernel)
    binary_clean = cv2.morphologyEx(binary_clean, cv2.MORPH_OPEN, kernel)
    binary_clean = cv2.morphologyEx(binary_clean, cv2.MORPH_CLOSE, kernel)
    
    components = get_connected_components(binary_clean)
    char_groups = merge_components(components, binary_clean.shape[1])
    
    segments = []
    for group in char_groups:
        if group:
            char_img = extract_character_from_group(group, binary_clean)
            if char_img is not None:
                segments.append(char_img)

    # Keep left-to-right ordering and ignore tiny noisy segments.
    segments = [seg for seg in segments if seg.shape[0] * seg.shape[1] >= 49]

    # Fallback path for thin strokes / sparse drawings where grouping fails.
    if not segments:
        segments = extract_single_character_fallback(binary_clean)

    if not segments:
        segments = extract_single_character_fallback(binary_no_header)

    if not segments:
        segments = extract_single_character_fallback(binary)
    
    return segments

def process_segment(segment):
    """Process individual segment for prediction."""
    _, segment = cv2.threshold(segment, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Tight crop around foreground before resizing to avoid distortion.
    coords = cv2.findNonZero(segment)
    if coords is None:
        return np.zeros((1, 32, 32, 1), dtype=np.float32)

    x, y, w, h = cv2.boundingRect(coords)
    glyph = segment[y:y + h, x:x + w]

    canvas_size = 32
    inner_size = 24
    scale = min(inner_size / max(1, w), inner_size / max(1, h))
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))

    resized = cv2.resize(glyph, (new_w, new_h), interpolation=cv2.INTER_AREA)
    processed = np.zeros((canvas_size, canvas_size), dtype=np.uint8)
    x_offset = (canvas_size - new_w) // 2
    y_offset = (canvas_size - new_h) // 2
    processed[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized

    processed = processed.astype(np.float32) / 255.0
    processed = np.reshape(processed, (1, 32, 32, 1))
    return processed

def predict_segments(segments):
    """Predict characters from segments."""
    predictions = []
    confidences = []
    class_numbers = []
    top_predictions = []
    
    for segment in segments:
        processed = process_segment(segment)
        pred_probab = model.predict(processed)[0]
        pred_class = np.argmax(pred_probab)
        confidence = float(pred_probab[pred_class])

        top_indices = np.argsort(pred_probab)[-3:][::-1]
        candidates = []
        for top_idx in top_indices:
            class_idx = int(top_idx)
            candidates.append({
                'class_number': class_idx if class_idx != 0 else None,
                'character': letter_map.get(class_idx, 'UNKNOWN'),
                'confidence': float(pred_probab[class_idx])
            })
        
        predictions.append(letter_map[pred_class])
        confidences.append(confidence)
        class_numbers.append(int(pred_class) if int(pred_class) != 0 else None)
        top_predictions.append(candidates)
    
    return predictions, confidences, class_numbers, top_predictions

if __name__ == '__main__':
    app.run(
        debug=os.getenv('FLASK_ENV') == 'development',
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000))
    )