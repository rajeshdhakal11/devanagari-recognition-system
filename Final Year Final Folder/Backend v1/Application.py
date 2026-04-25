## APPLICATION.PY

import numpy as np
from keras.models import load_model
import cv2
import tkinter as tk
from tkinter import filedialog

# Load the pre-trained model
model1 = load_model('devanagari.h5')
print("Model loaded successfully!")

# Dictionary to map class indices to Devanagari characters
letter_count = {
    0: 'CHECK', 1: '01_ka', 2: '02_kha', 3: '03_ga', 4: '04_gha', 5: '05_kna', 6: '06_cha',
    7: '07_chha', 8: '08_ja', 9: '09_jha', 10: '10_yna', 11: '11_taa', 12: '12_thaa', 13: '13_daa', 
    14: '14_dhaa', 15: '15_adna', 16: '16_ta', 17: '17_tha', 18: '18_da', 19: '19_dha', 20: '20_na', 
    21: '21_pa', 22: '22_pha', 23: '23_ba', 24: '24_bha', 25: '25_ma', 26: '26_yaw', 27: '27_ra', 
    28: '28_la', 29: '29_waw', 30: '30_sha', 31: '31_sha', 32: '32_sa', 33: '33_ha',
    34: '34_kshya', 35: '35_tra', 36: '36_gya'
}

# Function to preprocess the image for prediction
def keras_process_image(img):
    image_x = 32
    image_y = 32

    # Convert the image to grayscale if it's not already
    if len(img.shape) == 3:  # If the image has 3 channels (RGB)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Invert the image (if the background is white)
    img = cv2.bitwise_not(img)

    # Apply thresholding to create a binary image
    _, img = cv2.threshold(img, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # Resize the image to 32x32
    img = cv2.resize(img, (image_x, image_y))

    # Convert to numpy array and normalize pixel values
    img = np.array(img, dtype=np.float32)
    img = img / 255.0

    # Reshape the image to match the model's input shape (1, 32, 32, 1)
    img = np.reshape(img, (1, image_x, image_y, 1))

    return img

# Function to predict the character
def keras_predict(model, image):
    processed = keras_process_image(image)
    print("Processed image shape:", processed.shape)  # Debug statement
    pred_probab = model.predict(processed)[0]
    pred_class = np.argmax(pred_probab)  # Get the class with the highest probability
    return letter_count[pred_class]      # Return the corresponding character

# Function to handle image upload and prediction
def upload_image():
    # Open a file dialog to select an image
    file_path = filedialog.askopenfilename(
        title="Select an Image",
        filetypes=[("Image Files", "*.png *.jpg *.jpeg")]
    )

    if file_path:
        # Load the selected image
        image = cv2.imread(file_path)

        if image is None:
            print("Error: Could not load image. Please check the file path.")
        else:
            # Predict the character
            predicted_char = keras_predict(model1, image)
            print(f"Predicted Character: {predicted_char}")

            # Display the image with the predicted character
            image_display = cv2.resize(image, (500, 500))  # Resize for better display

            # Add the predicted character text to the image
            cv2.putText(image_display, f"Predicted: {predicted_char}", (8, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)  # Red text for contrast

            # Show the image
            cv2.imshow("Prediction", image_display)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

# Create a simple GUI for image upload
def create_gui():
    root = tk.Tk()
    root.title("Devanagari Character Recognition")
    root.geometry("500x500")

    # Add a button to upload an image
    upload_button = tk.Button(
        root,
        text="Upload Image",
        command=upload_image,
        font=("Arial", 14),
        bg="lightblue",
        fg="black"
    )
    upload_button.pack(pady=20)

    root.mainloop()

# Run the GUI
if __name__ == "__main__":
    create_gui()