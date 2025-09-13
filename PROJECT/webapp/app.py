import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, redirect, url_for, flash
from markupsafe import Markup
from scheduler import get_session, add_classroom, add_course, add_teacher, add_class, generate_timetable, find_available_rooms, suggest_reschedule_options, Course, Teacher, Class, Classroom, Timetable, User
from sqlalchemy.exc import IntegrityError
from flask import session as flask_session
import csv
from io import TextIOWrapper

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')
app.secret_key = 'your_secret_key'  # Change this to a random secret key
session = get_session()

# Jinja filter to assign a color class to each course
def course_color_class(cell):
    if not cell:
        return ''
    # Use the course name as a key for color assignment
    course_name = cell.split('<br>')[0] if '<br>' in cell else cell
    # Simple hash for color assignment
    idx = abs(hash(course_name)) % 10
    return f'course-color-{idx}'

app.jinja_env.filters['course_color_class'] = course_color_class

# Ensure current_user and helper functions are available in templates
@app.context_processor
def inject_template_globals():
    context = {}
    if 'user_id' in flask_session:
        user = session.query(User).get(flask_session['user_id'])
        context['current_user'] = user
    else:
        context['current_user'] = None
    
    # Add helper functions to template context
    context['get_teachers'] = get_teachers
    context['get_courses'] = get_courses
    context['get_classes'] = get_classes
    context['get_classrooms'] = get_classrooms
    
    return context

def get_courses():
    return session.query(Course).all()

def get_teachers():
    return session.query(Teacher).all()

def get_classes():
    return session.query(Class).all()

def get_classrooms():
    return session.query(Classroom).all()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_classroom', methods=['GET', 'POST'])
def add_classroom_route():
    if request.method == 'POST':
        if 'csv_file' in request.files:
            file = request.files['csv_file']
            if file.filename.endswith('.csv'):
                csvfile = TextIOWrapper(file, encoding='utf-8')
                reader = csv.DictReader(csvfile)
                for row in reader:
                    name = row.get('name') or row.get('Classroom Name')
                    capacity = row.get('capacity') or row.get('Capacity')
                    if name and capacity:
                        add_classroom(session, name, int(capacity))
                return redirect(url_for('index'))
        # fallback for manual (should not happen)
        name = request.form.get('name')
        capacity = request.form.get('capacity')
        if name and capacity:
            add_classroom(session, name, int(capacity))
            return redirect(url_for('index'))
    return render_template('add_classroom.html')

@app.route('/add_teacher', methods=['GET', 'POST'])
def add_teacher_route():
    if request.method == 'POST':
        if 'csv_file' in request.files:
            file = request.files['csv_file']
            if file.filename.endswith('.csv'):
                csvfile = TextIOWrapper(file, encoding='utf-8')
                reader = csv.DictReader(csvfile)
                for row in reader:
                    name = row.get('name') or row.get('Teacher Name')
                    subject = row.get('subject') or row.get('Courses')
                    if name and subject:
                        add_teacher(session, name, subject)
                return redirect(url_for('index'))
        # fallback for manual (should not happen)
        name = request.form.get('name')
        subject = request.form.get('subject')
        if name and subject:
            add_teacher(session, name, subject)
            return redirect(url_for('index'))
    return render_template('add_teacher.html', courses=get_courses())

@app.route('/add_course', methods=['GET', 'POST'])
def add_course_route():
    if request.method == 'POST':
        if 'csv_file' in request.files:
            file = request.files['csv_file']
            if file.filename.endswith('.csv'):
                csvfile = TextIOWrapper(file, encoding='utf-8')
                reader = csv.DictReader(csvfile)
                for row in reader:
                    name = row.get('name') or row.get('Course Name')
                    if name:
                        add_course(session, name)
                return redirect(url_for('index'))
        name = request.form.get('name')
        if name:
            add_course(session, name)
            return redirect(url_for('index'))
    return render_template('add_course.html')

@app.route('/add_class', methods=['GET', 'POST'])
def add_class_route():
    if request.method == 'POST':
        if 'csv_file' in request.files:
            file = request.files['csv_file']
            if file.filename.endswith('.csv'):
                csvfile = TextIOWrapper(file, encoding='utf-8')
                reader = csv.DictReader(csvfile)
                for row in reader:
                    name = row.get('name') or row.get('Class Group Name')
                    # You may want to extend this for course/teacher mapping
                    if name:
                        add_class(session, name, {})
                return redirect(url_for('index'))
        name = request.form.get('name')
        if name:
            add_class(session, name, {})
            return redirect(url_for('index'))
    return render_template('add_class.html', courses=get_courses(), teachers=get_teachers())

@app.route('/generate_timetable')
def generate_timetable_route():
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    # 8am to 6pm, 1 hour slots
    time_slots = [(f"{h:02d}:00", f"{h+1:02d}:00") for h in range(8, 18)]
    generate_timetable(session, days, time_slots)
    # Build timetable grid for all classes
    classes = session.query(Class).all()
    timetable_data = {}
    for class_ in classes:
        grid = {slot: {day: None for day in days} for slot in time_slots}
        entries = session.query(Timetable).filter_by(class_id=class_.id).all()
        for entry in entries:
            slot = (entry.start_time, entry.end_time)
            grid[slot][entry.day] = f"{entry.course.name}<br>{entry.teacher.name}<br>{entry.classroom.name}"
        timetable_data[class_.name] = grid
    return render_template('timetable.html', timetable_data=timetable_data, days=days, time_slots=time_slots)

@app.route('/find_rooms', methods=['GET', 'POST'])
def find_rooms_route():
    available = []
    if request.method == 'POST':
        day = request.form['day']
        start = request.form['start_time']
        end = request.form['end_time']
        available = find_available_rooms(session, day, start, end)
    return render_template('find_rooms.html', available=available)

@app.route('/reschedule', methods=['GET', 'POST'])
def reschedule_route():
    options = []
    if request.method == 'POST':
        class_id = int(request.form['class_id'])
        course_id = int(request.form['course_id'])
        options = suggest_reschedule_options(session, class_id, course_id)
    return render_template('reschedule.html', classes=get_classes(), courses=get_courses(), options=options)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('register.html')
        user = User(username=username)
        user.set_password(password)
        try:
            session.add(user)
            session.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except IntegrityError:
            session.rollback()
            flash('Username already exists.', 'danger')
            return render_template('register.html')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = session.query(User).filter_by(username=username).first()
        if user and user.check_password(password):
            flask_session['user_id'] = user.id
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
            return render_template('login.html')
    return render_template('login.html')

@app.route('/logout')
def logout():
    flask_session.pop('user_id', None)
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/cancel_class', methods=['GET', 'POST'])
def cancel_class():
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        course_id = request.form.get('course_id')
        date = request.form.get('date')
        reason = request.form.get('reason')
        if all([class_id, course_id, date]):
            # Add cancellation logic here
            flash('Class cancelled successfully.', 'success')
            return redirect(url_for('index'))
        flash('Please fill out all fields.', 'danger')
    return render_template('cancel_class.html', classes=get_classes(), courses=get_courses())

@app.route('/change_room', methods=['GET', 'POST'])
def change_room():
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        course_id = request.form.get('course_id')
        new_room_id = request.form.get('new_room_id')
        date = request.form.get('date')
        reason = request.form.get('reason')
        if all([class_id, course_id, new_room_id, date]):
            # Add room change logic here
            flash('Room changed successfully.', 'success')
            return redirect(url_for('index'))
        flash('Please fill out all fields.', 'danger')
    available_rooms = get_classrooms()  # Get all rooms initially
    return render_template('change_room.html', classes=get_classes(), courses=get_courses(), available_rooms=available_rooms)

@app.route('/teachers')
def teachers():
    return render_template('teachers.html')

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in flask_session:
        flash('Please log in first.', 'danger')
        return redirect(url_for('login'))
    user = session.query(User).get(flask_session['user_id'])
    if not user or not user.is_admin():
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        target_user_id = request.form.get('user_id')
        action = request.form.get('action')
        if target_user_id and action == 'toggle_admin':
            target_user = session.query(User).get(target_user_id)
            if target_user:
                target_user.is_admin_user = not target_user.is_admin_user
                session.commit()
                flash(f"Admin status updated for {target_user.username}.", 'success')
            return redirect(url_for('admin_route'))
            
    return render_template('admin.html', users=session.query(User).all())

if __name__ == '__main__':
    app.run(debug=True)
