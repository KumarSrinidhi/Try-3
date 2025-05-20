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
    app.run(debug=True)