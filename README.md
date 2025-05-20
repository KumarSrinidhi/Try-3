# Exam Management System

A comprehensive platform for creating, taking, and grading online exams, built with Python/Flask and MySQL.

## Features

- **User Authentication**: Secure login/registration with role-based access for students, teachers, and admins
- **Exam Creation**: Teachers can create and manage exams with multiple question types (MCQ/text/code)
- **Exam Taking**: Students can take exams and receive immediate feedback on MCQs
- **Grading System**: Automatic grading for MCQs, manual grading for text/code questions
- **Analytics**: Teachers can view statistics and insights on exam performance
- **Reviews**: Students can leave ratings and feedback for exams
- **Notifications**: Real-time alerts for new exams, grades, and activities

## System Architecture

### Components
- **Frontend**: HTML, CSS, JavaScript with Bootstrap 5
- **Backend**: Python/Flask with Blueprints for modular organization
- **Database**: MySQL with SQLAlchemy ORM
- **Authentication**: Flask-Login for session management

### Data Flow
User Request → Flask Routes → Database Operations → Response → Frontend Rendering

### For Teachers
- Create exams with time limits
- Add multiple types of questions (multiple choice, text, code)
- Review student submissions
- Grade manually graded questions

### For Students
- Take exams within time limits
- Auto-save answers during exams
- View results after completion

## Setup Instructions

### Prerequisites

- Python 3.10+
- MySQL 8.0+
- Git

### Installation

1. Clone the repository
   ```
   git clone https://github.com/yourusername/exam-platform.git
   cd exam-platform
   ```

2. Create a virtual environment
   ```
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

3. Install dependencies
   ```
   pip install -r requirements.txt
   ```

4. Set up the database
   ```
   # Create database in MySQL
   mysql -u root -p -e "CREATE DATABASE exam_platform;"

   # Run migrations
   flask db upgrade
   ```

5. Configure environment variables (create a .env file in project root)
   ```
   SECRET_KEY=your-secret-key
   DATABASE_URL=mysql+mysqlconnector://username:password@localhost/exam_platform
   FLASK_APP=app.py
   FLASK_ENV=development
   ```

6. Start the application
   ```
   flask run
   ```

The application will be available at `http://127.0.0.1:5000`

### Default Admin Account

After initial setup, create an admin account using the Python shell:

```python
flask shell
```

```python
from app.models import User, db
admin = User(username="admin", email="admin@example.com", user_type="admin")
admin.set_password("secure_password")
db.session.add(admin)
db.session.commit()
```

## Development

### Running Tests
```powershell
pytest
```

### Database Migrations

When changing models:
```powershell
flask db migrate -m "Description of changes"
flask db upgrade
```

## Security Considerations

- All passwords are hashed using PBKDF2-SHA256
- Session protection with secure cookies
- Input validation and sanitization
- Parameterized SQL queries

## License

[MIT License](LICENSE)