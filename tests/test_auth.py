import pytest
from app.models import User

def test_register_and_login(client, app):
    # Register a new user
    response = client.post('/register', data={
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password': 'newpassword123',
        'confirm_password': 'newpassword123'
    }, follow_redirects=True)
    assert b'Registration successful' in response.data

    # Login with the new user
    response = client.post('/login', data={
        'username': 'newuser',
        'password': 'newpassword123'
    }, follow_redirects=True)
    assert b'dashboard' in response.data or b'Logout' in response.data


def test_invalid_login(client, app, student_user):
    # Wrong password
    response = client.post('/login', data={
        'username': 'student',
        'password': 'wrongpassword'
    }, follow_redirects=True)
    assert b'Invalid username or password' in response.data

    # Nonexistent user
    response = client.post('/login', data={
        'username': 'ghost',
        'password': 'irrelevant'
    }, follow_redirects=True)
    assert b'Invalid username or password' in response.data


def test_logout(client, app, student_user):
    # Login first
    client.post('/login', data={
        'username': 'student',
        'password': 'password'
    }, follow_redirects=True)
    # Logout
    response = client.get('/logout', follow_redirects=True)
    assert b'logged out' in response.data or b'Login' in response.data
