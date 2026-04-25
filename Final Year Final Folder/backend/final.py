import os
import json
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
from keras.models import load_model
import logging
from werkzeug.utils import secure_filename
import hashlib
import re
from sqlalchemy import inspect, text
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Init app and config
load_dotenv()
app = Flask(__name__)
CORS(app)

app.config.update(
   SECRET_KEY=os.getenv('SECRET_KEY'),
   SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL'),
   SQLALCHEMY_TRACK_MODIFICATIONS=False,
   UPLOAD_FOLDER=os.getenv('UPLOAD_FOLDER', 'uploads'),
   AUDIO_FOLDER='audio',
   MODEL_PATH=os.getenv('MODEL_PATH', 'models/devanagari.h5'),
   JWT_EXPIRATION_HOURS=24,
   MAX_CONTENT_LENGTH=16 * 1024 * 1024
)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['AUDIO_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)

# Load model
try:
   model = load_model(app.config['MODEL_PATH'])
except Exception as e:
   model = None

letter_map = {
   0: 'CHECK', 1: 'क', 2: 'ख', 3: 'ग', 4: 'घ', 5: 'ङ', 6: 'च',
   7: 'छ', 8: 'ज', 9: 'झ', 10: 'ञ', 11: 'ट', 12: 'ठ', 13: 'ड',
   14: 'ढ', 15: 'ण', 16: 'त', 17: 'थ', 18: 'द', 19: 'ध', 20: 'न',
   21: 'प', 22: 'फ', 23: 'ब', 24: 'भ', 25: 'म', 26: 'य', 27: 'र',
   28: 'ल', 29: 'व', 30: 'श', 31: 'ष', 32: 'स', 33: 'ह',
   34: 'क्ष', 35: 'त्र', 36: 'ज्ञ'
}

SHA256_PATTERN = re.compile(r'^[a-f0-9]{64}$', re.IGNORECASE)
USER_ROLE = 'user'
ADMIN_ROLE = 'admin'


def is_strong_password(password):
   return isinstance(password, str) and len(password) >= 8


def normalize_password(password):
   if not isinstance(password, str):
       password = '' if password is None else str(password)
   candidate = password.strip()
   if not candidate:
       return ''
   if SHA256_PATTERN.fullmatch(candidate):
       return candidate.lower()
   return hashlib.sha256(candidate.encode('utf-8')).hexdigest()


def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


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
   ip_address = forwarded_for or real_ip or remote_ip or 'unknown'
   return f"IP:{ip_address}"


def ensure_user_role_column():
   inspector = inspect(db.engine)
   user_columns = {column['name'] for column in inspector.get_columns('users')}
   if 'role' in user_columns:
       return
   with db.engine.begin() as connection:
       connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"))


def ensure_prediction_location_column():
   inspector = inspect(db.engine)
   prediction_columns = {column['name'] for column in inspector.get_columns('prediction')}
   if 'processing_location' in prediction_columns:
       return
   with db.engine.begin() as connection:
       connection.execute(text("ALTER TABLE prediction ADD COLUMN processing_location VARCHAR(255)"))


def reverse_geocode_coordinates(latitude, longitude):
   query = urlencode({
       'lat': latitude,
       'lon': longitude,
       'format': 'jsonv2',
       'addressdetails': 1,
       'zoom': 18
   })
   request_obj = Request(
       f"https://nominatim.openstreetmap.org/reverse?{query}",
       headers={
           'User-Agent': 'DevanagariRecognitionSystem/1.0'
       }
   )

   try:
       with urlopen(request_obj, timeout=5) as response:
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
   except Exception:
       pass

   return f"{latitude}, {longitude}"


def resolve_signup_role(payload):
   requested_role = str(payload.get('role', USER_ROLE)).strip().lower()
   if requested_role != ADMIN_ROLE:
       return USER_ROLE

   configured_signup_key = str(os.getenv('ADMIN_SIGNUP_KEY', '')).strip()
   provided_signup_key = str(payload.get('admin_signup_key', '')).strip()
   if not configured_signup_key or configured_signup_key != provided_signup_key:
       return None

   return ADMIN_ROLE

# Models
class User(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   username = db.Column(db.String(50), unique=True, nullable=False)
   email = db.Column(db.String(120), unique=True, nullable=False)
   password = db.Column(db.String(255), nullable=False)
   role = db.Column(db.String(20), nullable=False, default=USER_ROLE)
   predictions = db.relationship('Prediction', backref='user', lazy=True)

   def to_dict(self):
       return {
           'id': self.id,
           'username': self.username,
           'email': self.email,
           'role': self.role
       }

class Prediction(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
   filename = db.Column(db.String(255), nullable=False) 
   prediction = db.Column(db.String(10), nullable=False)
   confidence = db.Column(db.Float, nullable=False)
    processing_location = db.Column(db.String(255), nullable=True)

with app.app_context():
   db.create_all()
    ensure_user_role_column()
    ensure_prediction_location_column()
    db.session.execute(text("UPDATE users SET role = 'user' WHERE role IS NULL OR role = ''"))
    db.session.commit()

# Auth decorator
def token_required(f):
   @wraps(f)
   def decorated(*args, **kwargs):
       auth_header = request.headers.get('Authorization', '')
       if not auth_header or not auth_header.startswith('Bearer '):
           return jsonify({'status': 'error', 'message': 'Invalid auth header'}), 401
           
       try:
           token = auth_header.split(' ')[1]
           data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
           current_user = User.query.get(data['user_id'])
           if not current_user:
               return jsonify({'status': 'error', 'message': 'User not found'}), 401
       except:
           return jsonify({'status': 'error', 'message': 'Invalid token'}), 401
           
       return f(current_user, *args, **kwargs)
   return decorated


def admin_required(f):
   @wraps(f)
   @token_required
   def decorated(current_user, *args, **kwargs):
       if current_user.role != ADMIN_ROLE:
           return jsonify({'status': 'error', 'message': 'Admin access required'}), 403
       return f(current_user, *args, **kwargs)
   return decorated

# Routes
@app.route('/api/signup', methods=['POST'])
def signup():
   try:
       data = request.get_json()
       
       if User.query.filter_by(email=data['email']).first():
           return jsonify({
               'status': 'error',
               'message': 'Email exists'
           }), 400

       raw_password = data.get('password', '')
       if not is_strong_password(raw_password):
           return jsonify({
               'status': 'error',
               'message': 'Password must be at least 8 characters long'
           }), 400
       normalized_password = normalize_password(raw_password)
       assigned_role = resolve_signup_role(data)
       if assigned_role is None:
           return jsonify({
               'status': 'error',
               'message': 'Invalid admin signup key'
           }), 403

       user = User(
           username=data['username'],
           email=data['email'],
           password=generate_password_hash(normalized_password),
           role=assigned_role
       )
       db.session.add(user)
       db.session.commit()
       
       return jsonify({
           'status': 'success',
           'message': 'User created'
       }), 201
       
   except Exception as e:
       return jsonify({
           'status': 'error',
           'message': str(e)
       }), 500

@app.route('/api/signin', methods=['POST'])
def signin():
   try:
       data = request.get_json()
       identifier = (data.get('identifier') or data.get('email') or data.get('username') or '').strip()
       if not identifier:
           return jsonify({
               'status': 'error',
               'message': 'Username/email is required'
           }), 400

       if is_valid_email(identifier):
           user = User.query.filter_by(email=identifier).first()
       else:
           user = User.query.filter_by(username=identifier).first()

       normalized_password = normalize_password(data.get('password', ''))
       
       if not user or not check_password_hash(user.password, normalized_password):
           return jsonify({
               'status': 'error',
               'message': 'Invalid credentials'
           }), 401

       if not user.role:
           user.role = USER_ROLE
           db.session.commit()
           
       token = jwt.encode({
           'user_id': user.id,
           'role': user.role,
           'exp': datetime.utcnow() + timedelta(hours=24)
       }, app.config['SECRET_KEY'])
       
       return jsonify({
           'status': 'success',
           'data': {'token': token, 'user': user.to_dict()}
       })
       
   except Exception as e:
       return jsonify({
           'status': 'error',
           'message': str(e)
       }), 500

@app.route('/api/predict', methods=['POST'])
@token_required 
def predict(current_user):
   if not model:
       return jsonify({'status': 'error', 'message': 'Model not loaded'}), 500
       
   if 'image' not in request.files:
       return jsonify({'status': 'error', 'message': 'No image'}), 400

   try:
       image_file = request.files['image']
       if not allowed_file(image_file.filename):
           return jsonify({'status': 'error', 'message': 'Invalid file type'}), 400

       # Process image
       nparr = np.frombuffer(image_file.read(), np.uint8)
       img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
       
       # Resize and preprocess
       img = cv2.resize(img, (32, 32))
       img = img.astype('float32') / 255
       img = np.expand_dims(img, axis=[0,3])

       # Predict
       pred = model.predict(img)[0]
       pred_class = np.argmax(pred)
       confidence = float(pred[pred_class])
       text = letter_map[pred_class]
    processing_location = get_processing_location()

       # Save prediction
       filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image_file.filename}")
       
       prediction = Prediction(
           user_id=current_user.id,
           filename=filename,
           prediction=text,
           confidence=confidence,
           processing_location=processing_location
       )
       db.session.add(prediction)
       db.session.commit()

       return jsonify({
           'status': 'success',
           'data': {
               'text': text,
               'location': processing_location,
               'characters': [{
                   'id': prediction.id,
                   'character': text,
                   'confidence': confidence,
                   'processing_location': processing_location
               }]
           }
       })

   except Exception as e:
       return jsonify({
           'status': 'error',
           'message': str(e)
       }), 500

@app.route('/api/generate-audio/<string:text>', methods=['GET'])
@token_required
def generate_audio(current_user, text):
   try:
       text = text.encode('utf-8').decode('unicode-escape')
       
       audio_file = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
       audio_path = os.path.join(app.config['AUDIO_FOLDER'], audio_file)
       
       tts = gTTS(text=text, lang='ne')
       tts.save(audio_path)
       
       response = send_file(
           audio_path,
           mimetype='audio/mpeg',
           as_attachment=True,
           download_name=audio_file
       )
       response.headers['Cache-Control'] = 'no-cache'
       return response

   except Exception as e:
       return jsonify({
           'status': 'error',
           'message': str(e)
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
   users = User.query.order_by(User.id.desc()).all()
   return jsonify({
       'status': 'success',
       'data': [
           {
               'id': user.id,
               'username': user.username,
               'email': user.email,
               'role': user.role,
               'prediction_count': Prediction.query.filter_by(user_id=user.id).count()
           }
           for user in users
       ]
   }), 200


@app.route('/api/admin/users/<int:user_id>/role', methods=['PUT'])
@admin_required
def update_user_role(current_user, user_id):
   data = request.get_json() or {}
   new_role = str(data.get('role', '')).strip().lower()
   if new_role not in {USER_ROLE, ADMIN_ROLE}:
       return jsonify({'status': 'error', 'message': 'Role must be user or admin'}), 400

   target_user = User.query.get(user_id)
   if not target_user:
       return jsonify({'status': 'error', 'message': 'User not found'}), 404

   if current_user.id == target_user.id and new_role != ADMIN_ROLE:
       return jsonify({'status': 'error', 'message': 'Cannot remove your own admin role'}), 400

   target_user.role = new_role
   db.session.commit()
   return jsonify({'status': 'success', 'message': 'Role updated'}), 200


@app.route('/api/admin/bootstrap', methods=['POST'])
def bootstrap_admin():
   try:
       data = request.get_json() or {}
       bootstrap_key = str(data.get('bootstrap_key', '')).strip()
       configured_key = str(os.getenv('ADMIN_BOOTSTRAP_KEY', '')).strip()

       if not configured_key or bootstrap_key != configured_key:
           return jsonify({
               'status': 'error',
               'message': 'Invalid bootstrap key'
           }), 403

       if User.query.filter_by(role=ADMIN_ROLE).first():
           return jsonify({
               'status': 'error',
               'message': 'An admin account already exists'
           }), 409

       identifier = str(data.get('identifier', '')).strip()
       if not identifier:
           return jsonify({
               'status': 'error',
               'message': 'Identifier is required'
           }), 400

       if is_valid_email(identifier):
           user = User.query.filter_by(email=identifier).first()
       else:
           user = User.query.filter_by(username=identifier).first()

       if not user:
           return jsonify({
               'status': 'error',
               'message': 'User not found'
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
       return jsonify({
           'status': 'error',
           'message': str(e)
       }), 500

if __name__ == '__main__':
   app.run(debug=True)