import face_recognition
import numpy as np
import os
import pickle


BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_PATH = os.path.join(BASE_DIR, "dataset")
MODEL_PATH   = os.path.join(BASE_DIR, "models", "face_data.pkl")


def train_model():
    """
    Encode all images per student, average them into ONE 128-d vector per student.
    Result: model has N rows (one per student), not N*20 rows.
    Face comparison per frame: N ops instead of N*20 ops.
    """
    if not os.path.exists(DATASET_PATH):
        print("Dataset folder not found.")
        return

    print("Training model...")

    known_names = []
    known_faces = []   # one averaged numpy array per student

    for student_name in sorted(os.listdir(DATASET_PATH)):
        student_folder = os.path.join(DATASET_PATH, student_name)
        if not os.path.isdir(student_folder):
            continue

        encs = []
        for image_name in os.listdir(student_folder):
            if not image_name.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            image_path = os.path.join(student_folder, image_name)
            try:
                img  = face_recognition.load_image_file(image_path)
                enc  = face_recognition.face_encodings(img, num_jitters=1, model="small")
                if enc:
                    encs.append(enc[0])
            except Exception as e:
                print(f"  Skip {image_path}: {e}")

        if encs:
            # Average all images into ONE encoding per student
            avg = np.mean(encs, axis=0)
            # Normalize to unit vector to make distance comparisons stable
            norm = np.linalg.norm(avg)
            if norm > 0:
                avg = avg / norm
            known_names.append(student_name)
            known_faces.append(avg)
            print(f"  {student_name}: {len(encs)} images -> 1 averaged encoding")
        else:
            print(f"  {student_name}: no face found, skipped")

    if not known_names:
        print("No encodings generated.")
        return

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump((known_faces, known_names), f)

    print(f"Model saved: {len(known_names)} student(s), {len(known_names)} encoding(s)")
    print(f"Path: {MODEL_PATH}")


if __name__ == "__main__":
    train_model()
