from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from app.models import db, Group, GroupMembership, User, Exam
from app.forms import CreateGroupForm, JoinGroupForm
from app.decorators import teacher_required

group_bp = Blueprint('group', __name__, url_prefix='/groups')

@group_bp.route('/')
@login_required
def list_groups():
    """List groups based on user role"""
    if current_user.is_teacher():
        # Teachers see groups they created
        groups = Group.query.filter_by(teacher_id=current_user.id).all()
        return render_template('groups/teacher_groups.html', groups=groups)
    else:
        # Students see groups they're members of
        groups = current_user.joined_groups.all()
        return render_template('groups/student_groups.html', groups=groups)

@group_bp.route('/create', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_group():
    """Create a new class group"""
    form = CreateGroupForm()
    
    if form.validate_on_submit():
        try:
            group = Group(
                name=form.name.data,
                description=form.description.data,
                subject=form.subject.data,
                section=form.section.data,
                room=form.room.data,
                teacher_id=current_user.id
            )
            # Generate unique joining code
            group.code = group.generate_code()
            
            db.session.add(group)
            db.session.commit()
            
            flash(f'Class created successfully! Share class code {group.code} with your students.', 'success')
            return redirect(url_for('group.view_group', group_id=group.id))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error creating class. Please try again.', 'danger')
            print(f"Error creating class: {str(e)}")
    
    return render_template('groups/create_group.html', form=form)

@group_bp.route('/<int:group_id>')
@login_required
def view_group(group_id):
    """View class details and stream"""
    group = Group.query.get_or_404(group_id)
    
    # Check if user has access to the group
    if not (current_user.id == group.teacher_id or current_user in group.students):
        flash('You do not have access to this class.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    # Get exams categorized by status
    active_exams = group.get_active_exams()
    upcoming_exams = group.get_upcoming_exams()
    past_exams = group.get_past_exams()
    
    # Get members count
    student_count = group.students.count()
    
    return render_template(
        'groups/view_group.html',
        group=group,
        active_exams=active_exams,
        upcoming_exams=upcoming_exams,
        past_exams=past_exams,
        student_count=student_count,
        is_teacher=current_user.id == group.teacher_id
    )

@group_bp.route('/join', methods=['GET', 'POST'])
@login_required
def join_group():
    """Join a group using a code"""
    if current_user.is_teacher():
        flash('Teachers cannot join groups.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    form = JoinGroupForm()
    
    if form.validate_on_submit():
        group = Group.query.filter_by(code=form.code.data.upper()).first()
        
        if not group:
            flash('Invalid group code.', 'danger')
            return redirect(url_for('group.join_group'))
        
        if current_user in group.members:
            flash('You are already a member of this group.', 'info')
            return redirect(url_for('group.view_group', group_id=group.id))
        
        try:
            group.members.append(current_user)
            db.session.commit()
            flash(f'Successfully joined {group.name}!', 'success')
            return redirect(url_for('group.view_group', group_id=group.id))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error joining group. Please try again.', 'danger')
            print(f"Error joining group: {str(e)}")
    
    return render_template('groups/join_group.html', form=form)

@group_bp.route('/<int:group_id>/leave', methods=['POST'])
@login_required
def leave_group(group_id):
    """Leave a group"""
    if current_user.is_teacher():
        flash('Teachers cannot leave groups.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    group = Group.query.get_or_404(group_id)
    
    if current_user not in group.members:
        flash('You are not a member of this group.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    try:
        group.members.remove(current_user)
        db.session.commit()
        flash(f'Successfully left {group.name}.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('Error leaving group. Please try again.', 'danger')
        print(f"Error leaving group: {str(e)}")
    
    return redirect(url_for('group.list_groups'))

@group_bp.route('/<int:group_id>/members')
@login_required
def list_members(group_id):
    """List all members of a group"""
    group = Group.query.get_or_404(group_id)
    
    # Check if user has access to the group
    if not (current_user.id == group.teacher_id or current_user in group.members):
        flash('You do not have access to this group.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    return render_template(
        'groups/members.html',
        group=group,
        is_teacher=current_user.id == group.teacher_id
    )

@group_bp.route('/<int:group_id>/remove/<int:user_id>', methods=['POST'])
@login_required
@teacher_required
def remove_member(group_id, user_id):
    """Remove a member from the group (teacher only)"""
    group = Group.query.get_or_404(group_id)
    
    # Verify teacher owns the group
    if group.teacher_id != current_user.id:
        flash('You do not have permission to remove members from this group.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    user = User.query.get_or_404(user_id)
    
    try:
        group.members.remove(user)
        db.session.commit()
        flash(f'Successfully removed {user.username} from {group.name}.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('Error removing member. Please try again.', 'danger')
        print(f"Error removing member: {str(e)}")
    
    return redirect(url_for('group.list_members', group_id=group_id))

@group_bp.route('/<int:group_id>/archive', methods=['POST'])
@login_required
@teacher_required
def archive_group(group_id):
    """Archive or unarchive a class group"""
    group = Group.query.get_or_404(group_id)
    
    # Verify teacher owns the group
    if group.teacher_id != current_user.id:
        flash('You do not have permission to archive this class.', 'warning')
        return redirect(url_for('group.list_groups'))
    
    try:
        # Toggle archived status
        group.archived = not group.archived
        db.session.commit()
        status = 'archived' if group.archived else 'unarchived'
        flash(f'Successfully {status} {group.name}.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('Error updating class. Please try again.', 'danger')
        print(f"Error updating class: {str(e)}")
    
    return redirect(url_for('group.view_group', group_id=group.id))
