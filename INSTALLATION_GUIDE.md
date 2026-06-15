# ⚙️ Installation Guide

### 1. Prerequisites
*   Python 3.10.x
*   C++ Compiler (Required for `dlib`)
    *   *Windows:* Install "Desktop development with C++" via Visual Studio Installer.

### 2. Setup Environment
```bash
git clone https://github.com/yourusername/ai-smart-attendance-system.git
cd ai-smart-attendance-system
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configuration
1.  Rename `.env.example` to `.env`.
2.  Generate a secret key: `python -c "import secrets; print(secrets.token_hex(16))"`.
3.  Add your Gmail App Password for SMTP notifications.

### 5. Initialize Database
```bash
python backend/database.py
```

### 6. Run
`python backend/app.py`