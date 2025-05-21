from dotenv import load_dotenv
load_dotenv()  # Load environment variables from .env file

from app import create_app, db
from app.models import User, Exam, Question, QuestionOption, ExamAttempt, Answer

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db, 
        'User': User, 
        'Exam': Exam,
        'Question': Question,
        'QuestionOption': QuestionOption,
        'ExamAttempt': ExamAttempt,
        'Answer': Answer
    }

if __name__ == '__main__':
    print("=" * 50)
    print("STARTING APPLICATION")
    print("=" * 50)
    print("\nChecking database connection...")
    
    # Test database connection
    from sqlalchemy import text
    try:
        with app.app_context():
            result = db.session.execute(text("SELECT 1")).fetchone()
            print(f"Database connection successful: {result[0]}")
            
        print("\nInitializing application...")
        app.run(debug=True)
    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nApplication failed to start. Please check the error message above.")