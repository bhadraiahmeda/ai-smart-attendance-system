import cv2
import os


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def capture_student_faces(student_name: str, num_images: int = 20):
    """Capture `num_images` webcam frames and save to dataset/<student_name>/."""
    dataset_path = os.path.join(BASE_DIR, "dataset", student_name)
    os.makedirs(dataset_path, exist_ok=True)

    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        print("ERROR: Cannot open webcam.")
        return

    count = 0
    print(f"Capturing faces for '{student_name}'...")

    while count < num_images:
        ret, frame = camera.read()
        if not ret:
            break

        img_path = os.path.join(dataset_path, f"img_{count}.jpg")
        cv2.imwrite(img_path, frame)
        print(f"  Saved: {img_path}")
        count += 1
        cv2.waitKey(200)

    camera.release()
    cv2.destroyAllWindows()
    print(f"Face capture complete — {count} images saved.")
