from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, session
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.urls import url_parse

from app.models import db, User
from app.forms import LoginForm, RegistrationForm
from app.security import ip_rate_limit, reset_login_attempts

# Create a Blueprint for authentication
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
@ip_rate_limit()
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        # Check if user exists and password is valid
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password', 'danger')
            return render_template('auth/login.html', form=form)
        
        try:
            # User authentication successful
            login_user(user, remember=form.remember_me.data)
            
            # Reset rate limiting for this IP on successful login
            reset_login_attempts(request.remote_addr)
            
            # Store user information in session
            session['user_id'] = user.id
            session['username'] = user.username
            session['user_type'] = user.user_type
            
            # Redirect user to the page they were trying to access
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('main.dashboard')
            
            return redirect(next_page)
        except Exception as e:
            flash(f'Error during login: {str(e)}', 'danger')
            print(f"Login error: {str(e)}")
            return render_template('auth/login.html', form=form)
    
    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    # Clear all session data
    session.clear()
    logout_user()
    flash('You have been logged out', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            user_type=form.user_type.data  # Only 'teacher' or 'admin' allowed
        )
        user.set_password(form.password.data)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('Error during registration. Please try again.', 'danger')
            # Log the error for administrator review (not shown to user)
            print(f"Registration error: {str(e)}")
    
    return render_template('auth/register.html', form=form)