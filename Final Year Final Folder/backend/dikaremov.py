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

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# App Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER', 'uploads')
app.config['AUDIO_FOLDER'] = 'audio'
app.config['MODEL_PATH'] = os.getenv('MODEL_PATH', 'models/devanagari.h5')
app.config['JWT_EXPIRATION_HOURS'] = int(os.getenv('JWT_EXPIRATION_HOURS', 24))

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

# Image Processing Functions
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
    # Convert image data to numpy array
    nparr = np.frombuffer(image_data, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)
    
    # Resize while maintaining aspect ratio
    target_height = 150
    aspect_ratio = img.shape[1] / img.shape[0]
    target_width = int(target_height * aspect_ratio)
    img = cv2.resize(img, (target_width, target_height))
    
    # Enhance contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    img = clahe.apply(img)
    
    # Binarize
    _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Remove header line and clean
    binary_no_header = remove_header_line(binary)
    kernel = np.ones((2,2), np.uint8)
    binary_clean = cv2.morphologyEx(binary_no_header, cv2.MORPH_OPEN, kernel)
    binary_clean = cv2.morphologyEx(binary_clean, cv2.MORPH_CLOSE, kernel)
    
    # Get and merge components
    components = get_connected_components(binary_clean)
    char_groups = merge_components(components, binary_clean.shape[1])
    
    # Extract characters
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

# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header:
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
                
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
            
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'User not found'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated

# Routes
@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.get_json()
        
        required_fields = ['first_name', 'last_name', 'username', 'email', 
                         'password', 'date_of_birth']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already exists'}), 400
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email already exists'}), 400
        
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
            'message': 'User created successfully',
            'user': new_user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error in signup: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/signin', methods=['POST'])
def signin():
    try:
        data = request.get_json()
        
        if not data.get('email') or not data.get('password'):
            return jsonify({'error': 'Email and password are required'}), 400
            
        user = Useruser = User.query.filter_by(email=data['email']).first()
        
        if user and check_password_hash(user.password, data['password']):
            token = jwt.encode({
                'user_id': user.id,
                'exp': datetime.utcnow() + timedelta(hours=app.config['JWT_EXPIRATION_HOURS'])
            }, app.config['SECRET_KEY'])
            
            return jsonify({
                'token': token,
                'user': user.to_dict()
            }), 200
        
        return jsonify({'error': 'Invalid credentials'}), 401
        
    except Exception as e:
        app.logger.error(f'Error in signin: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/predict', methods=['POST'])
@token_required
def predict(current_user):
    if not model:
        return jsonify({'error': 'Model not loaded'}), 500
        
    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400
        
    try:
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
            
        # Save original image
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image_file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image_file.save(filepath)
        
        # Read and process image
        image_data = image_file.read()
        segments = process_image(image_data)
        
        if not segments:
            return jsonify({'error': 'No characters detected in the image'}), 400
        
        # Get predictions
        predictions, confidences = predict_segments(segments)
        
        # Save all predictions to database
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
        
        # Prepare response
        result = {
            'text': ''.join(predictions),
            'characters': [{
                'id': pred.id,
                'character': pred.prediction,
                'confidence': pred.confidence
            } for pred in saved_predictions]
        }
        
        return jsonify(result), 200
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error in prediction: {str(e)}')
        return jsonify({'error': 'Error processing image'}), 500

@app.route('/api/generate-audio/<int:prediction_id>', methods=['GET'])
@token_required
def generate_audio(current_user, prediction_id):
    try:
        prediction = Prediction.query.get_or_404(prediction_id)
        
        # Check if user has access to this prediction
        if prediction.user_id != current_user.id:
            return jsonify({'error': 'Unauthorized access'}), 403
            
        audio_file = f"{prediction_id}.mp3"
        audio_path = os.path.join(app.config['AUDIO_FOLDER'], audio_file)
        
        # Generate audio if it doesn't exist
        if not os.path.exists(audio_path):
            tts = gTTS(text=prediction.prediction, lang='hi')
            tts.save(audio_path)
            
        return send_file(audio_path, mimetype='audio/mp3')
        
    except Exception as e:
        app.logger.error(f'Error generating audio: {str(e)}')
        return jsonify({'error': 'Error generating audio'}), 500

@app.route('/api/history', methods=['GET'])
@token_required
def get_history(current_user):
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        predictions = Prediction.query\
            .filter_by(user_id=current_user.id)\
            .order_by(Prediction.created_at.desc())\
            .paginate(page=page, per_page=per_page)
            
        return jsonify({
            'predictions': [p.to_dict() for p in predictions.items],
            'total': predictions.total,
            'pages': predictions.pages,
            'current_page': page
        }), 200
        
    except Exception as e:
        app.logger.error(f'Error fetching history: {str(e)}')
        return jsonify({'error': 'Error fetching history'}), 500

@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    return jsonify(current_user.to_dict()), 200

@app.route('/api/user/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    try:
        data = request.get_json()
        
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
        return jsonify(current_user.to_dict()), 200
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error updating profile: {str(e)}')
        return jsonify({'error': 'Error updating profile'}), 500

@app.route('/api/user/change-password', methods=['POST'])
@token_required
def change_password(current_user):
    try:
        data = request.get_json()
        
        if not data.get('old_password') or not data.get('new_password'):
            return jsonify({'error': 'Old and new passwords are required'}), 400
            
        if not check_password_hash(current_user.password, data['old_password']):
            return jsonify({'error': 'Invalid old password'}), 401
            
        current_user.password = generate_password_hash(data['new_password'])
        db.session.commit()
        
        return jsonify({'message': 'Password updated successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error changing password: {str(e)}')
        return jsonify({'error': 'Error changing password'}), 500

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    app.run(
        debug=os.getenv('FLASK_ENV') == 'development',
        host='0.0.0.0',
        port=5000
    )