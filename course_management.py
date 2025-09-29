"""
Course Management Module for Teacher Training System

This module handles all aspects of course management including:
- Course creation, editing, and deletion
- Course categories and levels
- Course enrollment management
- Course statistics and analytics
- Course publishing and visibility
"""

import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import render_template, request, redirect, url_for, flash, jsonify, session, send_from_directory


class CourseRepository:
    """Repository class for handling course-related database operations."""
    
    def __init__(self, db_connection_func):
        """Initialize with database connection function."""
        self.get_db_connection = db_connection_func
    
    def get_all_courses(self, include_unpublished=False):
        """Get all courses with enrollment statistics."""
        conn = self.get_db_connection()
        
        where_clause = "" if include_unpublished else "WHERE c.is_published = 1"
        
        courses = conn.execute(f'''
            SELECT c.*, 
                   COUNT(DISTINCT CASE WHEN eu.role != 'admin' THEN e.id END) as enrollment_count,
                   COUNT(DISTINCT CASE WHEN e.approval_status = 'approved' AND eu.role != 'admin' THEN e.id END) as approved_enrollments,
                   COUNT(DISTINCT CASE WHEN e.approval_status = 'pending' AND eu.role != 'admin' THEN e.id END) as pending_enrollments,
                   COUNT(DISTINCT l.id) as lesson_count,
                   u.full_name as instructor_name
            FROM courses c
            LEFT JOIN enrollments e ON c.id = e.course_id
            LEFT JOIN users eu ON e.user_id = eu.id
            LEFT JOIN lessons l ON c.id = l.course_id
            LEFT JOIN users u ON c.instructor_id = u.id
            {where_clause}
            GROUP BY c.id
            ORDER BY c.created_at DESC
        ''').fetchall()
        
        conn.close()
        return [dict(course) for course in courses]
    
    def get_course_by_id(self, course_id):
        """Get a specific course by ID with detailed information."""
        conn = self.get_db_connection()
        
        course = conn.execute('''
            SELECT c.*, 
                   COUNT(DISTINCT CASE WHEN eu.role != 'admin' THEN e.id END) as enrollment_count,
                   COUNT(DISTINCT CASE WHEN e.approval_status = 'approved' AND eu.role != 'admin' THEN e.id END) as approved_enrollments,
                   COUNT(DISTINCT l.id) as lesson_count,
                   u.full_name as instructor_name
            FROM courses c
            LEFT JOIN enrollments e ON c.id = e.course_id
            LEFT JOIN users eu ON e.user_id = eu.id
            LEFT JOIN lessons l ON c.id = l.course_id
            LEFT JOIN users u ON c.instructor_id = u.id
            WHERE c.id = ?
            GROUP BY c.id
        ''', (course_id,)).fetchone()
        
        conn.close()
        return dict(course) if course else None
    
    def create_course(self, course_data):
        """Create a new course."""
        conn = self.get_db_connection()
        
        try:
            cursor = conn.execute('''
                INSERT INTO courses (
                    title, description, category, level, duration_hours, 
                    instructor_id, is_published, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                course_data['title'], course_data['description'], 
                course_data['category'], course_data['level'],
                course_data['duration_hours'], course_data['instructor_id'],
                course_data.get('is_published', 0)
            ))
            
            course_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return True, f'Course "{course_data["title"]}" created successfully.', course_id
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'Failed to create course: {str(e)}', None
    
    def update_course(self, course_id, course_data):
        """Update an existing course."""
        conn = self.get_db_connection()
        
        try:
            conn.execute('''
                UPDATE courses 
                SET title = ?, description = ?, category = ?, level = ?, 
                    duration_hours = ?, is_published = ?
                WHERE id = ?
            ''', (
                course_data['title'], course_data['description'],
                course_data['category'], course_data['level'],
                course_data['duration_hours'], course_data.get('is_published', 0),
                course_id
            ))
            
            conn.commit()
            conn.close()
            
            return True, f'Course updated successfully.'
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'Failed to update course: {str(e)}'
    
    def delete_course(self, course_id):
        """Delete a course and all related data."""
        conn = self.get_db_connection()
        
        try:
            # Get course title for confirmation
            course = conn.execute('SELECT title FROM courses WHERE id = ?', (course_id,)).fetchone()
            if not course:
                conn.close()
                return False, 'Course not found.'
            
            # Delete related data in correct order
            conn.execute('DELETE FROM user_progress WHERE lesson_id IN (SELECT id FROM lessons WHERE course_id = ?)', (course_id,))
            conn.execute('DELETE FROM lessons WHERE course_id = ?', (course_id,))
            conn.execute('DELETE FROM enrollments WHERE course_id = ?', (course_id,))
            conn.execute('DELETE FROM courses WHERE id = ?', (course_id,))
            
            conn.commit()
            conn.close()
            
            return True, f'Course "{course["title"]}" and all related data deleted successfully.'
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'Failed to delete course: {str(e)}'
    
    def get_course_categories(self):
        """Get all unique course categories."""
        conn = self.get_db_connection()
        
        categories = conn.execute('''
            SELECT DISTINCT category 
            FROM courses 
            WHERE category IS NOT NULL AND category != ''
            ORDER BY category
        ''').fetchall()
        
        conn.close()
        return [cat['category'] for cat in categories]
    
    def get_course_statistics(self):
        """Get comprehensive course statistics (excludes admin users from enrollment stats)."""
        conn = self.get_db_connection()
        
        stats = {
            'total_courses': conn.execute('SELECT COUNT(*) as count FROM courses').fetchone()['count'],
            'published_courses': conn.execute('SELECT COUNT(*) as count FROM courses WHERE is_published = 1').fetchone()['count'],
            'draft_courses': conn.execute('SELECT COUNT(*) as count FROM courses WHERE is_published = 0').fetchone()['count'],
            'total_enrollments': conn.execute('''
                SELECT COUNT(*) as count FROM enrollments e
                JOIN users u ON e.user_id = u.id
                WHERE u.role != 'admin'
            ''').fetchone()['count'],
            'approved_enrollments': conn.execute('''
                SELECT COUNT(*) as count FROM enrollments e
                JOIN users u ON e.user_id = u.id
                WHERE e.approval_status = "approved" AND u.role != 'admin'
            ''').fetchone()['count'],
            'pending_enrollments': conn.execute('''
                SELECT COUNT(*) as count FROM enrollments e
                JOIN users u ON e.user_id = u.id
                WHERE e.approval_status = "pending" AND u.role != 'admin'
            ''').fetchone()['count'],
            'total_lessons': conn.execute('SELECT COUNT(*) as count FROM lessons').fetchone()['count'],
        }
        
        # Get category breakdown
        categories = conn.execute('''
            SELECT category, COUNT(*) as count 
            FROM courses 
            WHERE category IS NOT NULL 
            GROUP BY category 
            ORDER BY count DESC
        ''').fetchall()
        
        stats['categories'] = [dict(cat) for cat in categories]
        
        # Get level breakdown
        levels = conn.execute('''
            SELECT level, COUNT(*) as count 
            FROM courses 
            WHERE level IS NOT NULL 
            GROUP BY level 
            ORDER BY 
                CASE level 
                    WHEN 'beginner' THEN 1 
                    WHEN 'intermediate' THEN 2 
                    WHEN 'advanced' THEN 3 
                    ELSE 4 
                END
        ''').fetchall()
        
        stats['levels'] = [dict(level) for level in levels]
        
        conn.close()
        return stats
    
    def get_course_enrollments(self, course_id):
        """Get all enrollments for a specific course (excludes admin users)."""
        conn = self.get_db_connection()
        
        enrollments = conn.execute('''
            SELECT e.*, u.full_name, u.email, u.phone, u.department,
                   COUNT(up.id) as completed_lessons,
                   (SELECT COUNT(*) FROM lessons WHERE course_id = ?) as total_lessons
            FROM enrollments e
            JOIN users u ON e.user_id = u.id
            LEFT JOIN user_progress up ON u.id = up.user_id 
                AND up.lesson_id IN (SELECT id FROM lessons WHERE course_id = ?)
                AND up.completed = 1
            WHERE e.course_id = ? AND u.role != 'admin'
            GROUP BY e.id, u.id
            ORDER BY e.enrolled_at DESC
        ''', (course_id, course_id, course_id)).fetchall()
        
        conn.close()
        return [dict(enrollment) for enrollment in enrollments]
    
    def approve_enrollment(self, enrollment_id, approved_by):
        """Approve a course enrollment."""
        conn = self.get_db_connection()
        
        try:
            # Get enrollment details
            enrollment = conn.execute('''
                SELECT e.*, u.full_name, c.title 
                FROM enrollments e
                JOIN users u ON e.user_id = u.id
                JOIN courses c ON e.course_id = c.id
                WHERE e.id = ?
            ''', (enrollment_id,)).fetchone()
            
            if not enrollment:
                conn.close()
                return False, 'Enrollment not found.'
            
            # Update enrollment status
            conn.execute('''
                UPDATE enrollments 
                SET approval_status = 'approved', approved_at = CURRENT_TIMESTAMP, approved_by = ?
                WHERE id = ?
            ''', (approved_by, enrollment_id))
            
            conn.commit()
            conn.close()
            
            return True, f'Enrollment approved for {enrollment["full_name"]} in "{enrollment["title"]}".'
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'Failed to approve enrollment: {str(e)}'
    
    def reject_enrollment(self, enrollment_id, rejected_by):
        """Reject a course enrollment."""
        conn = self.get_db_connection()
        
        try:
            # Get enrollment details
            enrollment = conn.execute('''
                SELECT e.*, u.full_name, c.title 
                FROM enrollments e
                JOIN users u ON e.user_id = u.id
                JOIN courses c ON e.course_id = c.id
                WHERE e.id = ?
            ''', (enrollment_id,)).fetchone()
            
            if not enrollment:
                conn.close()
                return False, 'Enrollment not found.'
            
            # Update enrollment status
            conn.execute('''
                UPDATE enrollments 
                SET approval_status = 'rejected', approved_at = CURRENT_TIMESTAMP, approved_by = ?
                WHERE id = ?
            ''', (rejected_by, enrollment_id))
            
            conn.commit()
            conn.close()
            
            return True, f'Enrollment rejected for {enrollment["full_name"]} in "{enrollment["title"]}".'
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'Failed to reject enrollment: {str(e)}'
    
    def get_course_modules(self, course_id):
        """Get all modules for a specific course."""
        conn = self.get_db_connection()
        
        modules = conn.execute('''
            SELECT * FROM lessons 
            WHERE course_id = ? 
            ORDER BY lesson_order ASC
        ''', (course_id,)).fetchall()
        
        conn.close()
        return [dict(module) for module in modules]
    
    def get_module_by_id(self, module_id):
        """Get a specific module by ID."""
        conn = self.get_db_connection()
        
        module = conn.execute('''
            SELECT l.*, c.title as course_title, c.id as course_id
            FROM lessons l
            JOIN courses c ON l.course_id = c.id
            WHERE l.id = ?
        ''', (module_id,)).fetchone()
        
        conn.close()
        return dict(module) if module else None
    
    def create_module(self, module_data):
        """Create a new course module."""
        conn = self.get_db_connection()
        
        try:
            # Get the next order number
            max_order = conn.execute(
                'SELECT MAX(lesson_order) as max_order FROM lessons WHERE course_id = ?',
                (module_data['course_id'],)
            ).fetchone()
            
            next_order = (max_order['max_order'] or 0) + 1
            
            cursor = conn.execute('''
                INSERT INTO lessons (
                    title, content, lesson_type, duration_minutes, lesson_order, 
                    course_id, learning_objectives, additional_resources, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                module_data['title'], module_data['content'], 
                module_data['lesson_type'], module_data['duration_minutes'],
                next_order, module_data['course_id'],
                module_data.get('learning_objectives', ''),
                module_data.get('additional_resources', '')
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
                module_data['lesson_type'], module_data['duration_minutes'],
                module_data.get('learning_objectives', ''),
                module_data.get('additional_resources', ''),
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
        """Delete a module and related progress data."""
        conn = self.get_db_connection()
        
        try:
            # Get module title for confirmation
            module = conn.execute('SELECT title FROM lessons WHERE id = ?', (module_id,)).fetchone()
            if not module:
                conn.close()
                return False, 'Module not found.'
            
            # Delete related progress data
            conn.execute('DELETE FROM user_progress WHERE lesson_id = ?', (module_id,))
            conn.execute('DELETE FROM lessons WHERE id = ?', (module_id,))
            
            conn.commit()
            conn.close()
            
            return True, f'Module "{module["title"]}" deleted successfully.'
            
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f'Failed to delete module: {str(e)}'
    
    def reorder_modules(self, course_id, module_orders):
        """Reorder modules in a course."""
        conn = self.get_db_connection()
        
        try:
            for module_id, order in module_orders.items():
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
    
    def check_user_enrollment(self, user_id, course_id):
        """Check if user is enrolled and approved for a course."""
        conn = self.get_db_connection()
        
        enrollment = conn.execute('''
            SELECT * FROM enrollments 
            WHERE user_id = ? AND course_id = ? AND approval_status = 'approved'
        ''', (user_id, course_id)).fetchone()
        
        conn.close()
        return dict(enrollment) if enrollment else None
    
    def get_user_module_progress(self, user_id, module_id):
        """Get user's progress for a specific module."""
        conn = self.get_db_connection()
        
        progress = conn.execute('''
            SELECT * FROM user_progress 
            WHERE user_id = ? AND lesson_id = ?
        ''', (user_id, module_id)).fetchone()
        
        conn.close()
        return dict(progress) if progress else None
    
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


class CourseManager:
    """Manager class for handling course routes and business logic."""
    
    def __init__(self, app, db_connection_func):
        """Initialize with Flask app and database connection function."""
        self.app = app
        self.course_repo = CourseRepository(db_connection_func)
        self._register_routes()
    
    def _register_routes(self):
        """Register all course-related routes with the Flask app."""
        
        @self.app.route('/courses')
        def courses():
            """Public courses listing page."""
            courses_list = self.course_repo.get_all_courses(include_unpublished=False)
            return render_template('courses_public.html', courses=courses_list)
        
        @self.app.route('/course/<int:course_id>')
        def course_detail(course_id):
            """Course detail page."""
            course = self.course_repo.get_course_by_id(course_id)
            if not course:
                flash('Course not found.', 'error')
                return redirect(url_for('courses'))
            
            # Check if user is enrolled
            enrollment = None
            if 'user_id' in session:
                conn = self.course_repo.get_db_connection()
                enrollment = conn.execute(
                    'SELECT * FROM enrollments WHERE user_id = ? AND course_id = ?',
                    (session['user_id'], course_id)
                ).fetchone()
                conn.close()
            
            # Get course lessons
            conn = self.course_repo.get_db_connection()
            lessons = conn.execute(
                'SELECT * FROM lessons WHERE course_id = ? ORDER BY lesson_order',
                (course_id,)
            ).fetchall()
            conn.close()
            
            return render_template('course_detail_simple.html', 
                                 course=course, enrollment=enrollment, lessons=lessons)
        
        @self.app.route('/admin/courses')
        def admin_courses():
            """Admin courses management page."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            courses_list = self.course_repo.get_all_courses(include_unpublished=True)
            stats = self.course_repo.get_course_statistics()
            
            return render_template('admin_courses.html', courses=courses_list, stats=stats)
        
        @self.app.route('/admin/courses/create', methods=['GET', 'POST'])
        def admin_create_course():
            """Admin course creation page."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            if request.method == 'POST':
                course_data = {
                    'title': request.form['title'],
                    'description': request.form['description'],
                    'category': request.form['category'],
                    'level': request.form['level'],
                    'duration_hours': self._safe_int(request.form.get('duration_hours'), 0),
                    'instructor_id': session['user_id'],
                    'is_published': 1 if request.form.get('is_published') else 0
                }
                
                success, message, course_id = self.course_repo.create_course(course_data)
                flash(message, 'success' if success else 'error')
                
                if success:
                    return redirect(url_for('admin_courses'))
            
            categories = self.course_repo.get_course_categories()
            return render_template('create_course.html', categories=categories)
        
        @self.app.route('/admin/courses/<int:course_id>/edit', methods=['GET', 'POST'])
        def admin_edit_course(course_id):
            """Admin course editing page."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            if request.method == 'POST':
                course_data = {
                    'title': request.form['title'],
                    'description': request.form['description'],
                    'category': request.form['category'],
                    'level': request.form['level'],
                    'duration_hours': self._safe_int(request.form.get('duration_hours'), 0),
                    'is_published': 1 if request.form.get('is_published') else 0
                }
                
                success, message = self.course_repo.update_course(course_id, course_data)
                flash(message, 'success' if success else 'error')
                
                if success:
                    return redirect(url_for('admin_courses'))
            
            course = self.course_repo.get_course_by_id(course_id)
            if not course:
                flash('Course not found.', 'error')
                return redirect(url_for('admin_courses'))
            
            categories = self.course_repo.get_course_categories()
            return render_template('edit_course.html', course=course, categories=categories)
        
        @self.app.route('/admin/courses/<int:course_id>/delete', methods=['POST'])
        def admin_delete_course(course_id):
            """Admin course deletion."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            success, message = self.course_repo.delete_course(course_id)
            flash(message, 'success' if success else 'error')
            
            return redirect(url_for('admin_courses'))
        
        @self.app.route('/admin/courses/<int:course_id>/enrollments')
        def admin_course_enrollments(course_id):
            """Admin course enrollments management."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            course = self.course_repo.get_course_by_id(course_id)
            if not course:
                flash('Course not found.', 'error')
                return redirect(url_for('admin_courses'))
            
            enrollments = self.course_repo.get_course_enrollments(course_id)
            
            return render_template('course_enrollments.html', 
                                 course=course, enrollments=enrollments)
        
        @self.app.route('/admin/enrollments/<int:enrollment_id>/approve', methods=['POST'])
        def admin_approve_enrollment(enrollment_id):
            """Approve a course enrollment."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            success, message = self.course_repo.approve_enrollment(enrollment_id, session['user_id'])
            flash(message, 'success' if success else 'error')
            
            # Redirect back to the course enrollments page
            enrollment_data = request.form.get('course_id')
            if enrollment_data:
                return redirect(url_for('admin_course_enrollments', course_id=enrollment_data))
            
            return redirect(url_for('admin_courses'))
        
        @self.app.route('/admin/enrollments/<int:enrollment_id>/reject', methods=['POST'])
        def admin_reject_enrollment(enrollment_id):
            """Reject a course enrollment."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            success, message = self.course_repo.reject_enrollment(enrollment_id, session['user_id'])
            flash(message, 'success' if success else 'error')
            
            # Redirect back to the course enrollments page
            enrollment_data = request.form.get('course_id')
            if enrollment_data:
                return redirect(url_for('admin_course_enrollments', course_id=enrollment_data))
            
            return redirect(url_for('admin_courses'))
        
        @self.app.route('/admin/enrollments')
        def admin_enrollments():
            """Admin system-wide enrollment management."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            conn = self.course_repo.get_db_connection()
            
            # Get all enrollments with course and user details (excludes admin users)
            enrollments = conn.execute('''
                SELECT e.*, u.full_name, u.email, u.phone, u.department,
                       c.title as course_title, c.category, c.level,
                       COUNT(up.id) as completed_lessons,
                       (SELECT COUNT(*) FROM lessons WHERE course_id = e.course_id) as total_lessons
                FROM enrollments e
                JOIN users u ON e.user_id = u.id
                JOIN courses c ON e.course_id = c.id
                LEFT JOIN user_progress up ON u.id = up.user_id 
                    AND up.lesson_id IN (SELECT id FROM lessons WHERE course_id = e.course_id)
                    AND up.completed = 1
                WHERE u.role != 'admin'
                GROUP BY e.id, u.id, c.id
                ORDER BY e.enrolled_at DESC
            ''').fetchall()
            
            conn.close()
            
            # Separate enrollments by status
            pending_enrollments = [dict(e) for e in enrollments if e['approval_status'] == 'pending']
            approved_enrollments = [dict(e) for e in enrollments if e['approval_status'] == 'approved']
            rejected_enrollments = [dict(e) for e in enrollments if e['approval_status'] == 'rejected']
            
            return render_template('admin_enrollments.html', 
                                 pending_enrollments=pending_enrollments,
                                 approved_enrollments=approved_enrollments,
                                 rejected_enrollments=rejected_enrollments)
        
        @self.app.route('/admin/enrollments/pending')
        def pending_enrollments():
            """Admin pending enrollments management."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            conn = self.course_repo.get_db_connection()
            
            # Get pending enrollments with course and user details (excludes admin users)
            pending = conn.execute('''
                SELECT e.*, u.full_name as student_name, u.email as student_email, u.phone, u.department,
                       c.title as course_title, c.category, c.level, c.duration_hours
                FROM enrollments e
                JOIN users u ON e.user_id = u.id
                JOIN courses c ON e.course_id = c.id
                WHERE e.approval_status = 'pending' AND u.role != 'admin'
                ORDER BY e.enrolled_at DESC
            ''').fetchall()
            
            conn.close()
            
            return render_template('pending_enrollments.html', pending=pending)
        
        @self.app.route('/admin/enrollments/bulk-approve', methods=['POST'])
        def bulk_approve_enrollments():
            """Bulk approve multiple enrollment requests."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            enrollment_ids = request.form.getlist('enrollment_ids')
            if not enrollment_ids:
                flash('No enrollments selected for approval.', 'warning')
                return redirect(url_for('pending_enrollments'))
            
            approved_count = 0
            failed_count = 0
            
            for enrollment_id in enrollment_ids:
                try:
                    success, message = self.course_repo.approve_enrollment(int(enrollment_id), session['user_id'])
                    if success:
                        approved_count += 1
                    else:
                        failed_count += 1
                except Exception as e:
                    failed_count += 1
            
            if approved_count > 0:
                flash(f'Successfully approved {approved_count} enrollment(s).', 'success')
            if failed_count > 0:
                flash(f'Failed to approve {failed_count} enrollment(s).', 'error')
            
            return redirect(url_for('pending_enrollments'))
        
        @self.app.route('/enroll/<int:course_id>', methods=['POST'])
        def enroll_course(course_id):
            """Request enrollment in a course (admin users cannot enroll)."""
            if 'user_id' not in session:
                flash('Please log in to enroll in courses.', 'error')
                return redirect(url_for('login'))
            
            # Prevent admin users from enrolling
            if session.get('role') == 'admin':
                flash('Admin users have direct access to all course content and do not need to enroll.', 'info')
                return redirect(url_for('course_detail', course_id=course_id))
            
            conn = self.course_repo.get_db_connection()
            
            # Check if already enrolled
            existing = conn.execute(
                'SELECT id, approval_status FROM enrollments WHERE user_id = ? AND course_id = ?',
                (session['user_id'], course_id)
            ).fetchone()
            
            if existing:
                if existing['approval_status'] == 'pending':
                    flash('Your enrollment request is already pending approval.', 'info')
                elif existing['approval_status'] == 'approved':
                    flash('You are already enrolled in this course.', 'info')
                else:
                    flash('Your previous enrollment was rejected. Please contact administrator.', 'warning')
                conn.close()
                return redirect(url_for('course_detail', course_id=course_id))
            
            # Create enrollment request
            try:
                conn.execute('''
                    INSERT INTO enrollments (user_id, course_id, approval_status, enrolled_at)
                    VALUES (?, ?, 'pending', CURRENT_TIMESTAMP)
                ''', (session['user_id'], course_id))
                
                conn.commit()
                conn.close()
                
                flash('Enrollment request submitted successfully! Please wait for admin approval.', 'success')
                
            except Exception as e:
                conn.rollback()
                conn.close()
                flash(f'Failed to submit enrollment request: {str(e)}', 'error')
            
            return redirect(url_for('course_detail', course_id=course_id))
        
        # Course Module Management Routes
        @self.app.route('/admin/courses/<int:course_id>/modules')
        def admin_course_modules(course_id):
            """Admin course modules management page."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            course = self.course_repo.get_course_by_id(course_id)
            if not course:
                flash('Course not found.', 'error')
                return redirect(url_for('admin_courses'))
            
            modules = self.course_repo.get_course_modules(course_id)
            
            return render_template('admin_course_modules.html', 
                                 course=course, modules=modules)
        
        @self.app.route('/admin/courses/<int:course_id>/modules/create', methods=['GET', 'POST'])
        def admin_create_module(course_id):
            """Admin module creation page."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            course = self.course_repo.get_course_by_id(course_id)
            if not course:
                flash('Course not found.', 'error')
                return redirect(url_for('admin_courses'))
            
            if request.method == 'POST':
                # Handle file upload if present
                uploaded_file = None
                if 'module_file' in request.files:
                    file = request.files['module_file']
                    if file and file.filename:
                        uploaded_file = self._handle_file_upload(file, course_id)
                
                module_data = {
                    'title': request.form['title'],
                    'content': request.form['content'],
                    'lesson_type': request.form['lesson_type'],
                    'duration_minutes': self._safe_int(request.form.get('duration_minutes'), 0),
                    'course_id': course_id,
                    'learning_objectives': request.form.get('learning_objectives', ''),
                    'additional_resources': request.form.get('additional_resources', '')
                }
                
                # Add file path to content if file was uploaded
                if uploaded_file:
                    if module_data['content']:
                        module_data['content'] += f"\n\n**Attached File:** {uploaded_file['filename']}\n**File Path:** {uploaded_file['path']}"
                    else:
                        module_data['content'] = f"**Attached File:** {uploaded_file['filename']}\n**File Path:** {uploaded_file['path']}"
                
                success, message, module_id = self.course_repo.create_module(module_data)
                flash(message, 'success' if success else 'error')
                
                if success:
                    return redirect(url_for('admin_course_modules', course_id=course_id))
            
            return render_template('admin_create_module.html', course=course)
        
        @self.app.route('/admin/modules/<int:module_id>/edit', methods=['GET', 'POST'])
        def admin_edit_module(module_id):
            """Admin module editing page."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            module = self.course_repo.get_module_by_id(module_id)
            if not module:
                flash('Module not found.', 'error')
                return redirect(url_for('admin_courses'))
            
            if request.method == 'POST':
                # Handle file upload if present
                uploaded_file = None
                if 'module_file' in request.files:
                    file = request.files['module_file']
                    if file and file.filename:
                        uploaded_file = self._handle_file_upload(file, module['course_id'])
                
                module_data = {
                    'title': request.form['title'],
                    'content': request.form['content'],
                    'lesson_type': request.form['lesson_type'],
                    'duration_minutes': self._safe_int(request.form.get('duration_minutes'), 0),
                    'learning_objectives': request.form.get('learning_objectives', ''),
                    'additional_resources': request.form.get('additional_resources', '')
                }
                
                # Add file path to content if file was uploaded
                if uploaded_file:
                    if module_data['content']:
                        module_data['content'] += f"\n\n**Attached File:** {uploaded_file['filename']}\n**File Path:** {uploaded_file['path']}"
                    else:
                        module_data['content'] = f"**Attached File:** {uploaded_file['filename']}\n**File Path:** {uploaded_file['path']}"
                
                success, message = self.course_repo.update_module(module_id, module_data)
                flash(message, 'success' if success else 'error')
                
                if success:
                    return redirect(url_for('admin_course_modules', course_id=module['course_id']))
            
            return render_template('admin_edit_module.html', module=module)
        
        @self.app.route('/admin/modules/<int:module_id>/delete', methods=['POST'])
        def admin_delete_module(module_id):
            """Admin module deletion."""
            if not self._check_admin_access():
                return redirect(url_for('login'))
            
            module = self.course_repo.get_module_by_id(module_id)
            if not module:
                flash('Module not found.', 'error')
                return redirect(url_for('admin_courses'))
            
            course_id = module['course_id']
            success, message = self.course_repo.delete_module(module_id)
            flash(message, 'success' if success else 'error')
            
            return redirect(url_for('admin_course_modules', course_id=course_id))
        
        # Student Module Access Routes
        @self.app.route('/course/<int:course_id>/modules')
        def course_modules(course_id):
            """Student course modules listing (requires enrollment)."""
            if 'user_id' not in session:
                flash('Please log in to access course modules.', 'error')
                return redirect(url_for('login'))
            
            # Check if user is enrolled and approved
            enrollment = self.course_repo.check_user_enrollment(session['user_id'], course_id)
            if not enrollment and session.get('role') != 'admin':
                flash('You must be enrolled and approved to access course modules.', 'error')
                return redirect(url_for('course_detail', course_id=course_id))
            
            course = self.course_repo.get_course_by_id(course_id)
            if not course:
                flash('Course not found.', 'error')
                return redirect(url_for('courses'))
            
            modules = self.course_repo.get_course_modules(course_id)
            
            # Get user progress for each module
            for module in modules:
                progress = self.course_repo.get_user_module_progress(session['user_id'], module['id'])
                module['progress'] = progress
            
            return render_template('course_modules_student.html', 
                                 course=course, modules=modules, enrollment=enrollment)
        
        @self.app.route('/module/<int:module_id>')
        def student_view_module(module_id):
            """Student module viewer (requires enrollment)."""
            if 'user_id' not in session:
                flash('Please log in to access modules.', 'error')
                return redirect(url_for('login'))
            
            module = self.course_repo.get_module_by_id(module_id)
            if not module:
                flash('Module not found.', 'error')
                return redirect(url_for('courses'))
            
            # Check if user is enrolled and approved
            enrollment = self.course_repo.check_user_enrollment(session['user_id'], module['course_id'])
            if not enrollment and session.get('role') != 'admin':
                flash('You must be enrolled and approved to access this module.', 'error')
                return redirect(url_for('course_detail', course_id=module['course_id']))
            
            # Get user progress
            progress = self.course_repo.get_user_module_progress(session['user_id'], module_id)
            
            # Get all modules for navigation
            all_modules = self.course_repo.get_course_modules(module['course_id'])
            
            return render_template('module_viewer.html', 
                                 module=module, progress=progress, 
                                 all_modules=all_modules, enrollment=enrollment)
        
        @self.app.route('/module/<int:module_id>/complete', methods=['POST'])
        def student_complete_module(module_id):
            """Mark module as completed (AJAX endpoint)."""
            if 'user_id' not in session:
                return jsonify({'success': False, 'message': 'Not logged in'})
            
            module = self.course_repo.get_module_by_id(module_id)
            if not module:
                return jsonify({'success': False, 'message': 'Module not found'})
            
            # Check if user is enrolled and approved
            enrollment = self.course_repo.check_user_enrollment(session['user_id'], module['course_id'])
            if not enrollment and session.get('role') != 'admin':
                return jsonify({'success': False, 'message': 'Access denied'})
            
            time_spent = self._safe_int(request.form.get('time_spent'), 0)
            success, message = self.course_repo.mark_module_complete(session['user_id'], module_id, time_spent)
            
            return jsonify({'success': success, 'message': message})
        
        # File Download Route
        @self.app.route('/uploads/<path:filename>')
        def download_file(filename):
            """Serve uploaded files (requires authentication)."""
            if 'user_id' not in session:
                flash('Please log in to access files.', 'error')
                return redirect(url_for('login'))
            
            upload_folder = os.path.join(os.getcwd(), 'static', 'uploads')
            return send_from_directory(upload_folder, filename)
    
    def _check_admin_access(self):
        """Check if current user has admin access."""
        return session.get('role') == 'admin'
    
    def _safe_int(self, value, default=0):
        """Safely convert value to integer."""
        try:
            return int(value) if value else default
        except (ValueError, TypeError):
            return default
    
    def _handle_file_upload(self, file, course_id):
        """Handle file upload for course modules."""
        if not file or not file.filename:
            return None
        
        # Create upload directory if it doesn't exist
        upload_folder = os.path.join(os.getcwd(), 'static', 'uploads', 'courses', str(course_id))
        os.makedirs(upload_folder, exist_ok=True)
        
        # Secure the filename
        filename = secure_filename(file.filename)
        
        # Add timestamp to avoid conflicts
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
        filename = timestamp + filename
        
        # Save the file
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
        
        # Return file info
        return {
            'filename': file.filename,  # Original filename
            'saved_filename': filename,  # Saved filename with timestamp
            'path': f'/uploads/courses/{course_id}/{filename}',  # Web-accessible path
            'full_path': file_path  # Full system path
        }
    
    def get_course_statistics(self):
        """Get course statistics for dashboard."""
        return self.course_repo.get_course_statistics()


def create_course_manager(app, db_connection_func):
    """Factory function to create and configure CourseManager."""
    return CourseManager(app, db_connection_func)
