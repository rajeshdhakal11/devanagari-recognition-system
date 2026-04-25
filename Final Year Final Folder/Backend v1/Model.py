import numpy as np
import pandas as pd
from keras import layers
from keras.layers import Input, Dense, Activation, ZeroPadding2D, BatchNormalization, Flatten, Conv2D
from keras.layers import AveragePooling2D, MaxPooling2D, Dropout, GlobalMaxPooling2D, GlobalAveragePooling2D
from keras.utils import to_categorical  # Updated import
from keras.models import Sequential
from keras.callbacks import ModelCheckpoint

# Load Data
data = pd.read_csv("data.csv")
dataset = np.array(data)
np.random.shuffle(dataset)
X = dataset
Y = dataset
X = X[:, 0:1024]
Y = Y[:, 1024]

# Pre-process Data
# Train and Test data variables
X_train = X[0:70000, :]
X_train = X_train / 255.
X_test = X[70000:72001, :]
X_test = X_test / 255.

# Reshape
Y = Y.reshape(Y.shape[0], 1)
Y_train = Y[0:70000, :]
Y_train = Y_train.T
Y_test = Y[70000:72001, :]
Y_test = Y_test.T

print("number of training examples = " + str(X_train.shape[0]))
print("number of test examples = " + str(X_test.shape[0]))
print("X_train shape: " + str(X_train.shape))
print("Y_train shape: " + str(Y_train.shape))
print("X_test shape: " + str(X_test.shape))
print("Y_test shape: " + str(Y_test.shape))

# Let's see what we have
# number of training examples = 70000
# number of test examples = 2000
# X_train shape: (70000, 1024)
# Y_train shape: (1, 70000)
# X_test shape: (2000, 1024)
# Y_test shape: (1, 2000)

# Back to code...
image_x = 32
image_y = 32
train_y = to_categorical(Y_train)  # Updated function
test_y = to_categorical(Y_test)    # Updated function
train_y = train_y.reshape(train_y.shape[1], train_y.shape[2])
test_y = test_y.reshape(test_y.shape[1], test_y.shape[2])
X_train = X_train.reshape(X_train.shape[0], image_x, image_y, 1)
X_test = X_test.reshape(X_test.shape[0], image_x, image_y, 1)

print("X_train shape: " + str(X_train.shape))
print("Y_train shape: " + str(train_y.shape))
# What we got here
# X_train shape: (70000, 32, 32, 1)
# Y_train shape: (70000, 37)

# Define Model
def keras_model(image_x, image_y):
    num_of_classes = 37
    model = Sequential()
    model.add(Conv2D(filters=32, kernel_size=(5, 5), input_shape=(image_x, image_y, 1), activation='relu'))
    model.add(MaxPooling2D(pool_size=(2, 2), strides=(2, 2), padding='same'))
    model.add(Conv2D(64, (5, 5), activation='relu'))
    model.add(MaxPooling2D(pool_size=(5, 5), strides=(5, 5), padding='same'))
    model.add(Flatten())
    model.add(Dense(num_of_classes, activation='softmax'))
    model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])
    filepath = "devanagari.h5"
    checkpoint1 = ModelCheckpoint(filepath, monitor='val_acc', verbose=1, save_best_only=True, mode='max')
    callbacks_list = [checkpoint1]
    return model, callbacks_list

model, callbacks_list = keras_model(image_x, image_y)
model.fit(X_train, train_y, validation_data=(X_test, test_y), epochs=8, batch_size=64, callbacks=callbacks_list)
scores = model.evaluate(X_test, test_y, verbose=0)
print("CNN Error: %.2f%%" % (100 - scores[1] * 100))
model.summary()  # Replaced print_summary with model.summary()
model.save('devanagari.h5')

# Model: "sequential_1"
# _________________________________________________________________
# Layer (type)                 Output Shape              Param #
# =================================================================
# conv2d_1 (Conv2D)            (None, 28, 28, 32)        832
# _________________________________________________________________
# max_pooling2d_1 (MaxPooling2 (None, 14, 14, 32)        0
# _________________________________________________________________
# conv2d_2 (Conv2D)            (None, 10, 10, 64)        51264
# _________________________________________________________________
# max_pooling2d_2 (MaxPooling2 (None, 2, 2, 64)          0
# _________________________________________________________________
# flatten_1 (Flatten)          (None, 256)               0
# _________________________________________________________________
# dense_1 (Dense)              (None, 37)                9509
# =================================================================
# Total params: 61,605
# Trainable params: 61,605
# Non-trainable params: 0
# _________________________________________________________________
# This program will create devnagari.h5 file