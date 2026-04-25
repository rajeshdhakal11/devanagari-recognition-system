import numpy as np
import pandas as pd
from keras.models import Sequential
from keras.layers import Conv2D, MaxPooling2D, Flatten, Dense, Dropout, BatchNormalization
from keras.optimizers import Adam
from keras.callbacks import EarlyStopping, ModelCheckpoint
from keras.utils import to_categorical

# Load the image dataset (replace "data.csv" with your dataset)
# Each row should have 1024 columns for the image (32x32) and 1 column for the label
data = pd.read_csv("labels.csv")  # Ensure this file has 1024 columns for images and 1 column for labels
dataset = np.array(data)
np.random.shuffle(dataset)

# Split into features (X) and labels (Y)
X = dataset[:, 0:1024]  # Features (32x32 images flattened into 1024 columns)
Y = dataset[:, 1024]    # Labels

# Preprocess the data
X = X.reshape(X.shape[0], 32, 32, 1)  # Reshape to (32, 32, 1)
X = X / 255.0  # Normalize pixel values
Y = to_categorical(Y, num_classes=37)  # One-hot encode labels

# Split into training and testing sets
X_train, X_test = X[:70000], X[70000:]
Y_train, Y_test = Y[:70000], Y[70000:]

# Load the labels.csv file for mapping class indices to Devanagari characters
labels_df = pd.read_csv("labels.csv", header=None)

# Parse the CSV file to extract Numerals, Vowels, and Consonants
# Numerals: Rows 3 to 12
numerals = labels_df.iloc[3:13, :3].rename(columns={0: "Class", 1: "Label", 2: "Devanagari Label"})
# Vowels: Rows 17 to 28
vowels = labels_df.iloc[17:29, :3].rename(columns={0: "Class", 1: "Label", 2: "Devanagari Label"})
# Consonants: Rows 33 to 68
consonants = labels_df.iloc[33:69, :3].rename(columns={0: "Class", 1: "Label", 2: "Devanagari Label"})

# Combine the data into a single DataFrame
combined_df = pd.concat([numerals, vowels, consonants], ignore_index=True)

# Convert the "Class" column to integers
# Ensure the "Class" column contains only numeric values
combined_df = combined_df[pd.to_numeric(combined_df["Class"], errors="coerce").notna()]
combined_df["Class"] = combined_df["Class"].astype(int)

# Create a mapping from class index to Devanagari character
class_to_label = dict(zip(combined_df["Class"], combined_df["Devanagari Label"]))

# Define a CNN model
def create_model():
    model = Sequential()

    # First Convolutional Block
    model.add(Conv2D(32, (5, 5), activation='relu', input_shape=(32, 32, 1)))
    model.add(BatchNormalization())
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.25))

    # Second Convolutional Block
    model.add(Conv2D(64, (5, 5), activation='relu'))
    model.add(BatchNormalization())
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.25))

    # Third Convolutional Block
    model.add(Conv2D(128, (3, 3), activation='relu'))
    model.add(BatchNormalization())
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.25))

    # Fully Connected Layers
    model.add(Flatten())
    model.add(Dense(256, activation='relu'))
    model.add(BatchNormalization())
    model.add(Dropout(0.5))
    model.add(Dense(37, activation='softmax'))  # Output layer for 37 classes

    # Compile the model
    model.compile(
        optimizer=Adam(learning_rate=0.001),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )

    return model

# Create the model
model = create_model()
print(model.summary())

# Define callbacks
early_stopping = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)
model_checkpoint = ModelCheckpoint('best_model.h5', monitor='val_accuracy', save_best_only=True)

# Train the model
history = model.fit(
    X_train, Y_train,
    validation_data=(X_test, Y_test),
    epochs=50,
    batch_size=64,
    callbacks=[early_stopping, model_checkpoint]
)

# Evaluate the model
loss, accuracy = model.evaluate(X_test, Y_test, verbose=0)
print(f"Test Accuracy: {accuracy * 100:.2f}%")

# Save the final model
model.save('devanagari_vowel_improved.h5')