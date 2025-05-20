from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from app.models import db, User, Exam, ExamAttempt
from app.forms import UserEditForm, CreateUserForm, ExamForm
from werkzeug.security import generate_password_hash
from functools import wraps

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = UserEditForm(obj=user)
    
    if form.validate_on_submit():
        if user.user_type == 'admin' and not current_user.id == user.id:
            flash('Cannot modify another admin user.', 'danger')
            return redirect(url_for('main.admin_dashboard'))
        
        try:
            user.username = form.username.data
            user.email = form.email.data
            user.user_type = form.user_type.data
            db.session.commit()
            flash('User updated successfully!', 'success')
            return redirect(url_for('main.admin_dashboard'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error updating user.', 'danger')
    
    return render_template('admin/edit_user.html', form=form, user=user)

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.user_type == 'admin':
        flash('Cannot delete admin users.', 'danger')
        return redirect(url_for('main.admin_dashboard'))
    
    if user.id == current_user.id:
        flash('Cannot delete your own account.', 'danger')
        return redirect(url_for('main.admin_dashboard'))
    
    try:
        # Delete related records first
        ExamAttempt.query.filter_by(student_id=user.id).delete()
        Exam.query.filter_by(creator_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('Error deleting user.', 'danger')
    
    return redirect(url_for('main.admin_dashboard'))

@admin_bp.route('/exams/<int:exam_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    try:
        # Delete all related attempts first
        ExamAttempt.query.filter_by(exam_id=exam.id).delete()
        db.session.delete(exam)
        db.session.commit()
        flash('Exam deleted successfully!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('Error deleting exam.', 'danger')
    
    return redirect(url_for('main.admin_dashboard'))

@admin_bp.route('/exams/<int:exam_id>/toggle-publish', methods=['POST'])
@login_required
@admin_required
def toggle_exam_publish(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    
    try:
        exam.is_published = not exam.is_published
        db.session.commit()
        status = 'published' if exam.is_published else 'unpublished'
        flash(f'Exam {status} successfully!', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('Error updating exam status.', 'danger')
    
    return redirect(url_for('main.admin_dashboard'))

@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    form = CreateUserForm()
    if form.validate_on_submit():
        try:
            # Check if username or email already exists
            if User.query.filter_by(username=form.username.data).first():
                flash('Username already exists.', 'danger')
                return render_template('admin/create_user.html', form=form)
            
            if User.query.filter_by(email=form.email.data).first():
                flash('Email already exists.', 'danger')
                return render_template('admin/create_user.html', form=form)
            
            user = User(
                username=form.username.data,
                email=form.email.data,
                user_type=form.user_type.data,
                password_hash=generate_password_hash(form.password.data)
            )
            db.session.add(user)
            db.session.commit()
            flash('User created successfully!', 'success')
            return redirect(url_for('main.admin_dashboard'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error creating user.', 'danger')
    
    return render_template('admin/create_user.html', form=form)

@admin_bp.route('/exams/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_exam():
    form = ExamForm()
    if form.validate_on_submit():
        try:
            exam = Exam(
                title=form.title.data,
                description=form.description.data,
                time_limit_minutes=form.time_limit_minutes.data,
                creator_id=current_user.id,
                is_published=form.is_published.data
            )
            db.session.add(exam)
            db.session.commit()
            flash('Exam created successfully!', 'success')
            return redirect(url_for('main.admin_dashboard'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error creating exam.', 'danger')
    
    return render_template('admin/create_exam.html', form=form)
