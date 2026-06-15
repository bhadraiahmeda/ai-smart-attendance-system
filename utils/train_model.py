import face_recognition
import os
import pickle

dataset_path = "dataset"

known_faces = []
known_names = []

# Read dataset folders
for person_name in os.listdir(dataset_path):

    person_folder = os.path.join(dataset_path, person_name)

    # Skip if not folder
    if not os.path.isdir(person_folder):
        continue

    # Read images
    for image_name in os.listdir(person_folder):

        image_path = os.path.join(person_folder, image_name)

        print(f"Processing {image_path}")

        image = face_recognition.load_image_file(image_path)

        encodings = face_recognition.face_encodings(image)

        # Check face detected
        if len(encodings) > 0:
            known_faces.append(encodings[0])
            known_names.append(person_name)

# Save trained model
model_data = {
    "faces": known_faces,
    "names": known_names
}

with open("models/face_model.pkl", "wb") as file:
    pickle.dump(model_data, file)

print("Model trained successfully!")