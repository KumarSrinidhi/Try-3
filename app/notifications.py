from app.models import db, Notification, User, ExamAttempt, Exam, ExamReview
from flask_login import current_user
from app.email import send_exam_graded_email, send_new_exam_email, send_exam_review_email

def send_notification(user_id, message, notification_type, related_id=None):
    """
    Send a notification to a specific user
    
    Args:
        user_id (int): The ID of the user to notify
        message (str): The notification message
        notification_type (str): Type of notification (info, exam_graded, etc)
        related_id (int, optional): ID of the related entity (exam, attempt)
    """
    notification = Notification(
        user_id=user_id,
        message=message,
        type=notification_type,
        related_id=related_id
    )
    db.session.add(notification)
    db.session.commit()


def notify_exam_graded(attempt_id):
    """
    Notify a student that their exam has been graded
    
    Args:
        attempt_id (int): The ID of the graded exam attempt
    """
    attempt = ExamAttempt.query.get(attempt_id)
    if attempt:
        exam = attempt.exam
        student = User.query.get(attempt.student_id)
        
        # Send in-app notification
        send_notification(
            user_id=attempt.student_id,
            message=f"Your exam '{exam.title}' has been graded.",
            notification_type='exam_graded',
            related_id=attempt_id
        )
        
        # Send email notification
        score = attempt.calculate_score()
        send_exam_graded_email(student, exam.title, score)


def notify_new_exam(exam_id):
    """
    Notify all students about a new exam
    
    Args:
        exam_id (int): The ID of the newly published exam
    """
    exam = Exam.query.get(exam_id)
    if exam and exam.is_published:
        # Get all student users
        students = User.query.filter_by(user_type='student').all()
        
        for student in students:
            # Send in-app notification
            send_notification(
                user_id=student.id,
                message=f"New exam available: '{exam.title}'",
                notification_type='new_exam',
                related_id=exam_id
            )
            
            # Send email notification
            send_new_exam_email(student, exam)


def notify_new_review(review_id, exam_id):
    """
    Notify the teacher about a new review on their exam
    
    Args:
        review_id (int): The ID of the new review
        exam_id (int): The ID of the reviewed exam
    """
    exam = Exam.query.get(exam_id)
    if exam:
        send_notification(
            user_id=exam.creator_id,
            message=f"A new review has been submitted for your exam '{exam.title}'",
            notification_type='new_review',
            related_id=exam_id
        )
