# 🎓 AI Smart Attendance System Using Face Recognition

[!Python](https://www.python.org/)
[!Flask](https://flask.palletsprojects.com/)
[!OpenCV](https://opencv.org/)
[!SQLite](https://sqlite.org/)
[!License](LICENSE)

## 📝 Project Overview
The **AI Smart Attendance System** is a professional-grade automated solution designed to streamline the attendance-taking process in educational and corporate environments. By leveraging state-of-the-art **Deep Learning** and **Computer Vision**, the system identifies faces from a live webcam feed and logs attendance instantaneously into a secure SQLite database. 

This project eliminates the manual effort of roll-calling, prevents proxy attendance, and provides administrators with powerful data visualization and reporting tools.

---

## ✨ Key Features

### 🤖 Face Recognition & Attendance
- **Real-time Detection:** High-speed recognition using 128-D facial encodings.
- **One Encoding Per Student:** Optimized matching logic for high accuracy.
- **Proxy Prevention:** Minimizes manual errors and unauthorized attendance.

### 👨‍💼 Administration & Management
- **Admin Dashboard:** Centralized view of system health and real-time statistics.
- **Student Registration:** Seamless onboarding with automated face capture and training.
- **Student Management:** Full CRUD operations (Create, Read, Update, Delete) for student records.

### 📊 Analytics & Reporting
- **Dynamic Analytics:** Visual trends (Monthly/Daily) using Matplotlib.
- **Multi-format Exports:** Instant generation of CSV and professional PDF reports.
- **Email Notifications:** Automatic SMTP alerts sent to students/parents upon attendance marking.

### 🔐 Security & Access
- **Student Login:** Personalized portal for students to view their attendance history.
- **Secure Auth:** Password hashing using `werkzeug.security`.
- **Environment Control:** Sensitive credentials managed via `.env` files.

---

## 🛠️ Technology Stack

| Component          | Technology                                                     |
|--------------------|----------------------------------------------------------------|
| **Backend**        | Python 3.10, Flask                                             |
| **Computer Vision**| OpenCV, face-recognition (dlib-based)                          |
| **Database**       | SQLite3                                                        |
| **Data Science**   | Pandas, NumPy, Matplotlib                                      |
| **Frontend**       | HTML5, CSS3, Bootstrap 5, JavaScript                           |
| **Reporting**      | ReportLab (PDF), OpenPyXL (Excel)                               |
| **Communication**  | SMTP (Email Notifications)                                     |

---

## 🏗️ System Architecture

1.  **Capture:** OpenCV streams live video and detects faces.
2.  **Analyze:** The `face-recognition` library extracts 128 feature points (landmarks).
3.  **Identify:** Encodings are compared against `models/face_model.pkl` using Euclidean distance.
4.  **Log:** On match, a record is added to `attendance.db` and an email trigger is queued.
5.  **Visualize:** The Flask backend serves data to the Bootstrap-based Analytics dashboard.

---

## 📂 Folder Structure

```text
├── backend/              # Core Flask application & ML scripts
├── frontend/             # UI Layer
│   ├── static/           # CSS, JS, and UI Images
│   └── templates/        # Jinja2 HTML templates
├── dataset/              # Student face samples (gitignored)
├── models/               # Trained .pkl face encodings
├── scripts/              # Database initialization & utilities
├── utils/                # Helper functions for Email & PDF generation
├── screenshots/          # Project visualization for documentation
├── .env.example          # Configuration template
├── .gitignore            # Git exclusion rules
├── LICENSE               # MIT License
├── README.md             # Main documentation
└── requirements.txt      # Project dependencies
```

---

## 🚀 Installation Guide

### 1. Prerequisites
- Python 3.10+
- C++ Compiler (for `dlib`)

### 2. Setup
```bash
# Clone the repository
git clone https://github.com/yourusername/ai-smart-attendance-system.git
cd ai-smart-attendance-system

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Rename `.env.example` to `.env` and configure your SMTP settings and `SECRET_KEY`.

### 4. Initialize & Run
```bash
python backend/database.py  # Create DB tables
python backend/app.py       # Start Flask server
```

---

## 📖 Usage Guide

1.  **Admin Login:** Navigate to `/login` and use default credentials (`admin` / `admin123`).
2.  **Student Registration:** Go to "Add Student", fill details, and use the "Capture" tool to save face samples.
3.  **Live Attendance:** Open the "Live Camera" page to start the recognition engine.
4.  **Reporting:** Visit the "Analytics" tab to view charts and download PDF/CSV summaries.

---

## 📸 Screenshots
Detailed visual walkthroughs can be found in PROJECT_SCREENSHOTS.md.

> **Tip:** You can see the Dashboard, Registration, and Live Recognition interfaces there.

---

## 🔮 Future Enhancements
- **Liveness Detection:** Implementing eye-blink or head-movement detection to prevent spoofing.
- **Cloud Integration:** Migrating storage to AWS S3 and database to PostgreSQL.
- **Mobile App:** A cross-platform mobile application for students to track attendance on the go.

---

## 👨‍💻 Author
**[Bhadraiah meda]**
- **Degree:** B.Tech in Computer Science & Engineering [aiml]
- **GitHub:** @bhadraiahmeda
- **LinkedIn:** [https://www.linkedin.com/in/meda-bhadraiah-23a6483b1/]

---

## 📝 License
Distributed under the MIT License. See `LICENSE` for more information.
