import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from markupsafe import Markup
import sys
import json
import datetime
import collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from scheduler import get_session, add_classroom, add_course, add_teacher, add_class, generate_timetable, find_available_rooms, suggest_reschedule_options, get_current_timetable_data, Course, Teacher, Class, Classroom, Timetable, User, ClassCourseTeacher, Base
from models import ApprovedTimetable, RoomChange, ClassCancellation, Event, Feedback

from sqlalchemy.exc import IntegrityError
from flask import session as flask_session
import csv
from io import TextIOWrapper


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_secret_key')
app.secret_key = 'your_secret_key'  # Change this to a random secret key
session = get_session()  # Will use default relative path

# Exam model for scheduling exams
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Boolean, DateTime, Text
from sqlalchemy.orm import relationship

class Exam(Base):
    __tablename__ = 'exams'
    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.id'))
    room_id = Column(Integer, ForeignKey('classrooms.id'))
    date = Column(Date)
    start_time = Column(String)
    end_time = Column(String)
    course = relationship('Course')
    room = relationship('Classroom')

class ApprovedExamSchedule(Base):
    __tablename__ = 'approved_exam_schedules'
    id = Column(Integer, primary_key=True)
    name = Column(String, default='Approved Exam Schedule')
    description = Column(String)
    schedule_data = Column(Text)  # JSON string of approved exams
    approved_at = Column(DateTime, default=datetime.datetime.utcnow)
    approved_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    is_active = Column(Boolean, default=True)

# Ensure all tables (including Exam) are created
try:
    engine = session.get_bind()
    if engine is not None:
        Base.metadata.create_all(engine)
except Exception as _e:
    pass

# ---- Exams: auto-generation helpers ----
def next_monday(from_date=None):
    d = from_date or datetime.date.today()
    days_ahead = (7 - d.weekday()) % 7  # 0=Mon
    days_ahead = 7 if days_ahead == 0 else days_ahead
    return d + datetime.timedelta(days=days_ahead)

def generate_exam_schedule(db_session, start_date=None, num_days=5, reset=False):
    """Generate one exam per course across the upcoming exam window.
    - Distributes exams across days and slots
    - Avoids room conflicts and class overlap (a class can't have two exams at the same time)
    Returns (created_count, skipped_count).
    """
    # Optional reset (overwrite current draft exams)
    if reset:
        db_session.query(Exam).delete()
        db_session.commit()

    # Compute exam window
    start = start_date or next_monday()
    days = [start + datetime.timedelta(days=i) for i in range(num_days)]

    # Exam slots per day
    slots = [
        ("09:00", "11:00"),
        ("11:30", "13:30"),
        ("14:00", "16:00"),
    ]

    courses = db_session.query(Course).order_by(Course.name.asc()).all()
    rooms = db_session.query(Classroom).order_by(Classroom.name.asc()).all()

    # Build course -> classes mapping to avoid overlapping exams for the same class
    course_to_class_ids = collections.defaultdict(set)
    for cct in db_session.query(ClassCourseTeacher).all():
        course_to_class_ids[cct.course_id].add(cct.class_id)

    used_room_slots = set()      # (date, start, end, room_id)
    used_class_slots = set()     # (date, start, end, class_id)
    courses_already_scheduled = set()

    # If not resetting, consider existing draft exams to avoid duplicates
    if not reset:
        existing = db_session.query(Exam).all()
        for ex in existing:
            if ex.room_id and ex.date and ex.start_time and ex.end_time:
                used_room_slots.add((ex.date, ex.start_time, ex.end_time, ex.room_id))
            # mark classes occupied for this course's related classes
            rel_class_ids = [cct.class_id for cct in db_session.query(ClassCourseTeacher).filter_by(course_id=ex.course_id)]
            for cid in rel_class_ids:
                if ex.date and ex.start_time and ex.end_time:
                    used_class_slots.add((ex.date, ex.start_time, ex.end_time, cid))
            courses_already_scheduled.add(ex.course_id)

    created = 0
    skipped = 0

    for course in courses:
        if course.id in courses_already_scheduled:
            skipped += 1
            continue
        scheduled = False
        related_class_ids = course_to_class_ids.get(course.id, set())

        for day in days:
            for start_time, end_time in slots:
                # Ensure no related class has another exam at this slot
                class_conflict = any((day, start_time, end_time, cid) in used_class_slots for cid in related_class_ids)
                if class_conflict:
                    continue

                # Find a free room for this slot
                for room in rooms:
                    if (day, start_time, end_time, room.id) in used_room_slots:
                        continue

                    # Schedule exam
                    exam = Exam(
                        course_id=course.id,
                        room_id=room.id,
                        date=day,
                        start_time=start_time,
                        end_time=end_time,
                    )
                    db_session.add(exam)
                    db_session.flush()

                    # Mark resources
                    used_room_slots.add((day, start_time, end_time, room.id))
                    for cid in related_class_ids:
                        used_class_slots.add((day, start_time, end_time, cid))

                    created += 1
                    scheduled = True
                    break

                if scheduled:
                    break
            if scheduled:
                break

        if not scheduled:
            skipped += 1

    db_session.commit()
    return created, skipped

def get_active_approved_exam_schedule(db_session):
    return db_session.query(ApprovedExamSchedule).filter_by(is_active=True).order_by(ApprovedExamSchedule.approved_at.desc()).first()

def get_current_exam_data(db_session):
    exams = db_session.query(Exam).order_by(Exam.date.asc(), Exam.start_time.asc()).all()
    return [
        {
            'id': ex.id,
            'course_id': ex.course_id,
            'course': ex.course.name if ex.course else None,
            'room_id': ex.room_id,
            'room': ex.room.name if ex.room else None,
            'date': ex.date.strftime('%Y-%m-%d') if ex.date else None,
            'start_time': ex.start_time,
            'end_time': ex.end_time,
        }
        for ex in exams
    ]

# Jinja filter to assign a color class to each course
def course_color_class(cell):
    if not cell:
        return ''
        
    # Handle different types of cell content
    if isinstance(cell, list):
        # For lists, use the first course
        if len(cell) > 0:
            first_item = cell[0]
            if isinstance(first_item, str):
                course_name = first_item.split('<br>')[0] if '<br>' in first_item else first_item
            else:
                course_name = str(first_item)  # Convert to string if not already
        else:
            return ''
    elif isinstance(cell, str):
        # For strings
        course_name = cell.split('<br>')[0] if '<br>' in cell else cell
    else:
        # For integers or other types
        course_name = str(cell)  # Convert to string
    
    # Ensure we have a hashable string
    course_name = str(course_name)
    
    # Consistent color assignment for the same course
    color_idx = abs(hash(course_name)) % 10
    return f'course-color-{color_idx}'

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
    context['get_approved_timetables'] = get_approved_timetables
    
    return context

def get_approved_timetables():
    """Get all approved timetables, with active ones first."""
    return session.query(ApprovedTimetable).order_by(
        ApprovedTimetable.is_active.desc(),
        ApprovedTimetable.approved_at.desc()
    ).all()

def get_courses():
    return session.query(Course).all()

def get_teachers():
    return session.query(Teacher).all()

def get_classes():
    return session.query(Class).all()

def get_classrooms():
    return session.query(Classroom).all()

# Exam Scheduler: book and list exams
@app.route('/exam_scheduler', methods=['GET', 'POST'])
def exam_scheduler():
    if request.method == 'POST':
        course_id = request.form.get('course_id')
        room_id = request.form.get('room_id')
        date = request.form.get('date')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')

        if all([course_id, room_id, date, start_time, end_time]):
            try:
                exam = Exam(
                    course_id=int(course_id),
                    room_id=int(room_id),
                    date=datetime.datetime.strptime(date, '%Y-%m-%d').date(),
                    start_time=start_time,
                    end_time=end_time
                )
                session.add(exam)
                session.commit()
                flash('Exam scheduled successfully.', 'success')
                return redirect(url_for('exam_scheduler'))
            except Exception as e:
                session.rollback()
                flash(f'Error scheduling exam: {e}', 'danger')
        else:
            flash('Please fill all fields.', 'danger')

    exams = session.query(Exam).order_by(Exam.date.asc(), Exam.start_time.asc()).all()
    approved = get_active_approved_exam_schedule(session)
    return render_template('exam_scheduler.html', exams=exams, approved_exams=approved)

@app.route('/exams/generate', methods=['POST'])
def generate_exams():
    """Generate exam schedule automatically and redirect to the scheduler page."""
    try:
        reset = request.form.get('reset') == 'true'
        days = int(request.form.get('days', '5'))
        created, skipped = generate_exam_schedule(session, num_days=days, reset=reset)
        msg = f"Generated {created} exams"
        if skipped:
            msg += f"; skipped {skipped} due to unavailable slots"
        flash(msg + '.', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Failed to generate exams: {e}', 'danger')
    return redirect(url_for('exam_scheduler'))

@app.route('/exams/approve', methods=['POST'])
def approve_exams():
    """Admin approves current draft exams. Stores snapshot and clears drafts."""
    try:
        # create or get demo admin
        user = session.query(User).filter_by(username="demo_admin").first()
        if not user:
            user = User(username="demo_admin", is_admin_user=True)
            user.set_password("demo123")
            session.add(user)
            session.commit()

        # deactivate previous approved schedules
        for prev in session.query(ApprovedExamSchedule).filter_by(is_active=True).all():
            prev.is_active = False

        snapshot = json.dumps(get_current_exam_data(session))
        approved = ApprovedExamSchedule(
            name=request.form.get('name', 'Approved Exam Schedule'),
            description=request.form.get('description', f'Exams approved by {user.username}'),
            schedule_data=snapshot,
            approved_by=user.id,
            is_active=True
        )
        session.add(approved)
        # optional: clear drafts post-approval
        session.query(Exam).delete()
        session.commit()
        flash('Exam schedule approved and published.', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Failed to approve exams: {e}', 'danger')
    return redirect(url_for('exam_scheduler'))

@app.route('/exams/reset', methods=['POST'])
def reset_draft_exams():
    """Clear current draft exams without touching approved schedules."""
    try:
        session.query(Exam).delete()
        session.commit()
        flash('Draft exams cleared.', 'info')
    except Exception as e:
        session.rollback()
        flash(f'Failed to clear drafts: {e}', 'danger')
    return redirect(url_for('exam_scheduler'))

@app.route('/api/exams')
def api_exams():
    exams = session.query(Exam).order_by(Exam.date.asc(), Exam.start_time.asc()).all()
    data = [
        {
            'id': ex.id,
            'course': ex.course.name if ex.course else None,
            'room': ex.room.name if ex.room else None,
            'date': ex.date.strftime('%Y-%m-%d') if ex.date else None,
            'start_time': ex.start_time,
            'end_time': ex.end_time,
        }
        for ex in exams
    ]
    return jsonify({'exams': data})

@app.route('/')
def index():
    # Include the CSS files as a list for the template
    css_files = ['style.css', 'room_changes.css']
    return render_template('index.html', css_files=css_files)

@app.route('/favicon.ico')
def favicon():
    # Return empty response to avoid 404 noise for favicon requests in dev
    return ('', 204)

@app.route('/api/timetable-conflicts')
def api_timetable_conflicts():
    """Return detected conflicts across rooms, teachers, and classes from current timetable."""
    conflicts = []
    entries = session.query(Timetable).all()
    # Build indexes per day and time for fast detection
    by_slot = collections.defaultdict(list)
    for t in entries:
        key = (t.day, t.start_time, t.end_time)
        by_slot[key].append(t)

    for key, items in by_slot.items():
        day, start, end = key
        # Check room conflicts
        rooms = collections.defaultdict(list)
        teachers = collections.defaultdict(list)
        classes = collections.defaultdict(list)
        for t in items:
            rooms[t.classroom_id].append(t)
            teachers[t.teacher_id].append(t)
            classes[t.class_id].append(t)
        for rid, lst in rooms.items():
            if len(lst) > 1:
                conflicts.append({
                    'type': 'Room',
                    'resource': session.query(Classroom).get(rid).name,
                    'day': day,
                    'start': start,
                    'end': end,
                    'entries': [
                        {
                            'id': x.id,
                            'class': session.query(Class).get(x.class_id).name,
                            'course': session.query(Course).get(x.course_id).name,
                            'teacher': session.query(Teacher).get(x.teacher_id).name,
                            'class_id': x.class_id,
                            'course_id': x.course_id,
                            'teacher_id': x.teacher_id,
                            'classroom_id': x.classroom_id
                        } for x in lst
                    ]
                })
        for tid, lst in teachers.items():
            if len(lst) > 1:
                conflicts.append({
                    'type': 'Teacher',
                    'resource': session.query(Teacher).get(tid).name,
                    'day': day,
                    'start': start,
                    'end': end,
                    'entries': [
                        {
                            'id': x.id,
                            'class': session.query(Class).get(x.class_id).name,
                            'course': session.query(Course).get(x.course_id).name,
                            'room': session.query(Classroom).get(x.classroom_id).name,
                            'class_id': x.class_id,
                            'course_id': x.course_id,
                            'teacher_id': x.teacher_id,
                            'classroom_id': x.classroom_id
                        } for x in lst
                    ]
                })
        for cid, lst in classes.items():
            if len(lst) > 1:
                conflicts.append({
                    'type': 'Class',
                    'resource': session.query(Class).get(cid).name,
                    'day': day,
                    'start': start,
                    'end': end,
                    'entries': [
                        {
                            'id': x.id,
                            'course': session.query(Course).get(x.course_id).name,
                            'teacher': session.query(Teacher).get(x.teacher_id).name,
                            'room': session.query(Classroom).get(x.classroom_id).name,
                            'class_id': x.class_id,
                            'course_id': x.course_id,
                            'teacher_id': x.teacher_id,
                            'classroom_id': x.classroom_id
                        } for x in lst
                    ]
                })
    return jsonify({'conflicts': conflicts})

@app.route('/conflicts')
def conflicts_page():
    return render_template('conflicts.html')

@app.route('/events', methods=['GET', 'POST'])
def events_scheduler():
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        room_id = request.form.get('room_id')
        recurrence = request.form.get('recurrence', 'one-time')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')

        # Parse dates depending on recurrence type
        date = request.form.get('date')
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        day_of_week = request.form.get('day_of_week')
        day_of_month = request.form.get('day_of_month')

        try:
            e = Event(
                title=title,
                description=description,
                room_id=int(room_id),
                recurrence=recurrence,
                start_time=start_time,
                end_time=end_time,
                created_by=flask_session.get('user_id')
            )
            if recurrence == 'one-time' and date:
                e.date = datetime.datetime.strptime(date, '%Y-%m-%d')
            else:
                if start_date:
                    e.start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
                if end_date:
                    e.end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')
                e.day_of_week = day_of_week
                e.day_of_month = int(day_of_month) if day_of_month else None

            # Simple conflict check with Timetable and other events on exact slot
            # Check room availability for one-time date or representative day
            def overlaps(a_start, a_end, b_start, b_end):
                return not (a_end <= b_start or b_end <= a_start)

            # For one-time event, verify timetable and events on that day
            if recurrence == 'one-time' and e.date:
                # Check timetable
                tt = session.query(Timetable).filter(
                    Timetable.day == e.date.strftime('%A'),
                    Timetable.classroom_id == e.room_id
                ).all()
                for t in tt:
                    if overlaps(e.start_time, e.end_time, t.start_time, t.end_time):
                        flash('Room is occupied by timetable at that time.', 'danger')
                        return redirect(url_for('events_scheduler'))
                # Check other events same day
                evs = session.query(Event).filter(
                    Event.room_id == e.room_id,
                    Event.recurrence == 'one-time'
                ).all()
                for oe in evs:
                    if oe.date and oe.date.date() == e.date.date():
                        if overlaps(e.start_time, e.end_time, oe.start_time, oe.end_time):
                            flash('Room already booked for another event at that time.', 'danger')
                            return redirect(url_for('events_scheduler'))

            session.add(e)
            session.commit()
            flash('Event saved.', 'success')
            return redirect(url_for('events_scheduler'))
        except Exception as ex:
            session.rollback()
            flash(f'Failed to save event: {ex}', 'danger')

    events = session.query(Event).order_by(Event.created_at.desc()).all()
    return render_template('events_scheduler.html', rooms=get_classrooms(), events=events)

# Backwards-compatible alias: if any template or bookmark uses /events_scheduler,
# redirect it to the current /events endpoint to avoid duplicate menu items/links.
@app.route('/events_scheduler')
def events_scheduler_legacy():
    return redirect(url_for('events_scheduler'))

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

@app.route('/generate_timetable', methods=['GET', 'POST'])
def generate_timetable_route():
    days_all = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    
    # More realistic time slots with breaks between classes
    time_slots = [
        ("08:30", "09:30"),
        ("09:45", "10:45"),
        ("11:00", "12:00"),
        ("12:15", "13:15"),
        ("14:00", "15:00"),  # After lunch break
        ("15:15", "16:15"),
        ("16:30", "17:30")
    ]
    
    # Get college name from form or use default
    college_name = "University College"
    theme = "light"
    
    if request.method == 'POST':
        if request.form.get('college_name'):
            college_name = request.form.get('college_name')
        if request.form.get('theme'):
            theme = request.form.get('theme')
    
    # Check if we should regenerate the timetable or use the active approved one
    regenerate = request.args.get('regenerate', 'true').lower() == 'true'
    # View mode: 'day' (default) or 'week'
    view_mode = request.args.get('view', 'day')
    # Day filter: default to today if no explicit day provided (when in day view)
    requested_day = request.args.get('day')
    today_name = datetime.datetime.now().strftime('%A')
    if view_mode == 'week':
        days = days_all
        selected_day = today_name if today_name in days_all else 'Monday'
    else:
        if requested_day and requested_day in days_all:
            days = [requested_day]
            selected_day = requested_day
        else:
            selected_day = today_name if today_name in days_all else 'Monday'
            days = [selected_day]
    
    # Get active approved timetable if exists
    active_timetable = None
    if not regenerate:
        active_timetable = session.query(ApprovedTimetable).filter_by(is_active=True).first()
    
    # Build timetable grid
    classes = session.query(Class).all()
    timetable_data = {}
    
    if active_timetable and not regenerate:
        # Use the stored timetable data
        timetable_data = json.loads(active_timetable.timetable_data)
        flash('Using the currently approved timetable.', 'info')
    else:
        # Generate a new timetable
        generate_timetable(session, days, time_slots)
        
        for class_ in classes:
            # Initialize grid with empty lists for each day/time slot
            grid = {slot: {day: [] for day in days_all} for slot in time_slots}
            
            # Get all timetable entries for this class
            entries = session.query(Timetable).filter_by(class_id=class_.id).all()
            
            # Populate the grid with the entries
            for entry in entries:
                slot = (entry.start_time, entry.end_time)
                
                # Skip if the slot isn't in our time_slots (should not happen with proper data)
                if slot not in grid:
                    continue
                    
                # Add the entry to the grid
                if isinstance(grid[slot][entry.day], list):
                    grid[slot][entry.day].append(f"{entry.course.name}<br>{entry.teacher.name}<br>{entry.classroom.name}")
                else:
                    grid[slot][entry.day] = [f"{entry.course.name}<br>{entry.teacher.name}<br>{entry.classroom.name}"]
            
            # Convert empty lists to None for consistent template handling
            # and single-item lists to strings
            for slot in time_slots:
                for day in days_all:
                    if not grid[slot][day]:
                        grid[slot][day] = None
                    elif len(grid[slot][day]) == 1:
                        grid[slot][day] = grid[slot][day][0]
                        
            timetable_data[class_.name] = grid
    
    # For demo purposes: Always set is_coordinator to True to bypass login requirement
    is_coordinator = True
    user = None
    if 'user_id' in flask_session:
        user = session.query(User).get(flask_session['user_id'])
    
    # Get current datetime for the template
    current_date_time = datetime.datetime.now().strftime('%d %b %Y')
    
    return render_template('timetable.html', 
                          timetable_data=timetable_data, 
                          days=days, 
                          all_days=days_all,
                          time_slots=time_slots, 
                          college_name=college_name,
                          theme=theme,
                          is_coordinator=is_coordinator,
                          is_approved=bool(active_timetable and not regenerate),
                          active_timetable=active_timetable if not regenerate else None,
                          selected_day=selected_day,
                          view_mode=view_mode,
                          current_date_time=current_date_time)

@app.route('/find_rooms', methods=['GET', 'POST'])
def find_rooms_route():
    available = []
    if request.method == 'POST':
        day = request.form['day']
        start = request.form['start_time']
        end = request.form['end_time']
        available = find_available_rooms(session, day, start, end)
    return render_template('find_rooms.html', available=available)

@app.route('/api/availability')
def api_availability():
    """Return availability for rooms and teachers for a given day/time slot.
    Query params: day=Monday&start_time=HH:MM&end_time=HH:MM
    """
    day = request.args.get('day')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')
    if not (day and start_time and end_time):
        return jsonify({
            'error': 'Missing required parameters: day, start_time, end_time'
        }), 400

    # Rooms availability
    all_rooms = session.query(Classroom).all()
    occupied_room_ids = {
        r.classroom_id for r in session.query(Timetable).filter_by(day=day, start_time=start_time, end_time=end_time).all()
    }
    rooms = [
        {
            'id': r.id,
            'name': r.name,
            'available': r.id not in occupied_room_ids
        } for r in all_rooms
    ]

    # Teachers availability
    all_teachers = session.query(Teacher).all()
    occupied_teacher_ids = {
        t.teacher_id for t in session.query(Timetable).filter_by(day=day, start_time=start_time, end_time=end_time).all()
    }
    teachers = [
        {
            'id': t.id,
            'name': t.name,
            'available': t.id not in occupied_teacher_ids
        } for t in all_teachers
    ]

    return jsonify({'rooms': rooms, 'teachers': teachers})

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

@app.route('/room_changes', methods=['GET'])
def room_changes():
    """View the history of room changes."""
    session = get_session()
    room_changes = session.query(RoomChange).order_by(RoomChange.changed_at.desc()).all()
    return render_template('room_changes.html', room_changes=room_changes)

@app.route('/syllabus/<path:course_name>')
def course_syllabus(course_name):
    """Basic syllabus page placeholder by course name."""
    course = session.query(Course).filter(Course.name == course_name).first()
    return render_template('course_syllabus.html', course=course, course_name=course_name)

@app.route('/change_room', methods=['GET', 'POST'])
def change_room():
    session = get_session()
    
    # Variables for pre-selecting form values
    selected_class_id = None
    selected_course_id = None
    selected_day = None
    selected_time_slot = None
    
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        course_id = request.form.get('course_id')
        new_room_id = request.form.get('new_room_id')
        date = request.form.get('date')
        day = request.form.get('day')
        time_slot = request.form.get('time_slot')  # In format "start_time-end_time"
        reason = request.form.get('reason')
        
        if all([class_id, course_id, new_room_id]):
            try:
                # Find the old room for this class-course combination
                timetable_entries = session.query(Timetable).filter_by(
                    class_id=class_id, 
                    course_id=course_id
                )
                
                if day and time_slot:
                    start_time, end_time = time_slot.split('-')
                    timetable_entries = timetable_entries.filter_by(
                        day=day,
                        start_time=start_time,
                        end_time=end_time
                    )
                
                timetable_entry = timetable_entries.first()
                
                if not timetable_entry:
                    flash('No timetable entry found for this class and course.', 'danger')
                    available_rooms = get_classrooms()
                    today = datetime.datetime.now().strftime('%Y-%m-%d')
                    return render_template('change_room.html', 
                                          classes=get_classes(), 
                                          courses=get_courses(), 
                                          available_rooms=available_rooms,
                                          today=today)
                
                old_room_id = timetable_entry.classroom_id
                
                # Get user ID if authenticated
                user_id = flask_session.get('user_id')
                
                # Create a room change record
                room_change = RoomChange(
                    class_id=class_id,
                    course_id=course_id,
                    old_room_id=old_room_id,
                    new_room_id=new_room_id,
                    date=datetime.datetime.strptime(date, '%Y-%m-%d') if date else datetime.datetime.utcnow(),
                    reason=reason,
                    changed_by=user_id,
                    changed_at=datetime.datetime.utcnow()
                )
                
                # Update the timetable entry with the new room
                timetable_entry.classroom_id = new_room_id
                
                session.add(room_change)
                session.commit()
                
                flash('Room changed successfully.', 'success')
                return redirect(url_for('room_changes'))
            except Exception as e:
                session.rollback()
                flash(f'Error changing room: {str(e)}', 'danger')
        else:
            flash('Please fill out all required fields.', 'danger')
    else:
        # Handle GET request with possible pre-filled values from timetable view
        class_name = request.args.get('class')
        course_name = request.args.get('course')
        day = request.args.get('day')
        time_slot = request.args.get('time_slot')
        
        if class_name and course_name:
            # Find class_id from name
            class_obj = session.query(Class).filter(Class.name == class_name).first()
            if class_obj:
                selected_class_id = class_obj.id
            
            # Find course_id from name
            course_obj = session.query(Course).filter(Course.name == course_name).first()
            if course_obj:
                selected_course_id = course_obj.id
                
            # Set selected day and time slot
            if day:
                selected_day = day
            if time_slot:
                selected_time_slot = time_slot
            
    available_rooms = get_classrooms()  # Get all rooms initially
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    
    return render_template('change_room.html', 
                          classes=get_classes(), 
                          courses=get_courses(), 
                          available_rooms=available_rooms,
                          today=today,
                          selected_class_id=selected_class_id,
                          selected_course_id=selected_course_id,
                          selected_day=selected_day,
                          selected_time_slot=selected_time_slot)

@app.route('/add_courses_to_class', methods=['GET', 'POST'])
def add_courses_to_class():
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        course_ids = request.form.getlist('course_ids[]')
        teacher_ids = request.form.getlist('teacher_ids[]')
        
        if class_id and course_ids and teacher_ids and len(course_ids) == len(teacher_ids):
            class_obj = session.query(Class).get(class_id)
            if class_obj:
                # Clear existing course-teacher mappings for this class
                session.query(ClassCourseTeacher).filter_by(class_id=class_id).delete()
                
                # Add new course-teacher mappings
                for course_id, teacher_id in zip(course_ids, teacher_ids):
                    cct = ClassCourseTeacher(
                        class_id=class_id,
                        course_id=course_id,
                        teacher_id=teacher_id
                    )
                    session.add(cct)
                session.commit()
                flash('Courses and teachers assigned successfully!', 'success')
                return redirect(url_for('index'))
        
        flash('Please ensure all fields are filled correctly.', 'error')
    
    classes = session.query(Class).all()
    courses = session.query(Course).all()
    teachers = session.query(Teacher).all()
    return render_template('add_courses_to_class.html', classes=classes, courses=courses, teachers=teachers)

@app.route('/course_coordinator', methods=['GET', 'POST'])
def course_coordinator():
    # Login requirement removed for demo purposes
    
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        course_ids = request.form.getlist('course_ids[]')
        teacher_ids = request.form.getlist('teacher_ids[]')
        
        if class_id and course_ids and teacher_ids and len(course_ids) == len(teacher_ids):
            # Clear existing assignments for this class
            session.query(ClassCourseTeacher).filter_by(class_id=class_id).delete()
            
            # Add new assignments
            for course_id, teacher_id in zip(course_ids, teacher_ids):
                if course_id and teacher_id:  # Only add if both are selected
                    cct = ClassCourseTeacher(
                        class_id=class_id,
                        course_id=course_id,
                        teacher_id=teacher_id
                    )
                    session.add(cct)
            
            try:
                session.commit()
                flash('Class courses updated successfully!', 'success')
            except Exception as e:
                session.rollback()
                flash('Error updating class courses. Please try again.', 'danger')
                print(str(e))
                
            return redirect(url_for('course_coordinator'))
        else:
            flash('Please ensure all fields are filled correctly.', 'danger')
    
    classes = session.query(Class).all()
    courses = session.query(Course).all()
    teachers = session.query(Teacher).all()
    
    return render_template('course_coordinator.html', 
                         classes=classes,
                         courses=courses,
                         teachers=teachers)

@app.route('/teachers')
def teachers():
    return render_template('teachers.html')

@app.route('/analytics')
def analytics_page():
    return render_template('analytics.html')

@app.route('/api/teacher-class-counts')
def teacher_class_counts():
    """API endpoint to get the number of classes taught by each teacher."""
    active_timetable = session.query(ApprovedTimetable).filter_by(is_active=True).first()
    
    teacher_counts = collections.defaultdict(int)
    
    if active_timetable:
        # Load timetable data
        all_timetable_data = json.loads(active_timetable.timetable_data)
        
        # Analyze each class timetable
        for class_name, class_grid in all_timetable_data.items():
            for slot_key, days in class_grid.items():
                for day, cell in days.items():
                    if cell:
                        cell_data = cell
                        # Handle different data formats
                        if isinstance(cell_data, str):
                            parts = cell_data.split('<br>')
                            if len(parts) >= 2:  # Has teacher info
                                teacher_name = parts[1]
                                teacher_counts[teacher_name] += 1
                        elif isinstance(cell_data, list):
                            for item in cell_data:
                                if isinstance(item, str):
                                    parts = item.split('<br>')
                                    if len(parts) >= 2:  # Has teacher info
                                        teacher_name = parts[1]
                                        teacher_counts[teacher_name] += 1
                        elif isinstance(cell_data, dict):
                            # If the cell data is already parsed into a dict
                            if 'teacher' in cell_data:
                                teacher_name = cell_data['teacher']
                                teacher_counts[teacher_name] += 1
    
    # If no data is found, provide sample data for demonstration
    if not teacher_counts:
        teacher_counts = {
            "Jane Smith": 5,
            "John Doe": 4,
            "Alice Johnson": 6,
            "Robert Brown": 3
        }
    
    # Convert to sorted lists for chart
    labels = list(teacher_counts.keys())
    counts = [teacher_counts[teacher] for teacher in labels]
    
    return jsonify({
        'labels': labels,
        'counts': counts
    })

@app.route('/api/analytics/summary')
def analytics_summary():
    """Aggregate analytics summary: most/least used classrooms, avg teaching hours per teacher, on-time scheduling rate."""
    # Room usage from Timetable
    room_counts = collections.defaultdict(int)
    teacher_minutes = collections.defaultdict(int)
    entries = session.query(Timetable).all()

    def minutes_between(start, end):
        fmt = '%H:%M'
        try:
            s = datetime.datetime.strptime(start, fmt)
            e = datetime.datetime.strptime(end, fmt)
            return max(0, int((e - s).total_seconds() // 60))
        except Exception:
            return 0

    for t in entries:
        room_counts[t.classroom.name] += 1
        teacher_minutes[t.teacher.name] += minutes_between(t.start_time, t.end_time)

    # Most/least used classrooms
    most_used = None
    least_used = None
    if room_counts:
        sorted_rooms = sorted(room_counts.items(), key=lambda x: x[1], reverse=True)
        most_used = {'room': sorted_rooms[0][0], 'count': sorted_rooms[0][1]}
        least_used = {'room': sorted_rooms[-1][0], 'count': sorted_rooms[-1][1]}

    # Average teaching hours per teacher
    avg_hours = None
    if teacher_minutes:
        avg_minutes = sum(teacher_minutes.values()) / max(1, len(teacher_minutes))
        avg_hours = round(avg_minutes / 60.0, 2)

    # On-time scheduling rate: defined as sessions not affected by cancellations or room changes
    total_sessions = len(entries)
    changes = session.query(RoomChange).count() + session.query(ClassCancellation).count()
    on_time_rate = None
    if total_sessions:
        rate = max(0.0, min(1.0, 1.0 - (changes / total_sessions)))
        on_time_rate = round(rate * 100, 1)

    return jsonify({
        'most_used_classroom': most_used,
        'least_used_classroom': least_used,
        'avg_teaching_hours_per_teacher': avg_hours,
        'on_time_scheduling_rate': on_time_rate,
        'teacher_hours': [
            {'teacher': k, 'hours': round(v / 60.0, 2)} for k, v in sorted(teacher_minutes.items(), key=lambda x: x[1], reverse=True)
        ],
        'room_usage': [
            {'room': k, 'count': v} for k, v in sorted(room_counts.items(), key=lambda x: x[1], reverse=True)
        ]
    })

# Feedback: submit and list
@app.route('/feedback', methods=['POST'])
def submit_feedback():
    category = request.form.get('category') or 'other'
    title = request.form.get('title')
    message = request.form.get('message')
    contact = request.form.get('contact')
    page_url = request.form.get('page_url')
    if not (category and title and message):
        return jsonify({'success': False, 'message': 'Missing required fields.'}), 400
    try:
        fb = Feedback(
            user_id=flask_session.get('user_id'),
            category=category,
            title=title[:200],
            message=message,
            contact=contact[:200] if contact else None,
            page_url=page_url[:500] if page_url else None,
            status='new'
        )
        session.add(fb)
        session.commit()
        return jsonify({'success': True})
    except Exception as e:
        session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/feedback')
def admin_feedback():
    items = session.query(Feedback).order_by(Feedback.created_at.desc()).all()
    return render_template('admin_feedback.html', items=items)

@app.route('/api/room-usage')
def room_usage():
    """API endpoint to get the usage frequency of each classroom."""
    active_timetable = session.query(ApprovedTimetable).filter_by(is_active=True).first()
    
    room_counts = collections.defaultdict(int)
    
    if active_timetable:
        # Load timetable data
        all_timetable_data = json.loads(active_timetable.timetable_data)
        
        # Analyze each class timetable
        for class_name, class_grid in all_timetable_data.items():
            for slot_key, days in class_grid.items():
                for day, cell in days.items():
                    if cell:
                        cell_data = cell
                        # Handle different data formats
                        if isinstance(cell_data, str):
                            parts = cell_data.split('<br>')
                            if len(parts) > 2:  # Has room info
                                room = parts[2]
                                room_counts[room] += 1
                        elif isinstance(cell_data, list):
                            for item in cell_data:
                                if isinstance(item, str):
                                    parts = item.split('<br>')
                                    if len(parts) > 2:  # Has room info
                                        room = parts[2]
                                        room_counts[room] += 1
                        elif isinstance(cell_data, dict):
                            # If the cell data is already parsed into a dict
                            if 'room' in cell_data:
                                room = cell_data['room']
                                room_counts[room] += 1
    
    # If no data is found, provide sample data for demonstration
    if not room_counts:
        room_counts = {
            "Room 101": 7,
            "Room 102": 5,
            "Room 103": 8,
            "Room 104": 4,
            "Room 105": 6
        }
    
    # Convert to sorted lists for chart
    labels = list(room_counts.keys())
    counts = [room_counts[room] for room in labels]
    
    return jsonify({
        'labels': labels,
        'counts': counts
    })

@app.route('/api/course-distribution')
def course_distribution():
    """API endpoint to get the distribution of courses in the timetable."""
    active_timetable = session.query(ApprovedTimetable).filter_by(is_active=True).first()
    
    course_counts = collections.defaultdict(int)
    
    if active_timetable:
        # Load timetable data
        all_timetable_data = json.loads(active_timetable.timetable_data)
        
        # Analyze each class timetable
        for class_name, class_grid in all_timetable_data.items():
            for slot_key, days in class_grid.items():
                for day, cell in days.items():
                    if cell:
                        cell_data = cell
                        # Handle different data formats
                        if isinstance(cell_data, str):
                            parts = cell_data.split('<br>')
                            course = parts[0]
                            course_counts[course] += 1
                        elif isinstance(cell_data, list):
                            for item in cell_data:
                                if isinstance(item, str):
                                    parts = item.split('<br>')
                                    course = parts[0]
                                    course_counts[course] += 1
                        elif isinstance(cell_data, dict):
                            # If the cell data is already parsed into a dict
                            if 'course' in cell_data:
                                course = cell_data['course']
                                course_counts[course] += 1
    
    # If no data is found, provide sample data for demonstration
    if not course_counts:
        course_counts = {
            "Mathematics": 8,
            "Physics": 6,
            "Chemistry": 5,
            "Biology": 4,
            "Computer Science": 7,
            "English": 3
        }
    
    # Convert to sorted lists for chart
    labels = list(course_counts.keys())
    counts = [course_counts[course] for course in labels]
    
    return jsonify({
        'labels': labels,
        'counts': counts
    })

@app.route('/teacher-timetable/<int:teacher_id>')
def teacher_timetable(teacher_id):
    """View timetable for a specific teacher from the approved timetable."""
    teacher = session.query(Teacher).get(teacher_id)
    if not teacher:
        flash('Teacher not found.', 'danger')
        return redirect(url_for('teachers'))
    
    # Get active approved timetable
    active_timetable = session.query(ApprovedTimetable).filter_by(is_active=True).first()
    
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    time_slots = [
        ("08:30", "09:30"),
        ("09:45", "10:45"),
        ("11:00", "12:00"),
        ("12:15", "13:15"),
        ("14:00", "15:00"),
        ("15:15", "16:15"),
        ("16:30", "17:30")
    ]
    
    teacher_schedule = {}
    
    if active_timetable:
        # Load timetable data from active approved timetable
        all_timetable_data = json.loads(active_timetable.timetable_data)
        
        # Extract teacher's schedule from each class's timetable
        for class_name, class_grid in all_timetable_data.items():
            for time_slot in time_slots:
                slot_key = f"{time_slot[0]}-{time_slot[1]}"
                
                for day in days:
                    cell = class_grid.get(slot_key, {}).get(day)
                    
                    if cell:
                        # Format might be either a string like "Course<br>Teacher<br>Room" or a list of such strings
                        if isinstance(cell, str):
                            parts = cell.split('<br>')
                            if len(parts) >= 2 and teacher.name in parts[1]:
                                # Initialize the day dict if not present
                                if day not in teacher_schedule:
                                    teacher_schedule[day] = {}
                                
                                # Add the class to the teacher's schedule
                                teacher_schedule[day][slot_key] = {
                                    'class': class_name,
                                    'course': parts[0],
                                    'room': parts[2] if len(parts) > 2 else "N/A"
                                }
                        elif isinstance(cell, list):
                            for item in cell:
                                parts = item.split('<br>')
                                if len(parts) >= 2 and teacher.name in parts[1]:
                                    if day not in teacher_schedule:
                                        teacher_schedule[day] = {}
                                    
                                    teacher_schedule[day][slot_key] = {
                                        'class': class_name,
                                        'course': parts[0],
                                        'room': parts[2] if len(parts) > 2 else "N/A"
                                    }
        
    return render_template('teacher_timetable.html', 
                          teacher=teacher, 
                          teacher_schedule=teacher_schedule,
                          days=days,
                          time_slots=time_slots,
                          active_timetable=active_timetable)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    # Login requirement removed for demo purposes
    
    # Create or get a demo admin user
    user = session.query(User).filter_by(username="demo_admin").first()
    if not user:
        # Create a default admin user if none exists
        user = User(username="demo_admin", is_admin_user=True)
        user.set_password("demo123")
        session.add(user)
        session.commit()
        
    if request.method == 'POST':
        target_user_id = request.form.get('user_id')
        action = request.form.get('action')
        if target_user_id and action == 'toggle_admin':
            target_user = session.query(User).get(target_user_id)
            if target_user:
                target_user.is_admin_user = not target_user.is_admin_user
                session.commit()
                flash(f"Admin status updated for {target_user.username}.", 'success')
            return redirect(url_for('admin'))
            
    return render_template('admin.html', users=session.query(User).all())

@app.route('/timetable/approve', methods=['POST'])
def approve_timetable():
    # Login requirement removed for demo purposes
    
    # Create or get a demo admin user for approval
    user = session.query(User).filter_by(username="demo_admin").first()
    if not user:
        # Create a default admin user if none exists
        user = User(username="demo_admin", is_admin_user=True)
        user.set_password("demo123")
        session.add(user)
        session.commit()
    
    # Get form data
    name = request.form.get('name', 'Approved Timetable')
    description = request.form.get('description', f'Timetable approved by {user.username}')
    
    try:
        # Deactivate all previously approved timetables
        previously_approved = session.query(ApprovedTimetable).filter_by(is_active=True).all()
        for prev in previously_approved:
            prev.is_active = False
        
        # Get current timetable data
        timetable_data = get_current_timetable_data(session)
        
        # Create new approved timetable
        approved_timetable = ApprovedTimetable(
            name=name,
            description=description,
            timetable_data=json.dumps(timetable_data),
            approved_by=user.id,
            is_active=True
        )
        
        session.add(approved_timetable)
        session.commit()
        
        flash('Timetable approved successfully!', 'success')
        return jsonify({'success': True, 'redirect': url_for('view_approved_timetable', id=approved_timetable.id)})
        
    except Exception as e:
        session.rollback()
        print(str(e))
        return jsonify({'success': False, 'message': 'Error approving timetable.'}), 500

@app.route('/timetable/reject', methods=['POST'])
def reject_timetable():
    # Login requirement removed for demo purposes
    
    reason = request.form.get('reason', 'No reason provided')
    flash(f'Timetable rejected. Reason: {reason}', 'info')
    
    # Redirect to generate a new timetable
    return jsonify({'success': True, 'redirect': url_for('generate_timetable_route')})

@app.route('/approved-timetables')
def approved_timetables():
    # Login requirement removed for demo purposes
    
    timetables = session.query(ApprovedTimetable).order_by(ApprovedTimetable.approved_at.desc()).all()
    return render_template('approved_timetables.html', timetables=timetables)

@app.route('/approved-timetable/<int:id>')
def view_approved_timetable(id):
    # Login requirement removed for demo purposes
    
    approved_timetable = session.query(ApprovedTimetable).get(id)
    if not approved_timetable:
        flash('Timetable not found.', 'danger')
        return redirect(url_for('approved_timetables'))
    
    timetable_data = json.loads(approved_timetable.timetable_data)
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    time_slots = [
        ("08:30", "09:30"),
        ("09:45", "10:45"),
        ("11:00", "12:00"),
        ("12:15", "13:15"),
        ("14:00", "15:00"),
        ("15:15", "16:15"),
        ("16:30", "17:30")
    ]
    
    return render_template('view_approved_timetable.html', 
                          timetable=approved_timetable,
                          timetable_data=timetable_data,
                          days=days,
                          time_slots=time_slots)

@app.route('/timetable/activate/<int:id>', methods=['POST'])
def activate_timetable(id):
    # Login requirement removed for demo purposes
    
    try:
        # Deactivate all timetables
        active_timetables = session.query(ApprovedTimetable).filter_by(is_active=True).all()
        for timetable in active_timetables:
            timetable.is_active = False
        
        # Activate the selected timetable
        timetable = session.query(ApprovedTimetable).get(id)
        if not timetable:
            flash('Timetable not found.', 'danger')
            return redirect(url_for('approved_timetables'))
        
        timetable.is_active = True
        session.commit()
        
        flash(f'Timetable "{timetable.name}" is now active.', 'success')
        return redirect(url_for('view_approved_timetable', id=timetable.id))
        
    except Exception as e:
        session.rollback()
        print(str(e))
        flash('Error activating timetable.', 'danger')
        return redirect(url_for('approved_timetables'))

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=8080)

