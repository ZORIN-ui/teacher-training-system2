"""
Teacher Training System - Main Application File (Modular Version)

This is the main Flask application file that coordinates all the modular systems:
- User Management (user_management.py)
- Registration Management (registration_management.py) 
- Course Management (course_management.py)
- Course Modules Management (course_modules_management.py)
- Modules Management (modules_management.py)
"""

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import sqlite3
import hashlib
import os
import json
from datetime import datetime, timedelta
from functools import wraps
from user_management import create_user_manager
# from modules_management import create_module_manager  # Disabled - functionality moved to course_manager
from registration_management import create_registration_manager
from course_management import create_course_manager
# from course_modules_management import create_course_modules_manager  # Disabled - functionality moved to course_manager

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'teacher-training-secret-key-2024'

# Configure file uploads
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'static', 'uploads')

# Database file
DATABASE = 'teacher_training_simple.db'

def get_db_connection():
    """Get database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize the database with required tables."""
    conn = get_db_connection()
    
    # Create users table with approval system and university-style fields
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'teacher',
            department TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            approval_status TEXT DEFAULT 'pending',
            approved_at TIMESTAMP,
            approved_by INTEGER,
            -- University-style registration fields
            first_name TEXT,
            last_name TEXT,
            date_of_birth DATE,
            gender TEXT,
            phone_number TEXT,
            address TEXT,
            city TEXT,
            state_province TEXT,
            postal_code TEXT,
            country TEXT DEFAULT 'Kenya',
            nationality TEXT,
            id_number TEXT,
            passport_number TEXT,
            emergency_contact_name TEXT,
            emergency_contact_phone TEXT,
            emergency_contact_relationship TEXT,
            highest_education TEXT,
            institution_name TEXT,
            graduation_year INTEGER,
            professional_experience TEXT,
            current_position TEXT,
            organization TEXT,
            years_of_experience INTEGER,
            preferred_course_id INTEGER,
            motivation TEXT,
            how_did_you_hear TEXT,
            FOREIGN KEY (approved_by) REFERENCES users (id),
            FOREIGN KEY (preferred_course_id) REFERENCES courses (id)
        )
    ''')
    
    # Courses table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            level TEXT NOT NULL,
            duration_hours INTEGER DEFAULT 0,
            instructor_id INTEGER,
            is_published INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (instructor_id) REFERENCES users (id)
        )
    ''')
    
    # Lessons table (modules)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            lesson_type TEXT DEFAULT 'text',
            duration_minutes INTEGER DEFAULT 0,
            lesson_order INTEGER DEFAULT 1,
            course_id INTEGER NOT NULL,
            learning_objectives TEXT,
            additional_resources TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (id)
        )
    ''')
    
    # Check if lessons table needs migration for learning_objectives and additional_resources
    try:
        # Try to add the columns if they don't exist
        conn.execute('ALTER TABLE lessons ADD COLUMN learning_objectives TEXT')
        print("Added learning_objectives column to lessons table")
    except sqlite3.OperationalError:
        # Column already exists
        pass
    
    try:
        conn.execute('ALTER TABLE lessons ADD COLUMN additional_resources TEXT')
        print("Added additional_resources column to lessons table")
    except sqlite3.OperationalError:
        # Column already exists
        pass
    
    # Enrollments table with approval system
    conn.execute('''
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            course_id INTEGER NOT NULL,
            enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            approval_status TEXT DEFAULT 'pending',
            approved_at TIMESTAMP,
            approved_by INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (course_id) REFERENCES courses (id),
            FOREIGN KEY (approved_by) REFERENCES users (id),
            UNIQUE(user_id, course_id)
        )
    ''')
    
    # User progress table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            lesson_id INTEGER NOT NULL,
            completed INTEGER DEFAULT 0,
            completed_at TIMESTAMP,
            time_spent INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (lesson_id) REFERENCES lessons (id),
            UNIQUE(user_id, lesson_id)
        )
    ''')
    
    # Create default admin user if not exists
    admin_exists = conn.execute(
        'SELECT id FROM users WHERE email = ?', 
        ('admin@teachertraining.com',)
    ).fetchone()
    
    if not admin_exists:
        password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
        conn.execute('''
            INSERT INTO users (username, email, full_name, password_hash, role, is_active, approval_status, approved_at, approved_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 1)
        ''', ('admin', 'admin@teachertraining.com', 'System Administrator', 
              password_hash, 'admin', 1, 'approved'))
    else:
        # Ensure existing admin user is always approved
        conn.execute('''
            UPDATE users 
            SET approval_status = 'approved', approved_at = CURRENT_TIMESTAMP, approved_by = 1
            WHERE email = ? AND role = 'admin'
        ''', ('admin@teachertraining.com',))
        
        # Add main courses
        main_courses = [
            ('Leadership Development', 
             'Comprehensive program designed to develop effective leadership skills for educational professionals. Learn strategic thinking, team management, decision-making, and transformational leadership principles.',
             'Professional Development', 'intermediate', 40, 1, 1),
            ('Personal Transformation', 
             'A journey of self-discovery and personal growth. Develop emotional intelligence, resilience, mindfulness, and personal effectiveness skills essential for professional and personal success.',
             'Personal Development', 'beginner', 30, 1, 1),
            ('Finance', 
             'Master financial literacy, budgeting, investment strategies, and financial planning. Essential skills for personal financial management and understanding organizational finances.',
             'Financial Literacy', 'intermediate', 35, 1, 1),
            ('Educational Administration', 
             'Learn the principles and practices of educational management, policy development, curriculum planning, staff management, and institutional leadership in educational settings.',
             'Administration', 'advanced', 45, 1, 1)
        ]
        
        # Get or create Leadership Development course for sample lessons
        leadership_course = None
        for course_data in main_courses:
            # Check if course already exists
            existing = conn.execute(
                'SELECT id FROM courses WHERE title = ?', 
                (course_data[0],)
            ).fetchone()
            
            if not existing:
                cursor = conn.execute('''
                    INSERT INTO courses (title, description, category, level, duration_hours, instructor_id, is_published)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', course_data)
                
                # Store Leadership Development course ID for sample lessons
                if course_data[0] == 'Leadership Development':
                    leadership_course = cursor.lastrowid
            else:
                # Store existing Leadership Development course ID
                if course_data[0] == 'Leadership Development':
                    leadership_course = existing['id']
        
        # Add sample lessons for Leadership Development course if it exists
        if leadership_course:
            lessons = [
                ('Welcome to Leadership Development', 'Welcome to our comprehensive leadership development program!', 'text', 15, 1),
                ('Understanding Leadership Styles', 'Learn about different leadership approaches and when to use them.', 'text', 30, 2),
                ('Team Management Fundamentals', 'Effective strategies for managing and motivating teams.', 'text', 45, 3),
                ('Strategic Decision Making', 'Develop skills in strategic thinking and decision-making processes.', 'text', 30, 4)
            ]
            
            for lesson in lessons:
                # Check if lesson already exists
                existing_lesson = conn.execute(
                    'SELECT id FROM lessons WHERE title = ? AND course_id = ?',
                    (lesson[0], leadership_course)
                ).fetchone()
                
                if not existing_lesson:
                    conn.execute('''
                        INSERT INTO lessons (title, content, lesson_type, duration_minutes, lesson_order, course_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (*lesson, leadership_course))
    
    conn.commit()
    conn.close()

# Initialize managers (will be set after database initialization)
user_manager = None
module_manager = None
registration_manager = None
course_manager = None
course_modules_manager = None

def login_required(f):
    """Decorator to require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def safe_int(value, default=0):
    """Safely convert value to integer."""
    try:
        return int(value) if value else default
    except (ValueError, TypeError):
        return default

@app.route('/')
def index():
    """Home page."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index_simple.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        success, message, user = user_manager.login_user(email, password)

        if success:
            # Set session data
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            
            flash(message, 'success')
            return redirect(url_for('dashboard'))
        else:
            flash(message, 'error' if 'Invalid' in message else 'warning')
    
    return render_template('login_simple.html')

# Public signup route (simple). Detailed registration is done after login at /complete-registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    """Public account signup. Creates a basic account; detailed registration happens inside."""
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        full_name = request.form['full_name']
        password = request.form['password']
        confirm_password = request.form.get('confirm_password')
        department = request.form.get('department', '')

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register_simple.html')

        success, message = user_manager.register_user(username, email, full_name, password, department)
        if success:
            flash('Account created. Please sign in, then complete your registration inside the system.', 'success')
            return redirect(url_for('login'))
        else:
            flash(message, 'error')

    return render_template('register_simple.html')

# Registration routes are now handled by registration_manager
# Course routes are now handled by course_manager
# Course modules routes are now handled by course_modules_manager

@app.route('/logout')
@login_required
def logout():
    """Logout."""
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard."""
    if session.get('role') == 'admin':
        # Admin dashboard with system statistics
        user_stats = user_manager.get_user_statistics()
        course_stats = course_manager.get_course_statistics() if course_manager else {}
        
        conn = get_db_connection()
        
        # Get created courses
        created_courses = conn.execute('''
            SELECT c.*, COUNT(e.id) as enrollment_count
            FROM courses c
            LEFT JOIN enrollments e ON c.id = e.course_id
            WHERE c.instructor_id = ?
            GROUP BY c.id
            ORDER BY c.created_at DESC
            LIMIT 10
        ''', (session['user_id'],)).fetchall()
        
        # Get pending users count
        pending_users_count = conn.execute('''
            SELECT COUNT(*) as count FROM users 
            WHERE approval_status = 'pending' AND role != 'admin'
        ''').fetchone()['count']
        
        # Get pending enrollments count (excludes admin users)
        pending_enrollments_count = conn.execute('''
            SELECT COUNT(*) as count FROM enrollments e
            JOIN users u ON e.user_id = u.id
            WHERE e.approval_status = 'pending' AND u.role != 'admin'
        ''').fetchone()['count']
        
        # Get total statistics for dashboard cards (excludes admin users)
        total_users = conn.execute('SELECT COUNT(*) as count FROM users WHERE role != "admin"').fetchone()['count']
        total_courses = conn.execute('SELECT COUNT(*) as count FROM courses').fetchone()['count']
        total_enrollments = conn.execute('''
            SELECT COUNT(*) as count FROM enrollments e
            JOIN users u ON e.user_id = u.id
            WHERE u.role != 'admin'
        ''').fetchone()['count']
        published_courses = conn.execute('SELECT COUNT(*) as count FROM courses WHERE is_published = 1').fetchone()['count']
        
        conn.close()
        
        return render_template('admin_dashboard_simple.html',
                             created_courses=created_courses,
                             user_stats=user_stats,
                             course_stats=course_stats,
                             pending_users=pending_users_count,
                             pending_enrollments=pending_enrollments_count,
                             total_users=total_users,
                             total_courses=total_courses,
                             total_enrollments=total_enrollments,
                             published_courses=published_courses)
    else:
        # Regular user dashboard - show approved enrollments only
        conn = get_db_connection()
        
        enrollments = conn.execute('''
            SELECT e.*, c.title, c.description, c.category, c.level
            FROM enrollments e
            JOIN courses c ON e.course_id = c.id
            WHERE e.user_id = ? AND e.is_active = 1 AND e.approval_status = 'approved'
            ORDER BY e.enrolled_at DESC
        ''', (session['user_id'],)).fetchall()
        
        # Get pending enrollment requests
        pending_requests = conn.execute('''
            SELECT e.*, c.title, c.description, c.category, c.level
            FROM enrollments e
            JOIN courses c ON e.course_id = c.id
            WHERE e.user_id = ? AND e.approval_status = 'pending'
            ORDER BY e.enrolled_at DESC
        ''', (session['user_id'],)).fetchall()
        
        # Get available courses (not enrolled)
        enrolled_course_ids = [str(e['course_id']) for e in enrollments]
        if enrolled_course_ids:
            placeholders = ','.join(['?' for _ in enrolled_course_ids])
            available_courses = conn.execute(f'''
                SELECT * FROM courses 
                WHERE is_published = 1 AND id NOT IN ({placeholders})
                LIMIT 6
            ''', enrolled_course_ids).fetchall()
        else:
            available_courses = conn.execute('''
                SELECT * FROM courses WHERE is_published = 1 LIMIT 6
            ''').fetchall()
        
        conn.close()
        
        # Calculate statistics
        total_courses = len(enrollments)
        completed_courses = len([e for e in enrollments if e['completed_at']])
        in_progress_courses = total_courses - completed_courses
        
        return render_template('dashboard_simple.html',
                             enrollments=enrollments,
                             pending_requests=pending_requests,
                             available_courses=available_courses,
                             total_courses=total_courses,
                             completed_courses=completed_courses,
                             in_progress_courses=in_progress_courses)

# All other routes are now handled by the modular systems

if __name__ == '__main__':
    # Create upload directories
    os.makedirs('static/uploads', exist_ok=True)
    os.makedirs('static/uploads/courses', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # Initialize database
    init_database()
    
    # Initialize all managers
    user_manager = create_user_manager(app, get_db_connection)
    # module_manager = create_module_manager(app, get_db_connection)  # Disabled - functionality moved to course_manager
    registration_manager = create_registration_manager(app, get_db_connection)
    course_manager = create_course_manager(app, get_db_connection)
    # course_modules_manager = create_course_modules_manager(app, get_db_connection)  # Disabled - functionality moved to course_manager
    
    # Production settings
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    print("🚀 Teacher Training System (Modular)")
    print("=" * 50)
    print("📅 Starting at:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print(f"🌐 Port: {port}")
    print("📋 Default Login: admin@teachertraining.com / admin123")
    print("=" * 50)
    print("📦 Modular Systems Loaded:")
    print("   ✅ User Management")
    print("   ✅ Registration Management")
    print("   ✅ Course Management")
    print("   ✅ Course Modules Management")
    print("   ✅ Modules Management")
    print("=" * 50)
    
    app.run(debug=debug, host='0.0.0.0', port=port)
