#!/usr/bin/env python3
"""
User Management Module for Teacher Training System
==================================================

This module handles all user-related operations including:
- User CRUD operations
- User approval workflow
- Authentication helpers
- User statistics and reporting
"""

import sqlite3
import hashlib
from datetime import datetime
from flask import request, session, flash, redirect, url_for, render_template


class UserRepository:
    """Repository class for user database operations."""
    
    def __init__(self, db_connection_func):
        """Initialize with database connection function."""
        self.get_db_connection = db_connection_func
    
    def get_all_users(self):
        """Get all users with enrollment statistics."""
        conn = self.get_db_connection()
        users = conn.execute('''
            SELECT u.*, 
                   COUNT(e.id) as enrollment_count,
                   u2.full_name as approved_by_name
            FROM users u
            LEFT JOIN enrollments e ON u.id = e.user_id AND e.approval_status = 'approved'
            LEFT JOIN users u2 ON u.approved_by = u2.id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        ''').fetchall()
        conn.close()
        return users
    
    def get_user_by_id(self, user_id):
        """Get a single user by ID."""
        conn = self.get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        return user
    
    def get_pending_users(self):
        """Get all users pending approval."""
        conn = self.get_db_connection()
        pending = conn.execute('''
            SELECT * FROM users 
            WHERE approval_status = 'pending'
            ORDER BY created_at ASC
        ''').fetchall()
        conn.close()
        return pending
    
    def create_user(self, username, email, full_name, password, department='', role='teacher', approval_status='pending'):
        """Create a new user."""
        conn = self.get_db_connection()
        
        # Check if user exists
        existing_user = conn.execute(
            'SELECT id FROM users WHERE email = ? OR username = ?',
            (email, username)
        ).fetchone()
        
        if existing_user:
            conn.close()
            return False, 'Email or username already exists.'
        
        # Create new user
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        conn.execute('''
            INSERT INTO users (username, email, full_name, password_hash, department, role, approval_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (username, email, full_name, password_hash, department, role, approval_status))
        
        conn.commit()
        conn.close()
        return True, 'User created successfully.'
    
    def create_comprehensive_user(self, user_data):
        """Create a new user with comprehensive university-style data."""
        conn = self.get_db_connection()
        
        # Check if username or email already exists
        existing = conn.execute(
            'SELECT id FROM users WHERE username = ? OR email = ?',
            (user_data['username'], user_data['email'])
        ).fetchone()
        
        if existing:
            conn.close()
            return False, 'Username or email already exists.'
        
        # Hash password
        password_hash = hashlib.sha256(user_data['password'].encode()).hexdigest()
        
        try:
            # Insert comprehensive user data
            conn.execute('''
                INSERT INTO users (
                    username, email, full_name, password_hash, role, is_active, approval_status,
                    first_name, last_name, date_of_birth, gender, phone_number, address, city,
                    state_province, postal_code, country, nationality, id_number, passport_number,
                    emergency_contact_name, emergency_contact_phone, emergency_contact_relationship,
                    highest_education, institution_name, graduation_year, professional_experience,
                    current_position, organization, years_of_experience, department,
                    preferred_course_id, motivation, how_did_you_hear
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            conn.close()
            return False, f'Registration failed: {str(e)}'
    
    def update_user(self, user_id, username, email, full_name, role, department='', phone='', bio='', is_active=1):
        """Update user information."""
        conn = self.get_db_connection()
        
        # Check if username/email already exists for other users
        existing = conn.execute('''
            SELECT id FROM users 
            WHERE (username = ? OR email = ?) AND id != ?
        ''', (username, email, user_id)).fetchone()
        
        if existing:
            conn.close()
            return False, 'Username or email already exists for another user.'
        
        # Update user
        conn.execute('''
            UPDATE users 
            SET username = ?, email = ?, full_name = ?, role = ?, 
                department = ?, phone = ?, bio = ?, is_active = ?
            WHERE id = ?
        ''', (username, email, full_name, role, department, phone, bio, is_active, user_id))
        
        conn.commit()
        conn.close()
        return True, 'User updated successfully.'
    
    def toggle_user_status(self, user_id):
        """Toggle user active status."""
        conn = self.get_db_connection()
        
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            conn.close()
            return False, 'User not found.'
        
        new_status = 0 if user['is_active'] else 1
        conn.execute('UPDATE users SET is_active = ? WHERE id = ?', (new_status, user_id))
        conn.commit()
        conn.close()
        
        status_text = 'activated' if new_status else 'deactivated'
        return True, f'User "{user["full_name"]}" has been {status_text}.'
    
    def deactivate_user(self, user_id):
        """Soft delete user by deactivating."""
        conn = self.get_db_connection()
        
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            conn.close()
            return False, 'User not found.'
        
        # Soft delete by deactivating the user
        conn.execute('UPDATE users SET is_active = 0 WHERE id = ?', (user_id,))
        
        # Also deactivate their enrollments
        conn.execute('UPDATE enrollments SET is_active = 0 WHERE user_id = ?', (user_id,))
        
        conn.commit()
        conn.close()
        return True, f'User "{user["full_name"]}" has been deactivated successfully.'
    
    def approve_user(self, user_id, approved_by):
        """Approve a user registration."""
        conn = self.get_db_connection()
        
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            conn.close()
            return False, 'User not found.'
        
        # Approve the user
        conn.execute('''
            UPDATE users 
            SET approval_status = 'approved', approved_at = CURRENT_TIMESTAMP, approved_by = ?
            WHERE id = ?
        ''', (approved_by, user_id))
        conn.commit()
        conn.close()
        
        return True, f'User "{user["full_name"]}" approved successfully!'
    
    def reject_user(self, user_id, rejected_by):
        """Reject a user registration."""
        conn = self.get_db_connection()
        
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        if not user:
            conn.close()
            return False, 'User not found.'
        
        # Reject the user
        conn.execute('''
            UPDATE users 
            SET approval_status = 'rejected', approved_at = CURRENT_TIMESTAMP, approved_by = ?
            WHERE id = ?
        ''', (rejected_by, user_id))
        conn.commit()
        conn.close()
        
        return True, f'User "{user["full_name"]}" registration rejected.'
    
    def bulk_approve_users(self, user_ids, approved_by):
        """Approve multiple user registrations."""
        if not user_ids:
            return False, 'No users selected.'
        
        conn = self.get_db_connection()
        
        for user_id in user_ids:
            conn.execute('''
                UPDATE users 
                SET approval_status = 'approved', approved_at = CURRENT_TIMESTAMP, approved_by = ?
                WHERE id = ? AND approval_status = 'pending'
            ''', (approved_by, user_id))
        
        conn.commit()
        conn.close()
        
        return True, f'Approved {len(user_ids)} user registrations!'
    
    def authenticate_user(self, email, password):
        """Authenticate user login."""
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        
        conn = self.get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE email = ? AND password_hash = ? AND is_active = 1',
            (email, password_hash)
        ).fetchone()
        conn.close()
        
        return user
    
    def update_last_login(self, user_id):
        """Update user's last login timestamp."""
        conn = self.get_db_connection()
        conn.execute(
            'UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?',
            (user_id,)
        )
        conn.commit()
        conn.close()
    
    def get_user_statistics(self):
        """Get user statistics for dashboard."""
        conn = self.get_db_connection()
        
        stats = {
            'total_users': conn.execute('SELECT COUNT(*) as count FROM users').fetchone()['count'],
            'active_users': conn.execute('SELECT COUNT(*) as count FROM users WHERE is_active = 1').fetchone()['count'],
            'pending_users': conn.execute('SELECT COUNT(*) as count FROM users WHERE approval_status = "pending"').fetchone()['count'],
            'approved_users': conn.execute('SELECT COUNT(*) as count FROM users WHERE approval_status = "approved"').fetchone()['count'],
            'rejected_users': conn.execute('SELECT COUNT(*) as count FROM users WHERE approval_status = "rejected"').fetchone()['count'],
        }
        
        conn.close()
        return stats


class UserManager:
    """Main user management class that handles business logic and Flask routes."""
    
    def __init__(self, app, db_connection_func):
        """Initialize with Flask app and database connection function."""
        self.app = app
        self.user_repo = UserRepository(db_connection_func)
        self._register_routes()
    
    def _register_routes(self):
        """Register all user management routes with the Flask app."""
        
        @self.app.route('/admin/users')
        def admin_users():
            """Admin user management - view all users."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            users = self.user_repo.get_all_users()
            return render_template('admin_users.html', users=users)
        
        @self.app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
        def edit_user(user_id):
            """Edit user details."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            if request.method == 'POST':
                username = request.form['username']
                email = request.form['email']
                full_name = request.form['full_name']
                role = request.form['role']
                department = request.form.get('department', '')
                phone = request.form.get('phone', '')
                bio = request.form.get('bio', '')
                is_active = 1 if request.form.get('is_active') else 0
                
                success, message = self.user_repo.update_user(
                    user_id, username, email, full_name, role, 
                    department, phone, bio, is_active
                )
                
                if success:
                    flash(message, 'success')
                    return redirect(url_for('admin_users'))
                else:
                    flash(message, 'error')
                    return redirect(url_for('edit_user', user_id=user_id))
            
            user = self.user_repo.get_user_by_id(user_id)
            if not user:
                flash('User not found.', 'error')
                return redirect(url_for('admin_users'))
            
            return render_template('edit_user.html', user=user)
        
        @self.app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
        def delete_user(user_id):
            """Delete a user (soft delete by deactivating)."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            if user_id == session['user_id']:
                flash('You cannot delete your own account.', 'error')
                return redirect(url_for('admin_users'))
            
            success, message = self.user_repo.deactivate_user(user_id)
            flash(message, 'success' if success else 'error')
            return redirect(url_for('admin_users'))
        
        @self.app.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
        def toggle_user_status(user_id):
            """Toggle user active status."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            if user_id == session['user_id']:
                flash('You cannot modify your own account status.', 'error')
                return redirect(url_for('admin_users'))
            
            success, message = self.user_repo.toggle_user_status(user_id)
            flash(message, 'success' if success else 'error')
            return redirect(url_for('admin_users'))
        
        @self.app.route('/admin/pending-users')
        def pending_users():
            """View and manage pending user registrations."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            pending = self.user_repo.get_pending_users()
            user_stats = self.user_repo.get_user_statistics()
            return render_template('pending_users.html', pending=pending, user_stats=user_stats)
        
        @self.app.route('/admin/approve-user/<int:user_id>', methods=['POST'])
        def approve_user(user_id):
            """Approve a user registration."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            success, message = self.user_repo.approve_user(user_id, session['user_id'])
            flash(message, 'success' if success else 'error')
            return redirect(url_for('pending_users'))
        
        @self.app.route('/admin/reject-user/<int:user_id>', methods=['POST'])
        def reject_user(user_id):
            """Reject a user registration."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            success, message = self.user_repo.reject_user(user_id, session['user_id'])
            flash(message, 'warning' if success else 'error')
            return redirect(url_for('pending_users'))
        
        @self.app.route('/admin/bulk-approve-users', methods=['POST'])
        def bulk_approve_users():
            """Approve multiple user registrations."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            user_ids = request.form.getlist('user_ids')
            success, message = self.user_repo.bulk_approve_users(user_ids, session['user_id'])
            flash(message, 'success' if success else 'warning')
            return redirect(url_for('pending_users'))
    
    def _check_admin_access(self):
        """Check if current user has admin access."""
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return False
        
        if session.get('role') != 'admin':
            flash('Access denied. Admin privileges required.', 'error')
            return False
        
        return True
    
    def register_user(self, username, email, full_name, password, department=''):
        """Register a new user (public registration) - approved for login but restricted course access."""
        return self.user_repo.create_user(
            username, email, full_name, password, department, 'teacher', 'approved'
        )
    
    def register_comprehensive_user(self, user_data):
        """Register a new user with comprehensive university-style data."""
        return self.user_repo.create_comprehensive_user(user_data)
    
    def login_user(self, email, password):
        """Handle user login with approval status checking."""
        user = self.user_repo.authenticate_user(email, password)
        
        if not user:
            return False, 'Invalid email or password.', None
        
        # All users can login, but access to course content is controlled separately
        # Update last login
        self.user_repo.update_last_login(user['id'])
        
        # Admin users are automatically approved and don't need approval checks
        if user['role'] == 'admin':
            # Ensure admin is always approved
            if user['approval_status'] != 'approved':
                self.user_repo.approve_user(user['id'], user['id'])  # Self-approve
            message = f'Welcome back, Administrator {user["full_name"]}!'
            return True, message, user
        
        # Check approval status for non-admin users
        approval_status = user['approval_status'] if user['approval_status'] else 'approved'
        
        if approval_status == 'pending':
            message = f'Welcome, {user["full_name"]}! Your account is pending admin approval for full course access.'
        elif approval_status == 'rejected':
            message = f'Welcome, {user["full_name"]}! Please contact administrator regarding your account status.'
        else:
            message = f'Welcome back, {user["full_name"]}!'
        
        return True, message, user
    
    def get_user_statistics(self):
        """Get user statistics for admin dashboard."""
        return self.user_repo.get_user_statistics()


def create_user_manager(app, db_connection_func):
    """Factory function to create and configure user manager."""
    return UserManager(app, db_connection_func)
