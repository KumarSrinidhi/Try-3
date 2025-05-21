from datetime import datetime, timedelta
import csv
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, jsonify, abort, session, make_response
)
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func, desc
from sqlalchemy.sql import case
from functools import wraps

from app.models import db, User, Exam, Question, QuestionOption, ExamAttempt, Answer, ExamReview, Notification, Group
from app.forms import (
    ExamForm, QuestionForm, MCQAnswerForm, TextAnswerForm,
    CodeAnswerForm, GradeAnswerForm, ExamReviewForm, ImportQuestionsForm,
    MarkAllReadForm, MarkReadForm, TakeExamForm, AddGroupExamForm
)
from app.notifications import notify_exam_graded, notify_new_exam, notify_new_review
from app.decorators import admin_required, teacher_required, student_required

# Create blueprints for organization
main_bp = Blueprint('main', __name__)
teacher_bp = Blueprint('teacher', __name__, url_prefix='/teacher')
student_bp = Blueprint('student', __name__, url_prefix='/student')


# Helper functions for role-based access control
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def teacher_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_teacher():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def student_required(f):
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_student():
            abort(403)
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


# Helper function to check if exam time has expired
def check_time_expired(attempt):
    """Check if the exam time has expired for an attempt."""
    if not attempt or not attempt.started_at or not attempt.exam:
        return True
        
    if not attempt.exam.duration:  # If no duration set, exam doesn't expire
        return False
        
    time_limit = attempt.started_at + timedelta(minutes=attempt.exam.duration)
    return datetime.utcnow() > time_limit

def validate_submission_time(attempt, submission_time):
    """Validate that a submission is being made within the time limit."""
    if not attempt or not attempt.started_at or not attempt.exam:
        return False
        
    if not attempt.exam.duration:  # If no duration set, submission is always valid
        return True
        
    time_limit = attempt.started_at + timedelta(minutes=attempt.exam.duration)
    grace_period = timedelta(minutes=1)  # 1 minute grace period for network delays
    
    return submission_time <= (time_limit + grace_period)


# Main routes
@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin():
        # For admins: redirect to admin dashboard
        return redirect(url_for('main.admin_dashboard'))
    elif current_user.is_teacher():
        # For teachers: show created exams
        exams = Exam.query.filter_by(creator_id=current_user.id).all()
        return render_template('dashboard/teacher_dashboard.html', exams=exams)
    else:
        # For students: show available and completed exams
        available_exams = Exam.query.filter_by(is_published=True).all()
        
        # Get student's attempts
        attempts = ExamAttempt.query.filter_by(student_id=current_user.id).all()
        completed_attempts = [attempt for attempt in attempts if attempt.is_completed]
        completed_exams = [attempt.exam for attempt in completed_attempts]
        
        # Calculate average score for completed exams
        average_score = 0
        if completed_attempts:
            total_score = sum(attempt.score or 0 for attempt in completed_attempts)
            average_score = total_score / len(completed_attempts)
        
        return render_template(
            'dashboard/student_dashboard.html',
            available_exams=available_exams,
            completed_exams=completed_exams,
            average_score=average_score
        )


# Teacher routes
@teacher_bp.route('/exams/new', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_exam():
    form = ExamForm()
    # Add dropdown for selecting class
    class_form = AddGroupExamForm(teacher_id=current_user.id)
    
    if form.validate_on_submit() and class_form.validate_on_submit():
        try:
            exam = Exam(
                title=form.title.data,
                description=form.description.data,
                time_limit_minutes=form.time_limit_minutes.data,
                creator_id=current_user.id,
                is_published=form.is_published.data,
                group_id=class_form.group_id.data  # Associate with class
            )
            db.session.add(exam)
            db.session.commit()
            
            flash('Exam created successfully!', 'success')
            return redirect(url_for('teacher.edit_exam', exam_id=exam.id))
        
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('An error occurred while creating the exam.', 'danger')
            # Log the error (for admin/debugging purposes)
            print(f"Error creating exam: {str(e)}")
    
    return render_template('teacher/create_exam.html', form=form, class_form=class_form)


@teacher_bp.route('/exams/<int:exam_id>/edit', methods=['GET', 'POST'])
@login_required
@teacher_required
def edit_exam(exam_id):
    # Use enhanced security verification
    from app.security import verify_exam_owner, log_security_event, security_rate_limiter
    
    # This verifies ownership and returns the exam object
    exam = verify_exam_owner(exam_id)
    
    # Get existing questions
    questions = Question.query.filter_by(exam_id=exam_id).order_by(Question.order).all()
    
    # Form for adding new questions
    form = QuestionForm()
    
    if request.method == 'POST':
        if not form.validate():
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f'{form[field].label.text}: {error}', 'danger')
            return render_template('teacher/edit_exam.html', exam=exam, questions=questions, form=form)
            
        try:
            # Create new question
            question = Question(
                exam_id=exam_id,
                question_text=form.question_text.data,
                question_type=form.question_type.data,
                points=form.points.data,
                order=len(questions) + 1  # Add to the end
            )
            db.session.add(question)
            db.session.flush()  # Flush to get question.id
              # If MCQ, add options
            if form.question_type.data == 'mcq':
                has_correct = False
                option_count = 0
                
                # First verify we have at least 2 valid options and 1 correct
                valid_options = []
                for option_form in form.options:
                    if option_form.option_text.data and option_form.option_text.data.strip():
                        valid_options.append(option_form)
                        if option_form.is_correct.data:
                            has_correct = True
                
                if len(valid_options) < 2:
                    db.session.rollback()
                    flash('MCQ questions must have at least 2 non-empty options', 'danger')
                    return render_template('teacher/edit_exam.html', exam=exam, questions=questions, form=form)
                
                if not has_correct:
                    db.session.rollback()
                    flash('MCQ questions must have at least one correct answer', 'danger')
                    return render_template('teacher/edit_exam.html', exam=exam, questions=questions, form=form)
                
                # Add options to the database
                for option_form in valid_options:
                    option = QuestionOption(
                        question_id=question.id,
                        option_text=option_form.option_text.data.strip(),
                        is_correct=option_form.is_correct.data,
                        order=option_count
                    )
                    db.session.add(option)
                    option_count += 1
            
            db.session.commit()
            flash('Question added successfully!', 'success')
            return redirect(url_for('teacher.edit_exam', exam_id=exam_id))
        
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('An error occurred while adding the question.', 'danger')
            print(f"Error adding question: {str(e)}")
    
    return render_template('teacher/edit_exam.html', exam=exam, questions=questions, form=form)


@teacher_bp.route('/exams/<int:exam_id>/questions/<int:question_id>/delete', methods=['POST'])
@login_required
@teacher_required
def delete_question(exam_id, question_id):
    question = Question.query.get_or_404(question_id)
    
    # Check if current user is the creator of the exam
    if question.exam.creator_id != current_user.id:
        abort(403)
    
    try:
        db.session.delete(question)
        db.session.commit()
        flash('Question deleted successfully!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('An error occurred while deleting the question.', 'danger')
        print(f"Error deleting question: {str(e)}")
    
    return redirect(url_for('teacher.edit_exam', exam_id=exam_id))


@teacher_bp.route('/exams/<int:exam_id>/publish', methods=['POST'])
@login_required
@teacher_required
def publish_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    # Check if current user is the creator
    if exam.creator_id != current_user.id:
        abort(403)
    
    was_already_published = exam.is_published
    exam.is_published = True
    db.session.commit()
    
    # Send notifications only if this is the first time publishing
    if not was_already_published:
        notify_new_exam(exam_id)
    
    flash('Exam published successfully!', 'success')
    return redirect(url_for('teacher.view_exam', exam_id=exam_id))


@teacher_bp.route('/exams/<int:exam_id>/unpublish', methods=['POST'])
@login_required
@teacher_required
def exam_unpublish(exam_id):
    """Unpublish an exam that was previously published"""
    from app.security import verify_exam_owner, log_security_event
    
    exam = verify_exam_owner(exam_id)
    
    if not exam.is_published:
        flash('This exam is already unpublished.', 'warning')
    else:        # Check if there are any completed attempts
        completed_attempts = ExamAttempt.query.filter_by(
            exam_id=exam_id, 
            is_completed=True
        ).count()
        
        if completed_attempts > 0:
            flash('Cannot unpublish an exam that has completed attempts.', 'danger')
        else:
            exam.is_published = False
            db.session.commit()
            
            log_security_event('EXAM_UNPUBLISH', f'Teacher {current_user.id} unpublished exam {exam_id}')
            flash('Exam has been unpublished successfully.', 'success')
    
    return redirect(url_for('teacher.view_exam', exam_id=exam_id))


@teacher_bp.route('/exams/<int:exam_id>', methods=['GET'])
@login_required
@teacher_required
def view_exam(exam_id):
    # Use the enhanced verification function from security.py
    from app.security import verify_exam_owner
    
    # This will verify ownership and return the exam or abort with 403
    exam = verify_exam_owner(exam_id)
    
    # Fetch related data
    questions = Question.query.filter_by(exam_id=exam_id).order_by(Question.order).all()
    attempts = ExamAttempt.query.filter_by(exam_id=exam_id).all()
    
    # Log successful access for audit
    from app.security import log_security_event
    log_security_event('EXAM_ACCESS', f'Teacher {current_user.id} viewed exam {exam_id}')
    
    return render_template(
        'teacher/view_exam.html',
        exam=exam,
        questions=questions,
        attempts=attempts
    )


@teacher_bp.route('/exams/<int:exam_id>/attempts', methods=['GET'])
@login_required
@teacher_required
def view_exam_attempts(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    # Check if current user is the creator
    if exam.creator_id != current_user.id:
        abort(403)
    
    # Get all attempts for this exam
    attempts = ExamAttempt.query.filter_by(exam_id=exam_id).order_by(ExamAttempt.started_at.desc()).all()
    
    # Get student information
    students = {
        attempt.student_id: User.query.get(attempt.student_id).username
        for attempt in attempts
    }
    
    return render_template(
        'teacher/view_attempts.html',
        exam=exam,
        attempts=attempts,
        students=students
    )


@teacher_bp.route('/attempts/<int:attempt_id>/grade', methods=['GET', 'POST'])
@login_required
@teacher_required
def grade_attempt(attempt_id):
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    exam = attempt.exam
    
    # Check if current user is the creator of the exam
    if exam.creator_id != current_user.id:
        abort(403)
    
    # Get all answers for this attempt
    answers = Answer.query.filter_by(attempt_id=attempt_id).all()
    
    # Create a dictionary of forms for grading each non-MCQ answer
    grading_forms = {}
    for answer in answers:
        if answer.question.question_type != 'mcq':
            form = GradeAnswerForm(prefix=f'answer_{answer.id}')
            form.points_awarded.default = answer.question.points if answer.is_correct else 0
            grading_forms[answer.id] = form
    
    if request.method == 'POST':
        try:
            # Process each form and update the answers
            for answer in answers:
                if answer.question.question_type != 'mcq':
                    form = grading_forms[answer.id]
                    if form.validate_on_submit():
                        answer.is_correct = form.is_correct.data
                        
                        # Ensure points_awarded doesn't exceed question's max points
                        max_points = answer.question.points
                        points = min(form.points_awarded.data, max_points)
                        
                        # Save teacher feedback if provided
                        if 'feedback_' + str(answer.id) in request.form:
                            answer.teacher_feedback = request.form['feedback_' + str(answer.id)]
              # Mark attempt as graded
            attempt.is_graded = True
            db.session.commit()
            
            # Notify student that their exam has been graded
            notify_exam_graded(attempt.id)
            
            flash('Grading completed successfully!', 'success')
            return redirect(url_for('teacher.view_exam_attempts', exam_id=exam.id))
        
        except Exception as e:
            db.session.rollback()
            flash('Error while grading: ' + str(e), 'danger')
            print(f"Grading error: {str(e)}")
    else:
        # Pre-populate forms with existing data
        for answer in answers:
            if answer.question.question_type != 'mcq' and answer.id in grading_forms:
                form = grading_forms[answer.id]
                form.is_correct.data = answer.is_correct
                form.points_awarded.data = answer.question.points if answer.is_correct else 0
    
    return render_template(
        'teacher/grade_attempt.html',
        attempt=attempt,
        exam=exam,
        answers=answers,
        grading_forms=grading_forms,
        student=User.query.get(attempt.student_id)
    )


@teacher_bp.route('/exams/<int:exam_id>/analytics', methods=['GET'])
@login_required
@teacher_required
def exam_analytics(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    # Check if current user is the creator
    if exam.creator_id != current_user.id:
        abort(403)
    
    # Get all completed attempts
    attempts = ExamAttempt.query.filter_by(exam_id=exam_id, is_completed=True).all()
    
    if not attempts:
        flash('No attempts have been made on this exam yet.', 'info')
        return redirect(url_for('teacher.view_exam', exam_id=exam_id))
    
    # Calculate analytics
    analytics = {
        'total_attempts': len(attempts),
        'avg_score': 0,
        'highest_score': 0,
        'lowest_score': 100,
        'question_stats': {},
        'completion_times': []
    }
    
    # Get all questions
    questions = Question.query.filter_by(exam_id=exam_id).all()
    
    # Initialize question statistics
    for question in questions:
        analytics['question_stats'][question.id] = {
            'question': question,
            'correct': 0,
            'incorrect': 0,
            'percent_correct': 0
        }
    
    # Process each attempt
    total_score = 0
    for attempt in attempts:
        score = attempt.calculate_score()
        total_score += score['percentage']
        
        if score['percentage'] > analytics['highest_score']:
            analytics['highest_score'] = score['percentage']
        
        if score['percentage'] < analytics['lowest_score']:
            analytics['lowest_score'] = score['percentage']
        
        # Calculate time taken in minutes
        if attempt.completed_at and attempt.started_at:
            time_taken = (attempt.completed_at - attempt.started_at).total_seconds() / 60
            analytics['completion_times'].append({
                'student': User.query.get(attempt.student_id).username,
                'minutes': round(time_taken, 1)
            })
        
        # Process answers for each question
        for answer in attempt.answers:
            if answer.is_correct:
                analytics['question_stats'][answer.question_id]['correct'] += 1
            else:
                analytics['question_stats'][answer.question_id]['incorrect'] += 1
    
    # Calculate averages and percentages
    if analytics['total_attempts'] > 0:
        analytics['avg_score'] = round(total_score / analytics['total_attempts'], 1)
        
        for q_id, stats in analytics['question_stats'].items():
            total = stats['correct'] + stats['incorrect']
            if total > 0:
                stats['percent_correct'] = round((stats['correct'] / total) * 100, 1)
    
    # Sort questions by difficulty (lowest percent correct first)
    sorted_questions = sorted(
        [stats for stats in analytics['question_stats'].values()],
        key=lambda x: x['percent_correct']
    )
    
    return render_template(
        'teacher/exam_analytics.html',
        exam=exam,
        analytics=analytics,
        sorted_questions=sorted_questions
    )


@teacher_bp.route('/exams/<int:exam_id>/reviews', methods=['GET'])
@login_required
@teacher_required
def view_exam_reviews(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    # Check if current user is the creator
    if exam.creator_id != current_user.id:
        abort(403)
    
    # Get all reviews for this exam
    reviews = ExamReview.query.filter_by(exam_id=exam_id).order_by(ExamReview.created_at.desc()).all()
    
    # Calculate review statistics
    stats = {
        'total': len(reviews),
        'average': exam.get_average_rating(),
        'counts': {
            '5': 0, '4': 0, '3': 0, '2': 0, '1': 0
        }
    }
    
    for review in reviews:
        stats['counts'][str(review.rating)] += 1
    
    # Calculate percentages
    if stats['total'] > 0:
        for rating in stats['counts']:
            stats['counts'][rating] = {
                'count': stats['counts'][rating],
                'percent': round((stats['counts'][rating] / stats['total']) * 100)
            }
    
    return render_template(
        'teacher/view_reviews.html',
        exam=exam,
        reviews=reviews,
        stats=stats
    )


@teacher_bp.route('/review-queue', methods=['GET'])
@login_required
@teacher_required
def review_queue():
    """Show all pending submissions that need grading"""
    # Get all completed attempts for exams created by the current teacher
    # that haven't been graded yet (score is None)
    pending_attempts = (ExamAttempt.query
                        .join(Exam, ExamAttempt.exam_id == Exam.id)
                        .filter(Exam.creator_id == current_user.id)
                        .filter(ExamAttempt.status == 'completed')
                        .filter(ExamAttempt.score.is_(None))
                        .order_by(ExamAttempt.submitted_at.desc())
                        .all())
    
    return render_template(
        'teacher/review_queue.html',
        pending_attempts=pending_attempts
    )


@teacher_bp.route('/analytics', methods=['GET'])
@login_required
@teacher_required
def view_analytics():
    """Show overall analytics for all exams created by this teacher"""
    # Get some basic statistics
    total_exams = Exam.query.filter_by(creator_id=current_user.id).count()
    published_exams = Exam.query.filter_by(creator_id=current_user.id, is_published=True).count()
    
    # Get attempt statistics
    attempt_stats = db.session.query(
        func.count(ExamAttempt.id).label('total_attempts'),
        func.count(case([(ExamAttempt.status == 'completed', 1)])).label('completed_attempts'),
        func.avg(ExamAttempt.score).label('average_score')
    ).join(Exam).filter(Exam.creator_id == current_user.id).first()
    
    # Get top performing students
    top_students = db.session.query(
        User.id, 
        User.username,
        func.avg(ExamAttempt.score).label('avg_score'),
        func.count(ExamAttempt.id).label('attempts')
    ).join(ExamAttempt, User.id == ExamAttempt.student_id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .filter(ExamAttempt.score.isnot(None))\
     .group_by(User.id)\
     .order_by(desc('avg_score'))\
     .limit(5)\
     .all()
    
    # Get recent activity
    recent_activity = db.session.query(
        ExamAttempt.id,
        User.username,
        Exam.title,
        ExamAttempt.score,
        ExamAttempt.submitted_at
    ).join(User, ExamAttempt.student_id == User.id)\
     .join(Exam, ExamAttempt.exam_id == Exam.id)\
     .filter(Exam.creator_id == current_user.id)\
     .order_by(ExamAttempt.submitted_at.desc())\
     .limit(10)\
     .all()
    
    return render_template(
        'teacher/analytics_dashboard.html',
        total_exams=total_exams,
        published_exams=published_exams,
        attempt_stats=attempt_stats,
        top_students=top_students,
        recent_activity=recent_activity
    )


@teacher_bp.route('/exams/export', methods=['GET'])
@login_required
@teacher_required
def export_exams():
    """Export all exam data for the current teacher"""
    from io import StringIO
    
    # Security logging
    from app.security import log_security_event
    log_security_event('DATA_EXPORT', f'Teacher {current_user.id} exported exam data')
    
    # Create CSV data
    csv_data = StringIO()
    csv_writer = csv.writer(csv_data)
    
    # Write headers
    csv_writer.writerow(['Exam ID', 'Title', 'Description', 'Time Limit', 'Status', 
                         'Created Date', 'Questions', 'Total Attempts', 'Avg Score'])
    
    # Get all exams for this teacher with stats
    exams = Exam.query.filter_by(creator_id=current_user.id).all()
    
    for exam in exams:
        # Get question count
        question_count = Question.query.filter_by(exam_id=exam.id).count()
          # Get all attempts for this exam
        attempts = ExamAttempt.query.filter_by(exam_id=exam.id, is_completed=True).all()
        attempts_count = len(attempts)
        
        # Calculate average score
        if attempts_count > 0:
            total_score = sum(attempt.calculate_score()['percentage'] for attempt in attempts)
            avg_score = f"{(total_score / attempts_count):.1f}"
        else:
            avg_score = "N/A"
        
        # Format the data
        status = 'Published' if exam.is_published else 'Draft'
        created_date = exam.created_at.strftime('%Y-%m-%d')
          # Write the row
        csv_writer.writerow([
            exam.id, 
            exam.title, 
            exam.description[:50] + '...' if exam.description and len(exam.description) > 50 else exam.description,
            f"{exam.time_limit_minutes} minutes",
            status,
            created_date,
            question_count,
            attempts_count,
            avg_score
        ])
    
    # Prepare the response
    response = make_response(csv_data.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=exam_data.csv'
    response.headers['Content-type'] = 'text/csv'
    return response


@teacher_bp.route('/exams/<int:exam_id>/import-questions', methods=['GET', 'POST'])
@login_required
@teacher_required
def import_questions(exam_id):
    """Import questions from a template file"""
    from app.security import verify_exam_owner
    
    # Verify ownership
    exam = verify_exam_owner(exam_id)
    
    form = ImportQuestionsForm()
    
    if form.validate_on_submit():
        try:
            file_contents = form.template_file.data.read().decode('utf-8')
            
            # Process the CSV file
            from io import StringIO
            
            reader = csv.DictReader(StringIO(file_contents))
            question_count = 0
            
            for row in reader:
                # Create new question
                question = Question(
                    exam_id=exam_id,
                    question_text=row['question_text'],
                    question_type=row['question_type'],
                    points=int(row['points']),
                    order=Question.query.filter_by(exam_id=exam_id).count() + 1
                )
                db.session.add(question)
                db.session.flush()
                
                # If MCQ, add options
                if question.question_type == 'mcq' and 'options' in row:
                    options = row['options'].split('|')
                    correct_answer = int(row.get('correct_answer', 0))
                    
                    for i, option_text in enumerate(options):
                        option = QuestionOption(
                            question_id=question.id,
                            option_text=option_text.strip(),
                            is_correct=(i == correct_answer)
                        )
                        db.session.add(option)
                
                question_count += 1
            
            db.session.commit()
            flash(f'Successfully imported {question_count} questions.', 'success')
            return redirect(url_for('teacher.edit_exam', exam_id=exam_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error importing questions: {str(e)}', 'danger')
    
    return render_template('teacher/import_questions.html', form=form, exam=exam)


@teacher_bp.route('/import-questions-template', methods=['GET'])
@login_required
@teacher_required
def download_template():
    """Download a template CSV file for importing questions"""
    from io import StringIO
    
    # Create CSV template
    csv_data = StringIO()
    csv_writer = csv.writer(csv_data)
    
    # Headers
    csv_writer.writerow(['question_text', 'question_type', 'points', 'options', 'correct_answer'])
    
    # Example rows
    csv_writer.writerow(['What is 2+2?', 'mcq', '5', '2|3|4|5', '2'])
    csv_writer.writerow(['Explain recursion.', 'text', '10', '', ''])
    csv_writer.writerow(['Write a function to calculate factorial.', 'code', '15', '', ''])
    
    # Prepare the response
    response = make_response(csv_data.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=question_template.csv'
    response.headers['Content-type'] = 'text/csv'
    return response


# Route was removed to fix duplicate endpoint error
# Analytics route already defined above at line ~500


# Student routes
@student_bp.route('/exams/<int:exam_id>/take', methods=['GET', 'POST'])
@login_required
@student_required
def take_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    now = datetime.utcnow()
    
    # Check if exam is published
    if not exam.is_published:
        flash('This exam is not available for taking.', 'warning')
        return redirect(url_for('main.dashboard'))
        
    # Check if exam is within availability window
    if exam.available_from and now < exam.available_from:
        flash(f'This exam is not available yet. It will be available from {exam.available_from}.', 'warning')
        return redirect(url_for('main.dashboard'))
        
    if exam.available_until and now > exam.available_until:
        flash('This exam is no longer available.', 'danger')
        return redirect(url_for('main.dashboard'))
        
    # Check if the exam is from a group the student is part of
    if exam.group_id:
        group = Group.query.get(exam.group_id)
        if group and current_user not in group.students:
            flash('You need to join the class to access this exam.', 'warning')
            return redirect(url_for('group.join_group'))
    
    # Check if student has already completed this exam
    existing_attempt = ExamAttempt.query.filter_by(
        student_id=current_user.id,
        exam_id=exam_id,
        is_completed=True
    ).first()
    
    if existing_attempt:
        flash('You have already completed this exam.', 'info')
        return redirect(url_for('student.view_result', attempt_id=existing_attempt.id))
    
    # Get or create an attempt
    attempt = ExamAttempt.query.filter_by(
        student_id=current_user.id,
        exam_id=exam_id,
        is_completed=False
    ).first()
    
    if not attempt:
        attempt = ExamAttempt(
            student_id=current_user.id,
            exam_id=exam_id,
            started_at=datetime.utcnow()
        )
        db.session.add(attempt)
        try:
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error starting exam. Please try again.', 'danger')
            return redirect(url_for('main.dashboard'))
    
    # Create main form for CSRF protection
    form = TakeExamForm()
    
    # Handle AJAX requests for saving answers
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and request.method == 'POST':
        # Validate CSRF token
        if not form.validate_on_submit():
            return jsonify({
                'success': False,
                'message': 'Invalid form submission. Please refresh the page and try again.',
                'error': 'csrf_error'
            }), 400

        if check_time_expired(attempt):
            attempt.is_completed = True
            attempt.submitted_at = datetime.utcnow()
            try:
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
            
            return jsonify({
                'success': False,
                'message': 'Exam time has expired',
                'redirect_url': url_for('student.view_result', attempt_id=attempt.id)
            }), 400

        try:
            # Process form data
            save_answers(request.form, attempt)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Answers saved successfully',
                'saved_at': datetime.utcnow().isoformat()
            })
            
        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"Error saving answers: {str(e)}")
            return jsonify({
                'success': False,
                'message': "Error saving answers. Please try again.",
                'error': 'database_error'
            }), 500

    # Handle final submission
    if request.method == 'POST' and 'submit_exam' in request.form:
        # Validate CSRF token
        if not form.validate_on_submit():
            return jsonify({
                'success': False,
                'message': 'Invalid form submission. Please refresh the page and try again.',
                'error': 'csrf_error'
            }), 400
        
        submission_time = datetime.utcnow()
        
        # Check if exam was already completed (prevent double submission)
        if attempt.is_completed:
            return jsonify({
                'success': False,
                'message': 'This exam has already been submitted.',
                'redirect_url': url_for('student.view_result', attempt_id=attempt.id)
            }), 400
        
        # Validate submission time
        if not validate_submission_time(attempt, submission_time):
            try:
                attempt.is_completed = True
                attempt.submitted_at = submission_time
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Exam submitted (after time limit)',
                    'redirect_url': url_for('student.view_result', attempt_id=attempt.id)
                })
            except SQLAlchemyError as e:
                db.session.rollback()
                print(f"Error submitting exam: {str(e)}")
                return jsonify({
                    'success': False,
                    'message': "Error submitting exam. Please try again.",
                    'error': 'database_error'
                }), 500
        
        try:
            # Save final answers
            save_answers(request.form, attempt)
            
            # Mark attempt as completed
            attempt.is_completed = True
            attempt.submitted_at = submission_time
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Exam submitted successfully',
                'redirect_url': url_for('student.view_result', attempt_id=attempt.id)
            })
            
        except SQLAlchemyError as e:
            db.session.rollback()
            print(f"Error during exam submission: {str(e)}")
            return jsonify({
                'success': False,
                'message': "Error submitting exam. Your answers are saved and you can try submitting again.",
                'error': 'database_error'
            }), 500
    
    # Get all questions
    questions = Question.query.filter_by(exam_id=exam_id).order_by(Question.order).all()
    
    # Prepare forms for each question type
    answer_forms = {}
    existing_answers = {}
    
    # Get existing answers if any
    answers = Answer.query.filter_by(attempt_id=attempt.id).all()
    for answer in answers:
        existing_answers[answer.question_id] = answer
    
    for question in questions:
        if question.question_type == 'mcq':
            form = MCQAnswerForm()
            if question.id in existing_answers:
                form.selected_option.data = existing_answers[question.id].selected_option_id
            answer_forms[question.id] = form
            
        elif question.question_type == 'text':
            form = TextAnswerForm()
            if question.id in existing_answers:
                form.answer_text.data = existing_answers[question.id].text_answer
            answer_forms[question.id] = form
            
        elif question.question_type == 'code':
            form = CodeAnswerForm()
            if question.id in existing_answers:
                answer = existing_answers[question.id]
                form.code_answer.data = getattr(answer, 'code_answer', None) or answer.text_answer
            answer_forms[question.id] = form
    
    # Return the template with all necessary context
    return render_template(
        'student/take_exam.html',
        exam=exam,
        attempt=attempt,
        questions=questions,
        answer_forms=answer_forms,
        form=form  # Main form for CSRF protection
    )


def save_answers(form_data, attempt):
    """
    Save or update answers for an exam attempt
    """
    saved_question_ids = set()
    
    for key, value in form_data.items():
        if key.startswith('question_'):
            try:
                question_id = int(key.split('_')[1])
                saved_question_ids.add(question_id)
                
                question = Question.query.get(question_id)
                if not question:
                    print(f"Warning: Question {question_id} not found")
                    continue
                
                # Get or create answer
                answer = Answer.query.filter_by(
                    attempt_id=attempt.id,
                    question_id=question_id
                ).first()
                
                if not answer:
                    answer = Answer(
                        attempt_id=attempt.id,
                        question_id=question_id
                    )
                    db.session.add(answer)
                
                # Update answer based on question type
                if question.question_type == 'mcq':
                    try:
                        option_id = int(value)
                        # Verify option belongs to question
                        option = QuestionOption.query.filter_by(
                            id=option_id,
                            question_id=question_id
                        ).first()
                        if option:
                            answer.selected_option_id = option_id
                        else:
                            print(f"Warning: Invalid option {option_id} for question {question_id}")
                    except (ValueError, TypeError) as e:
                        print(f"Error processing MCQ answer: {str(e)}")
                        continue
                        
                elif question.question_type in ['text', 'code']:
                    answer.text_answer = value
                    if question.question_type == 'code':
                        answer.code_answer = value
                
                db.session.flush()  # Flush changes for this answer
                
            except (ValueError, TypeError) as e:
                print(f"Error processing answer for key {key}: {str(e)}")
                continue
    
    # Verify all questions were processed
    expected_questions = set(q.id for q in Question.query.filter_by(exam_id=attempt.exam_id).all())
    missing_questions = expected_questions - saved_question_ids
    
    if missing_questions:
        print(f"Warning: Missing answers for questions: {missing_questions}")
    
    return True

@student_bp.route('/exams/get_server_time', methods=['GET'])
@login_required
def get_server_time():
    """Endpoint to synchronize client time with server time."""
    return datetime.utcnow().isoformat()


@main_bp.route('/search')
@login_required
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('main.dashboard'))

    if current_user.is_teacher():
        # Teachers can search their own exams
        exams = Exam.query.filter(
            Exam.creator_id == current_user.id,
            Exam.title.ilike(f'%{query}%')
        ).all()
        template = 'partials/teacher_search_results.html' if request.headers.get('HX-Request') else 'search.html'
        return render_template(template, exams=exams, query=query)
    else:
        # Students can search published exams
        exams = Exam.query.filter(
            Exam.is_published == True,
            Exam.title.ilike(f'%{query}%')
        ).all()
        
        # Get student's attempts for these exams
        attempts = {
            a.exam_id: a for a in ExamAttempt.query.filter(
                ExamAttempt.student_id == current_user.id,
                ExamAttempt.exam_id.in_([e.id for e in exams])
            ).all()
        }
        
        template = 'partials/student_search_results.html' if request.headers.get('HX-Request') else 'search.html'
        return render_template(template, exams=exams, attempts=attempts, query=query)


@main_bp.route('/notifications', methods=['GET', 'POST'])
@login_required
def notifications():
    # Get user's notifications ordered by creation time
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()
    
    mark_all_form = MarkAllReadForm()
    mark_read_form = MarkReadForm()
    
    return render_template('notifications.html', 
                         notifications=notifications,
                         mark_all_form=mark_all_form,
                         mark_read_form=mark_read_form)


@main_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    form = MarkAllReadForm()
    if form.validate_on_submit():
        try:
            Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).update({'is_read': True})
            db.session.commit()
            flash('All notifications marked as read.', 'success')
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error marking notifications as read.', 'danger')
    
    return redirect(url_for('main.notifications'))


@main_bp.route('/notifications/<int:notification_id>/mark-read', methods=['POST'])
@login_required
def mark_read(notification_id):
    form = MarkReadForm()
    if form.validate_on_submit():
        try:
            notification = Notification.query.get_or_404(notification_id)
            if notification.user_id != current_user.id:
                abort(403)
            notification.is_read = True
            db.session.commit()
            flash('Notification marked as read.', 'success')
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error marking notification as read.', 'danger')
    
    return redirect(url_for('main.notifications'))


@student_bp.route('/attempts/<int:attempt_id>/result')
@login_required
@student_required
def view_result(attempt_id):
    # Get the attempt and verify it belongs to the current student
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    
    if attempt.student_id != current_user.id:
        abort(403)
    
    # Get all answers for this attempt
    answers = Answer.query.filter_by(attempt_id=attempt_id).all()
    
    # Calculate the score for this attempt
    score = attempt.calculate_score()
    
    return render_template(
        'student/view_result.html',
        attempt=attempt,
        answers=answers,
        score=score
    )


@main_bp.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    # Gather data for admin control center
    from app.models import User, Exam, ExamAttempt, Notification
    users = User.query.all()
    exams = Exam.query.all()
    attempts = ExamAttempt.query.all()
    notifications = Notification.query.order_by(Notification.created_at.desc()).limit(10).all()
    return render_template('dashboard/admin_dashboard.html', users=users, exams=exams, attempts=attempts, notifications=notifications)

@teacher_bp.route('/gradebook', methods=['GET'])
@login_required
@teacher_required
def gradebook():
    """
    Display gradebook with student scores across all exams or filtered by group/exam
    """
    group_id = request.args.get('group_id', type=int)
    exam_id = request.args.get('exam_id', type=int)
    sort_by = request.args.get('sort', 'name')
    
    # Get groups taught by this teacher
    groups = Group.query.filter_by(teacher_id=current_user.id).all()
    
    # Get exams created by this teacher
    exams_query = Exam.query.filter_by(creator_id=current_user.id)
    
    # Apply group filter if provided
    if group_id:
        group = Group.query.get_or_404(group_id)
        if group.teacher_id != current_user.id:
            flash('You do not have access to this group\'s gradebook.', 'warning')
            return redirect(url_for('teacher.gradebook'))
        
        students = group.students.all()
        exams_query = exams_query.filter_by(group_id=group_id)
    else:
        # Get all students who have taken the teacher's exams
        group = None
        students_query = db.session.query(User).join(
            ExamAttempt, User.id == ExamAttempt.student_id
        ).join(
            Exam, ExamAttempt.exam_id == Exam.id
        ).filter(
            Exam.creator_id == current_user.id,
            User.user_type == 'student'
        ).distinct()
        
        students = students_query.all()
    
    # Apply exam filter if provided
    if exam_id:
        exam = Exam.query.get_or_404(exam_id)
        if exam.creator_id != current_user.id:
            flash('You do not have access to this exam\'s gradebook.', 'warning')
            return redirect(url_for('teacher.gradebook'))
        
        exam_list = [exam]
    else:
        exam_list = exams_query.all()
    
    # Get all attempts for these students and exams
    attempts_query = ExamAttempt.query.join(
        Exam, ExamAttempt.exam_id == Exam.id
    ).filter(
        Exam.creator_id == current_user.id,
        ExamAttempt.student_id.in_([s.id for s in students]) if students else True,
        ExamAttempt.exam_id.in_([e.id for e in exam_list]) if exam_list else True
    )
    
    # Sort students based on sort parameter
    if sort_by == 'name':
        students.sort(key=lambda s: s.username.lower())
    elif sort_by == 'needs_grading':
        # Create a dict to store which students need grading
        needs_grading = {}
        for attempt in attempts_query:
            if not attempt.is_graded and attempt.needs_grading:
                needs_grading[attempt.student_id] = True
        
        # Sort with students needing grading first
        students.sort(key=lambda s: (0 if needs_grading.get(s.id) else 1, s.username.lower()))
    
    # Create a dictionary of attempts for quick lookup
    attempts = {}
    for attempt in attempts_query:
        attempts[(attempt.student_id, attempt.exam_id)] = attempt
    
    return render_template('teacher/gradebook.html',
        students=students,
        exam_list=exam_list,
        attempts=attempts,
        groups=groups,
        exams=Exam.query.filter_by(creator_id=current_user.id).all(),
        group=group,
        exam=Exam.query.get(exam_id) if exam_id else None,
        sort_by=sort_by
    )


@teacher_bp.route('/gradebook/export', methods=['GET'])
@login_required
@teacher_required
def export_gradebook():
    """
    Export gradebook as CSV file
    """
    group_id = request.args.get('group_id', type=int)
    exam_id = request.args.get('exam_id', type=int)
    
    # Build the query based on filters
    exams_query = Exam.query.filter_by(creator_id=current_user.id)
    
    if group_id:
        group = Group.query.get_or_404(group_id)
        if group.teacher_id != current_user.id:
            flash('You do not have access to this group\'s gradebook.', 'warning')
            return redirect(url_for('teacher.gradebook'))
        
        students = group.students.all()
        exams_query = exams_query.filter_by(group_id=group_id)
    else:
        # Get all students who have taken the teacher's exams
        students_query = db.session.query(User).join(
            ExamAttempt, User.id == ExamAttempt.student_id
        ).join(
            Exam, ExamAttempt.exam_id == Exam.id
        ).filter(
            Exam.creator_id == current_user.id,
            User.user_type == 'student'
        ).distinct()
        
        students = students_query.all()
    
    # Apply exam filter if provided
    if exam_id:
        exam = Exam.query.get_or_404(exam_id)
        if exam.creator_id != current_user.id:
            flash('You do not have access to this exam\'s gradebook.', 'warning')
            return redirect(url_for('teacher.gradebook'))
        
        exams = [exam]
    else:
        exams = exams_query.all()
    
    # Get all attempts
    attempts_query = ExamAttempt.query.join(
        Exam, ExamAttempt.exam_id == Exam.id
    ).filter(
        Exam.creator_id == current_user.id,
        ExamAttempt.student_id.in_([s.id for s in students]) if students else True,
        ExamAttempt.exam_id.in_([e.id for e in exams]) if exams else True
    )
    
    # Create a dictionary of attempts for quick lookup
    attempts = {}
    for attempt in attempts_query:
        attempts[(attempt.student_id, attempt.exam_id)] = attempt
    
    # Create CSV response
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header row
    header = ['Student', 'Email']
    for exam in exams:
        header.append(exam.title)
    header.append('Average')
    writer.writerow(header)
    
    # Write data rows
    for student in students:
        row = [student.username, student.email]
        
        # Add scores for each exam
        total_score = 0
        score_count = 0
        
        for exam in exams:
            attempt = attempts.get((student.id, exam.id))
            if attempt and attempt.is_graded:
                row.append(f"{attempt.score:.1f}%")
                total_score += attempt.score
                score_count += 1
            else:
                row.append("Not Attempted" if not attempt else "Needs Grading")
        
        # Calculate average
        if score_count > 0:
            average = total_score / score_count
            row.append(f"{average:.1f}%")
        else:
            row.append("N/A")
        
        writer.writerow(row)
    
    # Set response headers
    from flask import Response
    group_name = Group.query.get(group_id).name if group_id else "All-Classes"
    filename = f"gradebook-{group_name}-{datetime.now().strftime('%Y-%m-%d')}.csv"
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Cache-Control': 'no-cache'
        }
    )
