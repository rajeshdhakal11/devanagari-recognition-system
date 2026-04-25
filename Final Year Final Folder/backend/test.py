
import os
import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk
from keras.models import load_model
from dotenv import load_dotenv

class DevanagariRecognizer:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Devanagari Character Recognition")
        self.window.geometry("1000x800")
        
        # Load environment variables and model
        load_dotenv()
        self.model = load_model(os.getenv('MODEL_PATH', 'models/devanagari.h5'))
        
        # Character mapping
        self.letter_map = {
            0: 'CHECK', 1: 'क', 2: 'ख', 3: 'ग', 4: 'घ', 5: 'ङ', 6: 'च',
            7: 'छ', 8: 'ज', 9: 'झ', 10: 'ञ', 11: 'ट', 12: 'ठ', 13: 'ड',
            14: 'ढ', 15: 'ण', 16: 'त', 17: 'थ', 18: 'द', 19: 'ध', 20: 'न',
            21: 'प', 22: 'फ', 23: 'ब', 24: 'भ', 25: 'म', 26: 'य', 27: 'र',
            28: 'ल', 29: 'व', 30: 'श', 31: 'ष', 32: 'स', 33: 'ह',
            34: 'क्ष', 35: 'त्र', 36: 'ज्ञ'
        }
        
        self.setup_gui()

    def setup_gui(self):
        # Main frame
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Upload button
        self.upload_btn = ttk.Button(
            main_frame, 
            text="Upload Image",
            command=self.upload_image
        )
        self.upload_btn.grid(row=0, column=0, pady=10)
        
        # Image display frame
        image_frame = ttk.LabelFrame(main_frame, text="Images", padding="10")
        image_frame.grid(row=1, column=0, pady=10, sticky=(tk.W, tk.E))
        
        # Original image
        self.original_label = ttk.Label(image_frame)
        self.original_label.grid(row=0, column=0, padx=5)
        
        # Segmented image
        self.segmented_label = ttk.Label(image_frame)
        self.segmented_label.grid(row=0, column=1, padx=5)
        
        # Prediction display
        self.prediction_frame = ttk.LabelFrame(main_frame, text="Predictions", padding="10")
        self.prediction_frame.grid(row=2, column=0, pady=10, sticky=(tk.W, tk.E))
        
        self.prediction_label = ttk.Label(
            self.prediction_frame, 
            text="Upload an image to see the predictions",
            font=('Arial', 14)
        )
        self.prediction_label.grid(row=0, column=0, pady=5)
        
        self.details_label = ttk.Label(
            self.prediction_frame,
            text="",
            font=('Arial', 12)
        )
        self.details_label.grid(row=1, column=0, pady=5)

    def segment_image(self, image_path):
    # Read image
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        
        # Basic preprocessing
        _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Remove noise
        kernel = np.ones((2,2), np.uint8)
        binary = cv2.erode(binary, kernel, iterations=1)
        binary = cv2.dilate(binary, kernel, iterations=1)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Sort contours from left to right
        bounding_boxes = [cv2.boundingRect(c) for c in contours]
        (contours, bounding_boxes) = zip(*sorted(zip(contours, bounding_boxes),
                                                key=lambda b: b[1][0]))
        
        segments = []
        segmented_img = img.copy()
        
        min_width = 20  # Minimum width to be considered a character
        min_spacing = 10  # Minimum spacing between characters
        
        prev_x = 0
        prev_width = 0
        
        for contour, bbox in zip(contours, bounding_boxes):
            x, y, w, h = bbox
            
            # Filter out too small contours
            if w < min_width:
                continue
            
            # Check spacing from previous character
            spacing = x - (prev_x + prev_width)
            
            # If spacing is less than minimum, consider it part of the same character
            if spacing < min_spacing and prev_x > 0:
                # Merge with previous character
                x_start = prev_x
                width = (x + w) - prev_x
                height = max(h, prev_width)
                
                # Extract merged character region
                char_region = binary[y:y+height, x_start:x_start+width]
            else:
                # Extract individual character
                char_region = binary[y:y+h, x:x+w]
            
            # Add padding
            padding = 5
            char_region = cv2.copyMakeBorder(
                char_region, 
                padding, padding, padding, padding,
                cv2.BORDER_CONSTANT,
                value=0
            )
            
            segments.append(char_region)
            cv2.rectangle(segmented_img, (x, y), (x+w, y+h), (0, 0, 0), 2)
            
            # Update previous position and width for next iteration
            prev_x = x
            prev_width = w
        
        return segments, segmented_img

    def process_segment(self, segment):
        # Resize to model input size
        processed = cv2.resize(segment, (32, 32))
        processed = np.array(processed, dtype=np.float32) / 255.0
        processed = np.reshape(processed, (1, 32, 32, 1))
        return processed

    def predict_segments(self, segments):
        predictions = []
        confidences = []
        
        for segment in segments:
            processed = self.process_segment(segment)
            pred_probab = self.model.predict(processed)[0]
            pred_class = np.argmax(pred_probab)
            confidence = float(pred_probab[pred_class])
            
            predictions.append(self.letter_map[pred_class])
            confidences.append(confidence)
        
        return predictions, confidences

    def display_image(self, img, label, size=(400, 300)):
        # Convert OpenCV image to PIL format
        if len(img.shape) == 2:  # If grayscale
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        img = cv2.resize(img, size)
        img = Image.fromarray(img)
        photo = ImageTk.PhotoImage(img)
        label.configure(image=photo)
        label.image = photo

    def upload_image(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff")]
        )
        
        if file_path:
            try:
                # Read and display original image
                original_img = cv2.imread(file_path)
                self.display_image(original_img, self.original_label)
                
                # Segment image and display
                segments, segmented_img = self.segment_image(file_path)
                self.display_image(segmented_img, self.segmented_label)
                
                # Make predictions
                if segments:
                    predictions, confidences = self.predict_segments(segments)
                    
                    # Display results
                    result_text = "".join(predictions)
                    self.prediction_label.configure(
                        text=f"Predicted Text: {result_text}"
                    )
                    
                    # Display detailed results
                    details = "\n".join([
                        f"Character {i+1}: {char} (Confidence: {conf:.2%})"
                        for i, (char, conf) in enumerate(zip(predictions, confidences))
                    ])
                    self.details_label.configure(text=details)
                else:
                    self.prediction_label.configure(
                        text="No characters detected in the image"
                    )
                    self.details_label.configure(text="")
                    
            except Exception as e:
                self.prediction_label.configure(
                    text="Error processing image"
                )
                self.details_label.configure(text=str(e))

    def run(self):
        self.window.mainloop()

if __name__ == "__main__":
    app = DevanagariRecognizer()
    app.run()


