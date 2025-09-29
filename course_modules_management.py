"""
Course Modules Management System for Teacher Training System

This module handles all aspects of course modules/lessons including:
- Module creation, editing, and deletion
- Module content management with rich features
- Module sequencing and organization
- Student progress tracking
- Module access control
- Interactive module types (text, video, quiz, assignment, etc.)
"""

import sqlite3
import json
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, session


class CourseModulesRepository:
    """Repository class for handling course modules database operations."""
    
    def __init__(self, db_connection_func):
        """Initialize with database connection function."""
        self.get_db_connection = db_connection_func
    
    def get_course_modules(self, course_id):
        """Get all modules for a specific course."""
        conn = self.get_db_connection()
        
        modules = conn.execute('''
            SELECT l.*, 
                   COUNT(DISTINCT up.user_id) as students_completed,
                   AVG(up.time_spent) as avg_time_spent
            FROM lessons l
            LEFT JOIN user_progress up ON l.id = up.lesson_id AND up.completed = 1
            WHERE l.course_id = ?
            GROUP BY l.id
            ORDER BY l.lesson_order
        ''', (course_id,)).fetchall()
        
        conn.close()
        return [dict(module) for module in modules]
    
    def get_module_by_id(self, module_id):
        """Get a specific module by ID with detailed information."""
        conn = self.get_db_connection()
        
        module = conn.execute('''
            SELECT l.*, c.title as course_title, c.id as course_id,
                   COUNT(DISTINCT up.user_id) as students_completed,
                   AVG(up.time_spent) as avg_time_spent
            FROM lessons l
            JOIN courses c ON l.course_id = c.id
            LEFT JOIN user_progress up ON l.id = up.lesson_id AND up.completed = 1
            WHERE l.id = ?
            GROUP BY l.id
        ''', (module_id,)).fetchone()
        
        conn.close()
        return dict(module) if module else None
    
    def create_module(self, course_id, module_data):
        """Create a new course module."""
        conn = self.get_db_connection()
        
        try:
            # Get the next lesson order
            max_order = conn.execute(
                'SELECT MAX(lesson_order) as max_order FROM lessons WHERE course_id = ?',
                (course_id,)
            ).fetchone()
            
            next_order = (max_order['max_order'] or 0) + 1
            
            # Insert the new module
            cursor = conn.execute('''
                INSERT INTO lessons (
                    title, content, lesson_type, duration_minutes, lesson_order, 
                    course_id, learning_objectives, additional_resources, 
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                module_data['title'], module_data['content'], 
                module_data['lesson_type'], module_data.get('duration_minutes'),
                next_order, course_id, 
                module_data.get('learning_objectives'), 
                module_data.get('additional_resources')
            ))
            
            module_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return True, f'Module "{module_data["title"]}" created successfully.', module_id
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'Failed to create module: {str(e)}', None
    
    def update_module(self, module_id, module_data):
        """Update an existing module."""
        conn = self.get_db_connection()
        
        try:
            conn.execute('''
                UPDATE lessons 
                SET title = ?, content = ?, lesson_type = ?, duration_minutes = ?,
                    learning_objectives = ?, additional_resources = ?
                WHERE id = ?
            ''', (
                module_data['title'], module_data['content'],
                module_data['lesson_type'], module_data.get('duration_minutes'),
                module_data.get('learning_objectives'), 
                module_data.get('additional_resources'),
                module_id
            ))
            
            conn.commit()
            conn.close()
            
            return True, 'Module updated successfully.'
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'Failed to update module: {str(e)}'
    
    def delete_module(self, module_id):
        """Delete a module and all related progress data."""
        conn = self.get_db_connection()
        
        try:
            # Get module info for confirmation
            module = conn.execute(
                'SELECT title, course_id FROM lessons WHERE id = ?', 
                (module_id,)
            ).fetchone()
            
            if not module:
                conn.close()
                return False, 'Module not found.'
            
            # Delete user progress for this module
            conn.execute('DELETE FROM user_progress WHERE lesson_id = ?', (module_id,))
            
            # Delete the module
            conn.execute('DELETE FROM lessons WHERE id = ?', (module_id,))
            
            # Reorder remaining modules
            modules = conn.execute('''
                SELECT id FROM lessons WHERE course_id = ? ORDER BY lesson_order
            ''', (module['course_id'],)).fetchall()
            
            for i, mod in enumerate(modules, 1):
                conn.execute(
                    'UPDATE lessons SET lesson_order = ? WHERE id = ?',
                    (i, mod['id'])
                )
            
            conn.commit()
            conn.close()
            
            return True, f'Module "{module["title"]}" deleted successfully.'
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'Failed to delete module: {str(e)}'
    
    def reorder_modules(self, course_id, module_order):
        """Reorder modules in a course."""
        conn = self.get_db_connection()
        
        try:
            for order, module_id in enumerate(module_order, 1):
                conn.execute(
                    'UPDATE lessons SET lesson_order = ? WHERE id = ? AND course_id = ?',
                    (order, module_id, course_id)
                )
            
            conn.commit()
            conn.close()
            
            return True, 'Modules reordered successfully.'
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'Failed to reorder modules: {str(e)}'
    
    def duplicate_module(self, module_id):
        """Create a duplicate of an existing module."""
        conn = self.get_db_connection()
        
        try:
            # Get original module data
            original = conn.execute(
                'SELECT * FROM lessons WHERE id = ?', 
                (module_id,)
            ).fetchone()
            
            if not original:
                conn.close()
                return False, 'Module not found.', None
            
            # Get next order number
            max_order = conn.execute(
                'SELECT MAX(lesson_order) as max_order FROM lessons WHERE course_id = ?',
                (original['course_id'],)
            ).fetchone()
            
            next_order = (max_order['max_order'] or 0) + 1
            
            # Create duplicate
            cursor = conn.execute('''
                INSERT INTO lessons (
                    title, content, lesson_type, duration_minutes, lesson_order,
                    course_id, learning_objectives, additional_resources, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                f"{original['title']} (Copy)", original['content'],
                original['lesson_type'], original['duration_minutes'],
                next_order, original['course_id'],
                original['learning_objectives'], original['additional_resources']
            ))
            
            new_module_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return True, f'Module duplicated successfully.', new_module_id
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'Failed to duplicate module: {str(e)}', None
    
    def get_user_module_progress(self, user_id, course_id):
        """Get user's progress for all modules in a course."""
        conn = self.get_db_connection()
        
        progress = conn.execute('''
            SELECT l.id as lesson_id, l.title, l.lesson_order,
                   up.completed, up.completed_at, up.time_spent
            FROM lessons l
            LEFT JOIN user_progress up ON l.id = up.lesson_id AND up.user_id = ?
            WHERE l.course_id = ?
            ORDER BY l.lesson_order
        ''', (user_id, course_id)).fetchall()
        
        conn.close()
        return [dict(p) for p in progress]
    
    def mark_module_complete(self, user_id, module_id, time_spent=0):
        """Mark a module as completed for a user (excludes admin users)."""
        conn = self.get_db_connection()
        
        try:
            # Check if user is admin - admins don't get progress tracking
            user_role = conn.execute(
                'SELECT role FROM users WHERE id = ?', (user_id,)
            ).fetchone()
            
            if user_role and user_role['role'] == 'admin':
                conn.close()
                return True, 'Admin access - progress not tracked.'
            
            # Check if progress record exists
            existing = conn.execute(
                'SELECT id FROM user_progress WHERE user_id = ? AND lesson_id = ?',
                (user_id, module_id)
            ).fetchone()
            
            if existing:
                # Update existing record
                conn.execute('''
                    UPDATE user_progress 
                    SET completed = 1, completed_at = CURRENT_TIMESTAMP, time_spent = ?
                    WHERE user_id = ? AND lesson_id = ?
                ''', (time_spent, user_id, module_id))
            else:
                # Create new progress record
                conn.execute('''
                    INSERT INTO user_progress (user_id, lesson_id, completed, completed_at, time_spent)
                    VALUES (?, ?, 1, CURRENT_TIMESTAMP, ?)
                ''', (user_id, module_id, time_spent))
            
            conn.commit()
            conn.close()
            
            return True, 'Module marked as completed.'
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'Failed to mark module as completed: {str(e)}'
    
    def check_module_access(self, user_id, course_id):
        """Check if user has access to course modules."""
        conn = self.get_db_connection()
        
        # Check user approval status and role
        user = conn.execute(
            'SELECT approval_status, role FROM users WHERE id = ?', 
            (user_id,)
        ).fetchone()
        
        if not user:
            conn.close()
            return False, "User not found"
        
        # Admin users always have access to all modules
        if user['role'] == 'admin':
            conn.close()
            return True, "Admin access granted"
        
        # Check enrollment status for non-admin users
        enrollment = conn.execute(
            'SELECT approval_status FROM enrollments WHERE user_id = ? AND course_id = ?',
            (user_id, course_id)
        ).fetchone()
        
        conn.close()
        
        if not enrollment:
            return False, "Please request enrollment in this course first to access the modules"
        
        # Both user and enrollment must be approved for module access
        user_approved = user['approval_status'] == 'approved'
        enrollment_approved = enrollment['approval_status'] == 'approved'
        
        if not user_approved:
            return False, "Your account is pending admin approval. You'll gain access once approved"
        
        if not enrollment_approved:
            return False, "Your enrollment request is being reviewed by the administrator. You'll gain access to course modules once approved"
        
        return True, "Access granted"
    
    def get_module_types(self):
        """Get available module types."""
        return [
            {'value': 'text', 'label': 'Text/Reading', 'icon': 'fas fa-file-text'},
            {'value': 'video', 'label': 'Video', 'icon': 'fas fa-video'},
            {'value': 'audio', 'label': 'Audio', 'icon': 'fas fa-volume-up'},
            {'value': 'presentation', 'label': 'Presentation', 'icon': 'fas fa-presentation'},
            {'value': 'interactive', 'label': 'Interactive', 'icon': 'fas fa-mouse-pointer'},
            {'value': 'quiz', 'label': 'Quiz/Assessment', 'icon': 'fas fa-question-circle'},
            {'value': 'assignment', 'label': 'Assignment', 'icon': 'fas fa-tasks'},
            {'value': 'discussion', 'label': 'Discussion', 'icon': 'fas fa-comments'}
        ]


class CourseModulesManager:
    """Manager class for handling course modules routes and business logic."""
    
    def __init__(self, app, db_connection_func):
        """Initialize with Flask app and database connection function."""
        self.app = app
        self.modules_repo = CourseModulesRepository(db_connection_func)
        self._register_routes()
    
    def _register_routes(self):
        """Register all course modules routes with the Flask app."""
        
        @self.app.route('/course/<int:course_id>/modules')
        def course_modules_list(course_id):
            """View course modules with access control."""
            if not self._check_login():
                return redirect(url_for('login'))
            
            # Check module access
            has_access, message = self.modules_repo.check_module_access(session['user_id'], course_id)
            
            # Get course info
            conn = self.modules_repo.get_db_connection()
            course = conn.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
            conn.close()
            
            if not course:
                flash('Course not found.', 'error')
                return redirect(url_for('courses'))
            
            if not has_access:
                flash(message, 'info')
                return redirect(url_for('course_detail', course_id=course_id))
            
            # Get modules and user progress
            modules = self.modules_repo.get_course_modules(course_id)
            user_progress = self.modules_repo.get_user_module_progress(session['user_id'], course_id)
            
            return render_template('course_modules_list.html', 
                                 course=course, modules=modules, user_progress=user_progress)
        
        @self.app.route('/course-module/<int:module_id>/view')
        def view_course_module(module_id):
            """Individual module viewer with progress tracking."""
            if not self._check_login():
                return redirect(url_for('login'))
            
            module = self.modules_repo.get_module_by_id(module_id)
            if not module:
                flash('Module not found.', 'error')
                return redirect(url_for('courses'))
            
            # Check access
            has_access, message = self.modules_repo.check_module_access(
                session['user_id'], module['course_id']
            )
            
            if not has_access:
                flash(message, 'info')
                return redirect(url_for('course_detail', course_id=module['course_id']))
            
            # Get course info
            conn = self.modules_repo.get_db_connection()
            course = conn.execute('SELECT * FROM courses WHERE id = ?', (module['course_id'],)).fetchone()
            conn.close()
            
            return render_template('module_view.html', module=module, course=course)
        
        @self.app.route('/course-module/<int:module_id>/complete', methods=['POST'])
        def complete_course_module(module_id):
            """Mark module as completed (AJAX endpoint)."""
            if not self._check_login():
                return jsonify({'success': False, 'message': 'Please log in'})
            
            data = request.get_json() or {}
            time_spent = data.get('time_spent', 0)
            
            success, message = self.modules_repo.mark_module_complete(
                session['user_id'], module_id, time_spent
            )
            
            return jsonify({'success': success, 'message': message})
        
        @self.app.route('/admin/courses/<int:course_id>/modules/manage')
        def admin_manage_modules(course_id):
            """Admin module management interface."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            # Get course info
            conn = self.modules_repo.get_db_connection()
            course = conn.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
            conn.close()
            
            if not course:
                flash('Course not found.', 'error')
                return redirect(url_for('admin_courses'))
            
            modules = self.modules_repo.get_course_modules(course_id)
            
            return render_template('admin_manage_modules.html', course=course, modules=modules)
        
        @self.app.route('/admin/courses/<int:course_id>/modules/create', methods=['GET', 'POST'])
        def admin_create_module(course_id):
            """Admin module creation."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            if request.method == 'POST':
                module_data = {
                    'title': request.form['title'],
                    'content': request.form['content'],
                    'lesson_type': request.form['lesson_type'],
                    'duration_minutes': self._safe_int(request.form.get('duration_minutes')),
                    'learning_objectives': request.form.get('learning_objectives'),
                    'additional_resources': request.form.get('additional_resources')
                }
                
                success, message, module_id = self.modules_repo.create_module(course_id, module_data)
                flash(message, 'success' if success else 'error')
                
                if success:
                    return redirect(url_for('admin_manage_modules', course_id=course_id))
            
            # Get course info
            conn = self.modules_repo.get_db_connection()
            course = conn.execute('SELECT * FROM courses WHERE id = ?', (course_id,)).fetchone()
            conn.close()
            
            if not course:
                flash('Course not found.', 'error')
                return redirect(url_for('admin_courses'))
            
            module_types = self.modules_repo.get_module_types()
            
            return render_template('admin_create_module.html', 
                                 course=course, module_types=module_types)
        
        @self.app.route('/admin/modules/<int:module_id>/edit', methods=['GET', 'POST'])
        def admin_edit_module(module_id):
            """Admin module editing."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            module = self.modules_repo.get_module_by_id(module_id)
            if not module:
                flash('Module not found.', 'error')
                return redirect(url_for('admin_courses'))
            
            if request.method == 'POST':
                module_data = {
                    'title': request.form['title'],
                    'content': request.form['content'],
                    'lesson_type': request.form['lesson_type'],
                    'duration_minutes': self._safe_int(request.form.get('duration_minutes')),
                    'learning_objectives': request.form.get('learning_objectives'),
                    'additional_resources': request.form.get('additional_resources')
                }
                
                success, message = self.modules_repo.update_module(module_id, module_data)
                flash(message, 'success' if success else 'error')
                
                if success:
                    return redirect(url_for('admin_manage_modules', course_id=module['course_id']))
            
            module_types = self.modules_repo.get_module_types()
            
            return render_template('admin_edit_module.html', 
                                 module=module, module_types=module_types)
        
        @self.app.route('/admin/modules/<int:module_id>/delete', methods=['POST'])
        def admin_delete_module(module_id):
            """Admin module deletion."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            module = self.modules_repo.get_module_by_id(module_id)
            if not module:
                flash('Module not found.', 'error')
                return redirect(url_for('admin_courses'))
            
            success, message = self.modules_repo.delete_module(module_id)
            flash(message, 'success' if success else 'error')
            
            return redirect(url_for('admin_manage_modules', course_id=module['course_id']))
        
        @self.app.route('/admin/modules/<int:module_id>/duplicate', methods=['POST'])
        def admin_duplicate_module(module_id):
            """Admin module duplication."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            module = self.modules_repo.get_module_by_id(module_id)
            if not module:
                flash('Module not found.', 'error')
                return redirect(url_for('admin_courses'))
            
            success, message, new_module_id = self.modules_repo.duplicate_module(module_id)
            flash(message, 'success' if success else 'error')
            
            return redirect(url_for('admin_manage_modules', course_id=module['course_id']))
        
        @self.app.route('/admin/courses/<int:course_id>/modules/reorder', methods=['POST'])
        def admin_reorder_modules(course_id):
            """Admin module reordering (AJAX endpoint)."""
            if not self._check_admin_access():
                return jsonify({'success': False, 'message': 'Access denied'})
            
            data = request.get_json() or {}
            module_order = data.get('module_order', [])
            
            success, message = self.modules_repo.reorder_modules(course_id, module_order)
            
            return jsonify({'success': success, 'message': message})
    
    def _check_login(self):
        """Check if user is logged in."""
        return 'user_id' in session
    
    def _check_admin_access(self):
        """Check if current user has admin access."""
        return session.get('role') == 'admin'
    
    def _safe_int(self, value, default=None):
        """Safely convert value to integer."""
        try:
            return int(value) if value else default
        except (ValueError, TypeError):
            return default
    
    def get_module_access_status(self, user_id, course_id):
        """Get module access status for a user and course."""
        return self.modules_repo.check_module_access(user_id, course_id)


def create_course_modules_manager(app, db_connection_func):
    """Factory function to create and configure CourseModulesManager."""
    return CourseModulesManager(app, db_connection_func)
