"""
Registration Management Module for Teacher Training System

This module handles all aspects of user registration including:
- University-style comprehensive registration forms
- Course selection during registration
- User profile management
- Registration validation and processing
"""

import sqlite3
import hashlib
import re
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, session


class RegistrationRepository:
    """Repository class for handling registration-related database operations."""
    
    def __init__(self, db_connection_func):
        """Initialize with database connection function."""
        self.get_db_connection = db_connection_func
    
    def validate_registration_data(self, user_data):
        """Validate registration data before processing."""
        errors = []
        
        # Required field validation
        required_fields = ['username', 'email', 'first_name', 'last_name', 'password', 'phone_number']
        for field in required_fields:
            if not user_data.get(field, '').strip():
                errors.append(f'{field.replace("_", " ").title()} is required')
        
        # Email validation
        email = user_data.get('email', '')
        if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append('Please enter a valid email address')
        
        # Username validation
        username = user_data.get('username', '')
        if username and len(username) < 3:
            errors.append('Username must be at least 3 characters long')
        if username and not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append('Username can only contain letters, numbers, and underscores')
        
        # Password validation
        password = user_data.get('password', '')
        if password and len(password) < 8:
            errors.append('Password must be at least 8 characters long')
        
        # Phone number validation
        phone = user_data.get('phone_number', '')
        if phone and not re.match(r'^[\+]?[0-9\s\-\(\)]{10,15}$', phone):
            errors.append('Please enter a valid phone number')
        
        # ID number validation (if provided)
        id_number = user_data.get('id_number', '')
        if id_number and not re.match(r'^[0-9]{7,8}$', id_number):
            errors.append('National ID number should be 7-8 digits')
        
        return errors
    
    def check_existing_user(self, username, email):
        """Check if username or email already exists."""
        conn = self.get_db_connection()
        
        existing = conn.execute(
            'SELECT username, email FROM users WHERE username = ? OR email = ?',
            (username, email)
        ).fetchone()
        
        conn.close()
        
        if existing:
            if existing['username'] == username:
                return 'Username already exists'
            if existing['email'] == email:
                return 'Email address already exists'
        
        return None
    
    def create_comprehensive_user(self, user_data):
        """Create a new user with comprehensive university-style data."""
        # Validate data first
        validation_errors = self.validate_registration_data(user_data)
        if validation_errors:
            return False, '; '.join(validation_errors)
        
        # Check for existing user
        existing_error = self.check_existing_user(user_data['username'], user_data['email'])
        if existing_error:
            return False, existing_error
        
        conn = self.get_db_connection()
        
        try:
            # Hash password
            password_hash = hashlib.sha256(user_data['password'].encode()).hexdigest()
            
            # Insert comprehensive user data
            conn.execute('''
                INSERT INTO users (
                    username, email, full_name, password_hash, role, is_active, approval_status,
                    first_name, last_name, date_of_birth, gender, phone_number, address, city,
                    state_province, postal_code, country, nationality, id_number, passport_number,
                    emergency_contact_name, emergency_contact_phone, emergency_contact_relationship,
                    highest_education, institution_name, graduation_year, professional_experience,
                    current_position, organization, years_of_experience, department,
                    preferred_course_id, motivation, how_did_you_hear, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                user_data['username'], user_data['email'], user_data['full_name'], 
                password_hash, 'teacher', 1, 'approved',
                user_data.get('first_name'), user_data.get('last_name'), 
                user_data.get('date_of_birth'), user_data.get('gender'),
                user_data.get('phone_number'), user_data.get('address'), 
                user_data.get('city'), user_data.get('state_province'),
                user_data.get('postal_code'), user_data.get('country'), 
                user_data.get('nationality'), user_data.get('id_number'),
                user_data.get('passport_number'), user_data.get('emergency_contact_name'),
                user_data.get('emergency_contact_phone'), user_data.get('emergency_contact_relationship'),
                user_data.get('highest_education'), user_data.get('institution_name'),
                user_data.get('graduation_year'), user_data.get('professional_experience'),
                user_data.get('current_position'), user_data.get('organization'),
                user_data.get('years_of_experience'), user_data.get('department'),
                user_data.get('preferred_course_id'), user_data.get('motivation'),
                user_data.get('how_did_you_hear')
            ))
            
            user_id = conn.lastrowid
            
            # If user selected a preferred course, automatically enroll them (pending approval)
            if user_data.get('preferred_course_id'):
                conn.execute('''
                    INSERT INTO enrollments (user_id, course_id, approval_status, enrolled_at)
                    VALUES (?, ?, 'pending', CURRENT_TIMESTAMP)
                ''', (user_id, user_data['preferred_course_id']))
            
            conn.commit()
            conn.close()
            
            return True, f'Registration successful for "{user_data["full_name"]}". Your account and course enrollment are pending admin approval.'
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'Registration failed: {str(e)}'
    
    def get_available_courses(self):
        """Get all published courses available for registration."""
        conn = self.get_db_connection()
        
        courses = conn.execute('''
            SELECT id, title, description, category, level, duration_hours 
            FROM courses 
            WHERE is_published = 1 
            ORDER BY title
        ''').fetchall()
        
        conn.close()
        return [dict(course) for course in courses]
    
    def get_user_profile(self, user_id):
        """Get comprehensive user profile data."""
        conn = self.get_db_connection()
        
        user = conn.execute('''
            SELECT u.*, c.title as preferred_course_title
            FROM users u
            LEFT JOIN courses c ON u.preferred_course_id = c.id
            WHERE u.id = ?
        ''', (user_id,)).fetchone()
        
        conn.close()
        return dict(user) if user else None
    
    def update_user_profile(self, user_id, profile_data):
        """Update user profile with new information."""
        conn = self.get_db_connection()
        
        try:
            conn.execute('''
                UPDATE users SET
                    first_name = ?, last_name = ?, full_name = ?, phone_number = ?,
                    address = ?, city = ?, state_province = ?, postal_code = ?,
                    country = ?, nationality = ?, emergency_contact_name = ?,
                    emergency_contact_phone = ?, emergency_contact_relationship = ?,
                    highest_education = ?, institution_name = ?, graduation_year = ?,
                    professional_experience = ?, current_position = ?, organization = ?,
                    years_of_experience = ?, department = ?
                WHERE id = ?
            ''', (
                profile_data.get('first_name'), profile_data.get('last_name'),
                profile_data.get('full_name'), profile_data.get('phone_number'),
                profile_data.get('address'), profile_data.get('city'),
                profile_data.get('state_province'), profile_data.get('postal_code'),
                profile_data.get('country'), profile_data.get('nationality'),
                profile_data.get('emergency_contact_name'), profile_data.get('emergency_contact_phone'),
                profile_data.get('emergency_contact_relationship'), profile_data.get('highest_education'),
                profile_data.get('institution_name'), profile_data.get('graduation_year'),
                profile_data.get('professional_experience'), profile_data.get('current_position'),
                profile_data.get('organization'), profile_data.get('years_of_experience'),
                profile_data.get('department'), user_id
            ))
            
            conn.commit()
            conn.close()
            return True, 'Profile updated successfully'
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'Profile update failed: {str(e)}'


class RegistrationManager:
    """Manager class for handling registration routes and business logic."""
    
    def __init__(self, app, db_connection_func):
        """Initialize with Flask app and database connection function."""
        self.app = app
        self.registration_repo = RegistrationRepository(db_connection_func)
        self._register_routes()
    
    def _register_routes(self):
        """Register all registration-related routes with the Flask app."""
        
        @self.app.route('/complete-registration', methods=['GET', 'POST'])
        def complete_registration():
            """Comprehensive post-signup registration inside the system (requires login)."""
            if 'user_id' not in session:
                flash('Please log in to complete your registration.', 'error')
                return redirect(url_for('login'))

            if request.method == 'POST':
                # Build full name from first and last name
                first_name = request.form.get('first_name', '')
                last_name = request.form.get('last_name', '')
                full_name = f"{first_name} {last_name}".strip()

                profile_data = {
                    'first_name': first_name,
                    'last_name': last_name,
                    'full_name': full_name,
                    'phone_number': request.form.get('phone_number'),
                    'address': request.form.get('address'),
                    'city': request.form.get('city'),
                    'state_province': request.form.get('state_province'),
                    'postal_code': request.form.get('postal_code'),
                    'country': request.form.get('country', 'Kenya'),
                    'nationality': request.form.get('nationality'),
                    'emergency_contact_name': request.form.get('emergency_contact_name'),
                    'emergency_contact_phone': request.form.get('emergency_contact_phone'),
                    'emergency_contact_relationship': request.form.get('emergency_contact_relationship'),
                    'highest_education': request.form.get('highest_education'),
                    'institution_name': request.form.get('institution_name'),
                    'graduation_year': self._safe_int(request.form.get('graduation_year')),
                    'professional_experience': request.form.get('professional_experience'),
                    'current_position': request.form.get('current_position'),
                    'organization': request.form.get('organization'),
                    'years_of_experience': self._safe_int(request.form.get('years_of_experience')),
                    'department': request.form.get('department')
                }

                success, message = self.registration_repo.update_user_profile(session['user_id'], profile_data)

                # Handle preferred course selection -> create pending enrollment request
                preferred_course_id = self._safe_int(request.form.get('preferred_course_id'))
                if preferred_course_id:
                    try:
                        conn = self.registration_repo.get_db_connection()
                        # Check if enrollment already exists
                        existing = conn.execute(
                            'SELECT id FROM enrollments WHERE user_id = ? AND course_id = ?',
                            (session['user_id'], preferred_course_id)
                        ).fetchone()
                        if not existing:
                            conn.execute('''
                                INSERT INTO enrollments (user_id, course_id, approval_status, enrolled_at)
                                VALUES (?, ?, 'pending', CURRENT_TIMESTAMP)
                            ''', (session['user_id'], preferred_course_id))
                            conn.commit()
                        conn.close()
                    except Exception as e:
                        flash(f'Could not submit course selection: {str(e)}', 'warning')

                flash('Your registration details have been saved. Await admin approval for course access.', 'success' if success else 'error')
                return redirect(url_for('dashboard'))

            # GET: render form with internal flag and current user data
            user_profile = self.registration_repo.get_user_profile(session['user_id'])
            return render_template('register_comprehensive.html', internal=True, user=user_profile)
        
        @self.app.route('/api/courses')
        def api_courses():
            """API endpoint to get available courses for registration."""
            courses = self.registration_repo.get_available_courses()
            return jsonify(courses)
        
        @self.app.route('/profile')
        def profile():
            """User profile page."""
            if 'user_id' not in session:
                flash('Please log in to view your profile.', 'error')
                return redirect(url_for('login'))
            
            user_profile = self.registration_repo.get_user_profile(session['user_id'])
            if not user_profile:
                flash('Profile not found.', 'error')
                return redirect(url_for('dashboard'))
            
            return render_template('user_profile.html', user=user_profile)
        
        @self.app.route('/profile/edit', methods=['GET', 'POST'])
        def edit_profile():
            """Edit user profile page."""
            if 'user_id' not in session:
                flash('Please log in to edit your profile.', 'error')
                return redirect(url_for('login'))
            
            if request.method == 'POST':
                # Build full name from first and last name
                first_name = request.form.get('first_name', '')
                last_name = request.form.get('last_name', '')
                full_name = f"{first_name} {last_name}".strip()
                
                profile_data = {
                    'first_name': first_name,
                    'last_name': last_name,
                    'full_name': full_name,
                    'phone_number': request.form.get('phone_number'),
                    'address': request.form.get('address'),
                    'city': request.form.get('city'),
                    'state_province': request.form.get('state_province'),
                    'postal_code': request.form.get('postal_code'),
                    'country': request.form.get('country'),
                    'nationality': request.form.get('nationality'),
                    'emergency_contact_name': request.form.get('emergency_contact_name'),
                    'emergency_contact_phone': request.form.get('emergency_contact_phone'),
                    'emergency_contact_relationship': request.form.get('emergency_contact_relationship'),
                    'highest_education': request.form.get('highest_education'),
                    'institution_name': request.form.get('institution_name'),
                    'graduation_year': self._safe_int(request.form.get('graduation_year')),
                    'professional_experience': request.form.get('professional_experience'),
                    'current_position': request.form.get('current_position'),
                    'organization': request.form.get('organization'),
                    'years_of_experience': self._safe_int(request.form.get('years_of_experience')),
                    'department': request.form.get('department')
                }
                
                success, message = self.registration_repo.update_user_profile(session['user_id'], profile_data)
                flash(message, 'success' if success else 'error')
                
                if success:
                    return redirect(url_for('profile'))
            
            user_profile = self.registration_repo.get_user_profile(session['user_id'])
            if not user_profile:
                flash('Profile not found.', 'error')
                return redirect(url_for('dashboard'))
            
            return render_template('edit_profile.html', user=user_profile)
    
    def _safe_int(self, value, default=None):
        """Safely convert value to integer."""
        try:
            return int(value) if value else default
        except (ValueError, TypeError):
            return default


def create_registration_manager(app, db_connection_func):
    """Factory function to create and configure RegistrationManager."""
    return RegistrationManager(app, db_connection_func)
