import os
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
from scipy.signal import find_peaks
import logging
from logging.handlers import RotatingFileHandler
import re
from werkzeug.utils import secure_filename

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
    MAX_CONTENT_LENGTH=16 * 1024 * 1024  # 16MB max file size
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

# Validation helpers
def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def is_strong_password(password):
    return len(password) >= 8

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database Models
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    predictions = db.relationship('Prediction', backref='user', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'username': self.username,
            'email': self.email,
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'prediction': self.prediction,
            'confidence': self.confidence,
            'created_at': self.created_at.isoformat()
        }

# Create tables
with app.app_context():
    db.create_all()
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

# Routes
@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['first_name', 'last_name', 'username', 'email', 
                         'password', 'date_of_birth']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'status': 'error',
                    'message': f'Missing required field: {field}',
                    'code': 'MISSING_FIELD'
                }), 400

        # Validate email format
        if not is_valid_email(data['email']):
            return jsonify({
                'status': 'error',
                'message': 'Invalid email format',
                'code': 'INVALID_EMAIL'
            }), 400

        # Validate password strength
        if not is_strong_password(data['password']):
            return jsonify({
                'status': 'error',
                'message': 'Password must be at least 8 characters long',
                'code': 'WEAK_PASSWORD'
            }), 400

        # Check existing username/email
        if User.query.filter_by(username=data['username']).first():
            return jsonify({
                'status': 'error',
                'message': 'Username already exists',
                'code': 'USERNAME_EXISTS'
            }), 400
        if User.query.filter_by(email=data['email']).first():
            return jsonify({
                'status': 'error',
                'message': 'Email already exists',
                'code': 'EMAIL_EXISTS'
            }), 400
        
        # Create new user
        new_user = User(
            first_name=data['first_name'],
            last_name=data['last_name'],
            username=data['username'],
            email=data['email'],
            date_of_birth=datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date(),
            password=generate_password_hash(data['password'])
        )
        
        db.session.add(new_user)
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
        
        if not data.get('email') or not data.get('password'):
            return jsonify({
                'status': 'error',
                'message': 'Email and password are required',
                'code': 'MISSING_CREDENTIALS'
            }), 400
            
        user = User.query.filter_by(email=data['email']).first()
        
        if not user or not check_password_hash(user.password, data['password']):
            return jsonify({
                'status': 'error',
                'message': 'Invalid email or password',
                'code': 'INVALID_CREDENTIALS'
            }), 401
            
        token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(hours=app.config['JWT_EXPIRATION_HOURS'])
        }, app.config['SECRET_KEY'])
        
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
        predictions, confidences = predict_segments(segments)
        
        # Save file after successful processing
        filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image_file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(filepath, 'wb') as f:
            f.write(image_data)
        
        # Save predictions to database
        saved_predictions = []
        for pred, conf in zip(predictions, confidences):
            prediction = Prediction(
                user_id=current_user.id,
                filename=filename,
                prediction=pred,
                confidence=conf
            )
            db.session.add(prediction)
            saved_predictions.append(prediction)
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'data': {
                'text': ''.join(predictions),
                'characters': [{
                    'id': pred.id,
                    'character': pred.prediction,
                    'confidence': pred.confidence
                } for pred in saved_predictions]
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

@app.route('/api/generate-audio/<int:prediction_id>', methods=['GET'])
@token_required
def generate_audio(current_user, prediction_id):
    try:
        prediction = Prediction.query.get(prediction_id)
        
        if not prediction:
            return jsonify({
                'status': 'error',
                'message': 'Prediction not found',
                'code': 'PREDICTION_NOT_FOUND'
            }), 404
            
        if prediction.user_id != current_user.id:
            return jsonify({
                'status': 'error',
                'message': 'Unauthorized access',
                'code': 'UNAUTHORIZED'
            }), 403
            
        audio_file = f"{prediction_id}.mp3"
        audio_path = os.path.join(app.config['AUDIO_FOLDER'], audio_file)
        
        try:
            if not os.path.exists(audio_path):
                tts = gTTS(text=prediction.prediction, lang='hi')
                tts.save(audio_path)
                
            return send_file(audio_path, mimetype='audio/mp3')
            
        except Exception as audio_error:
            app.logger.error(f'Error generating audio file: {str(audio_error)}')
            if os.path.exists(audio_path):
                os.remove(audio_path)  # Clean up partial file
            raise
            
    except Exception as e:
        app.logger.error(f'Error generating audio: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Error generating audio',
            'code': 'AUDIO_GENERATION_ERROR'
        }), 500

@app.route('/api/history', methods=['GET'])
@token_required
def get_history(current_user):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)  # Limit max items
        
        if page < 1 or per_page < 1:
            return jsonify({
                'status': 'error',
                'message': 'Invalid pagination parameters',
                'code': 'INVALID_PAGINATION'
            }), 400
            
        predictions = Prediction.query\
            .filter_by(user_id=current_user.id)\
            .order_by(Prediction.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
            
        if not predictions.items and page != 1:
            return jsonify({
                'status': 'error',
                'message': 'Page not found',
                'code': 'PAGE_NOT_FOUND'
            }), 404
            
        return jsonify({
            'status': 'success',
            'data': {
                'predictions': [p.to_dict() for p in predictions.items],
                'total': predictions.total,
                'pages': predictions.pages,
                'current_page': page
            }
        }), 200
        
    except Exception as e:
        app.logger.error(f'Error fetching history: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Error fetching history',
            'code': 'HISTORY_ERROR'
        }), 500

@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    return jsonify({
        'status': 'success',
        'data': current_user.to_dict()
    }), 200

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

@app.route('/api/user/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    try:
        data = request.get_json()
        
        if not data.get('old_password') or not data.get('new_password'):
            return jsonify({
                'status': 'error',
                'message': 'Old and new passwords are required',
                'code': 'MISSING_PASSWORDS'
            }), 400
            
        if not check_password_hash(current_user.password, data['old_password']):
            return jsonify({
                'status': 'error',
                'message': 'Current password is incorrect',
                'code': 'INVALID_OLD_PASSWORD'
            }), 401
            
        if not is_strong_password(data['new_password']):
            return jsonify({
                'status': 'error',
                'message': 'New password must be at least 8 characters long',
                'code': 'WEAK_NEW_PASSWORD'
            }), 400
            
        current_user.password = generate_password_hash(data['new_password'])
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Password updated successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error changing password: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Error changing password',
            'code': 'PASSWORD_CHANGE_ERROR'
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
    """Remove the shirorekha (header line) using improved method."""
    height, width = img.shape
    horiz_proj = np.sum(img, axis=1)
    upper_half = horiz_proj[:height//2]
    header_position = np.argmax(upper_half)
    header_thickness = height // 15
    mask = np.ones_like(img)
    mask[max(0, header_position-header_thickness):min(height, header_position+header_thickness), :] = 0
    return img * mask

def get_connected_components(binary_img):
    """Get connected components with their bounding boxes and centroids."""
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(binary_img, connectivity=8)
    stats = stats[1:]
    centroids = centroids[1:]
    
    components = []
    for i, (stat, centroid) in enumerate(zip(stats, centroids)):
        x, y, w, h, area = stat
        if area > 50:
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
    
    if len(char_groups) != 3:
        char_width = img_width // 3
        new_groups = [[], [], []]
        for comp in components:
            group_idx = min(2, comp['x'] // char_width)
            new_groups[group_idx].append(comp)
        char_groups = new_groups
    
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

def process_image(image_data):
    """Process image data for prediction."""
    nparr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    
    target_height = 150
    aspect_ratio = img.shape[1] / img.shape[0]
    target_width = int(target_height * aspect_ratio)
    img = cv2.resize(img, (target_width, target_height))
    
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    img = clahe.apply(img)
    
    _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    binary_no_header = remove_header_line(binary)
    
    kernel = np.ones((2,2), np.uint8)
    binary_clean = cv2.morphologyEx(binary_no_header, cv2.MORPH_OPEN, kernel)
    binary_clean = cv2.morphologyEx(binary_clean, cv2.MORPH_CLOSE, kernel)
    
    components = get_connected_components(binary_clean)
    char_groups = merge_components(components, binary_clean.shape[1])
    
    segments = []
    for group in char_groups:
        if group:
            char_img = extract_character_from_group(group, binary_clean)
            if char_img is not None:
                segments.append(char_img)
    
    return segments

def process_segment(segment):
    """Process individual segment for prediction."""
    _, segment = cv2.threshold(segment, 127, 255, cv2.THRESH_BINARY)
    processed = cv2.resize(segment, (32, 32))
    processed = np.array(processed, dtype=np.float32) / 255.0
    processed = np.reshape(processed, (1, 32, 32, 1))
    return processed

def predict_segments(segments):
    """Predict characters from segments."""
    predictions = []
    confidences = []
    
    for segment in segments:
        processed = process_segment(segment)
        pred_probab = model.predict(processed)[0]
        pred_class = np.argmax(pred_probab)
        confidence = float(pred_probab[pred_class])
        
        predictions.append(letter_map[pred_class])
        confidences.append(confidence)
    
    return predictions, confidences

if __name__ == '__main__':
    app.run(
        debug=os.getenv('FLASK_ENV') == 'development',
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000))
    )