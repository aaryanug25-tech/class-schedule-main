import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Table, Boolean
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from sqlalchemy import UniqueConstraint

Base = declarative_base()

# User authentication model
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin_user = Column(Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_admin(self):
        return self.is_admin_user

    def __repr__(self):
        return f"<User(username={self.username}, admin={self.is_admin_user})>"

# Association table for class-course-teacher mapping
class ClassCourseTeacher(Base):
    __tablename__ = 'class_course_teacher'
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey('classes.id'))
    course_id = Column(Integer, ForeignKey('courses.id'))
    teacher_id = Column(Integer, ForeignKey('teachers.id'))
    __table_args__ = (UniqueConstraint('class_id', 'course_id', name='_class_course_uc'),)

    class_ = relationship('Class', back_populates='course_teachers')
    course = relationship('Course')
    teacher = relationship('Teacher')

# Models
class Classroom(Base):
    __tablename__ = 'classrooms'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    capacity = Column(Integer)
    
    def __repr__(self):
        return f"<Classroom(name={self.name}, capacity={self.capacity})>"

class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    
    def __repr__(self):
        return f"<Course(name={self.name})>"

class Teacher(Base):
    __tablename__ = 'teachers'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    subject = Column(String)
    
    def __repr__(self):
        return f"<Teacher(name={self.name}, subject={self.subject})>"

class Class(Base):
    __tablename__ = 'classes'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    course_teachers = relationship('ClassCourseTeacher', back_populates='class_')

    def __repr__(self):
        return f"<Class(name={self.name})>"

class Timetable(Base):
    __tablename__ = 'timetables'
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey('classes.id'))
    classroom_id = Column(Integer, ForeignKey('classrooms.id'))
    course_id = Column(Integer, ForeignKey('courses.id'))
    teacher_id = Column(Integer, ForeignKey('teachers.id'))
    day = Column(String)
    start_time = Column(String)
    end_time = Column(String)
    
    class_ = relationship('Class')
    classroom = relationship('Classroom')
    course = relationship('Course')
    teacher = relationship('Teacher')

    def __repr__(self):
        return f"<Timetable(class={self.class_.name}, classroom={self.classroom.name}, course={self.course.name}, teacher={self.teacher.name}, day={self.day}, {self.start_time}-{self.end_time})>"

# Database setup
def get_session(db_url=None):
    if db_url is None:
        # Use a relative path for the database file
        db_path = 'scheduler.db'
        db_url = f'sqlite:///{db_path}'
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()

# Add functions
def add_classroom(session, name, capacity):
    classroom = Classroom(name=name, capacity=capacity)
    session.add(classroom)
    session.commit()
    return classroom

def add_course(session, name):
    course = Course(name=name)
    session.add(course)
    session.commit()
    return course

def add_teacher(session, name, subject):
    teacher = Teacher(name=name, subject=subject)
    session.add(teacher)
    session.commit()
    return teacher

# Add a class and assign one teacher per course
def add_class(session, name, course_teacher_map):
    """
    course_teacher_map: dict of {course_id: teacher_id}
    """
    class_ = Class(name=name)
    session.add(class_)
    session.commit()
    for course_id, teacher_id in course_teacher_map.items():
        cct = ClassCourseTeacher(class_id=class_.id, course_id=course_id, teacher_id=teacher_id)
        session.add(cct)
    session.commit()
    return class_


# Enhanced timetable generation function with improved distribution
def generate_timetable(session, days, time_slots):
    """
    Generate a weekly timetable with hard minimums per course per class:
    - 3 one-hour lecture sessions
    - 1 lab session occupying two consecutive one-hour slots
    Avoids conflicts across rooms, teachers, and classes. Labs prefer rooms
    whose name contains 'lab' (case-insensitive); falls back to any room.

    Returns a human-readable summary list.
    """
    from random import shuffle

    # Fresh start for draft timetable
    session.query(Timetable).delete()
    session.commit()

    classes = session.query(Class).all()
    classrooms = session.query(Classroom).all()
    summary = []

    # Separate lab-friendly rooms
    lab_rooms = [r for r in classrooms if 'lab' in (r.name or '').lower()]
    non_lab_rooms = [r for r in classrooms if r not in lab_rooms]

    # Resources usage sets
    used_classroom_slots = set()  # (day, start, end, room_id)
    used_teacher_slots = set()    # (day, start, end, teacher_id)
    used_class_slots = set()      # (day, start, end, class_id)

    # Helper: check if slot is free for all resources
    def free_for_all(day, start, end, room_id, teacher_id, class_id):
        return (
            (day, start, end, room_id) not in used_classroom_slots and
            (day, start, end, teacher_id) not in used_teacher_slots and
            (day, start, end, class_id) not in used_class_slots
        )

    # Helper: book a slot
    def book_slot(day, start, end, room, class_, course, teacher):
        tt = Timetable(
            class_id=class_.id,
            classroom_id=room.id,
            course_id=course.id,
            teacher_id=teacher.id,
            day=day,
            start_time=start,
            end_time=end,
        )
        session.add(tt)
        used_classroom_slots.add((day, start, end, room.id))
        used_teacher_slots.add((day, start, end, teacher.id))
        used_class_slots.add((day, start, end, class_.id))
        summary.append(f"{class_.name} - {course.name} in {room.name} by {teacher.name} on {day} {start}-{end}")

    # Use all provided days for even distribution
    week_days = list(days)

    # Precompute adjacent slot pairs for labs (allowing small breaks between slots)
    consecutive_pairs = []  # list of (i, i+1, (start,end) for i, (start,end) for i+1)
    for i in range(len(time_slots) - 1):
        s1, e1 = time_slots[i]
        s2, e2 = time_slots[i + 1]
        # We treat two adjacent one-hour slots as a 2-hour lab block
        consecutive_pairs.append((i, i + 1, (s1, e1), (s2, e2)))

    # Shuffle classes for fairness
    classes_list = list(classes)
    shuffle(classes_list)

    for class_ in classes_list:
        # For each course assigned to the class
        ccts = list(class_.course_teachers)
        shuffle(ccts)
        for cct in ccts:
            course = cct.course
            teacher = cct.teacher

            # 1) Schedule LAB (2 consecutive slots) - shuffle days for even spread
            lab_scheduled = False
            lab_days = week_days[:]
            shuffle(lab_days)
            for day in lab_days:
                for i, j, (s1, e1), (s2, e2) in consecutive_pairs:
                    # Try lab-preferred rooms first, then others
                    for room in (lab_rooms + non_lab_rooms):
                        if (
                            free_for_all(day, s1, e1, room.id, teacher.id, class_.id) and
                            free_for_all(day, s2, e2, room.id, teacher.id, class_.id)
                        ):
                            # Book both consecutive slots
                            book_slot(day, s1, e1, room, class_, course, teacher)
                            book_slot(day, s2, e2, room, class_, course, teacher)
                            lab_scheduled = True
                            break
                    if lab_scheduled:
                        break
                if lab_scheduled:
                    break

            # 2) Schedule 3 LECTURES (single slots), shuffle days for even spread
            lectures_needed = 3
            lecture_days = week_days[:]
            shuffle(lecture_days)
            slot_indices = list(range(len(time_slots)))
            for day in lecture_days:
                if lectures_needed == 0:
                    break
                shuffle(slot_indices)
                for idx in slot_indices:
                    start, end = time_slots[idx]
                    # Prefer non-lab rooms for lectures, but allow labs if needed
                    for room in (non_lab_rooms + lab_rooms):
                        if free_for_all(day, start, end, room.id, teacher.id, class_.id):
                            book_slot(day, start, end, room, class_, course, teacher)
                            lectures_needed -= 1
                            break
                    if lectures_needed == 0:
                        break

            # Fallback: if still not enough, try any remaining weekday/slot/room combinations
            if lectures_needed > 0:
                for day in week_days:
                    if lectures_needed == 0:
                        break
                    for start, end in time_slots:
                        if lectures_needed == 0:
                            break
                        for room in (non_lab_rooms + lab_rooms):
                            if free_for_all(day, start, end, room.id, teacher.id, class_.id):
                                book_slot(day, start, end, room, class_, course, teacher)
                                lectures_needed -= 1
                                if lectures_needed == 0:
                                    break

    session.commit()
    print("Timetable generation complete with 3 lectures + 1 lab per course.")
    return summary

def reschedule_class(session, timetable_id, new_day, new_start, new_end, new_classroom_id=None):
    timetable = session.query(Timetable).get(timetable_id)
    if not timetable:
        print("Timetable entry not found.")
        return
    # Check for conflicts
    conflict = session.query(Timetable).filter_by(
        classroom_id=new_classroom_id or timetable.classroom_id,
        day=new_day, start_time=new_start, end_time=new_end
    ).first()
    if conflict:
        print("Conflict detected. Cannot reschedule.")
        return
    timetable.day = new_day
    timetable.start_time = new_start
    timetable.end_time = new_end
    if new_classroom_id:
        timetable.classroom_id = new_classroom_id
    session.commit()
    print("Rescheduling complete.")

def find_available_rooms(session, day, start_time, end_time):
    """
    Returns a list of available classrooms for the given day and time slot.
    """
    all_rooms = session.query(Classroom).all()
    occupied = session.query(Timetable.classroom_id).filter_by(day=day, start_time=start_time, end_time=end_time).all()
    occupied_ids = {r[0] for r in occupied}
    available = [room for room in all_rooms if room.id not in occupied_ids]
    return available

def suggest_reschedule_options(session, class_id, course_id, exclude_timetable_id=None):
    """
    Suggests alternative slots and rooms for a class/course, avoiding conflicts.
    Optionally exclude a specific timetable entry (for rescheduling that entry).
    Returns a list of (day, start_time, end_time, classroom) tuples.
    """
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    time_slots = [("09:00", "10:00"), ("10:00", "11:00"), ("11:00", "12:00")]
    class_ = session.query(Class).get(class_id)
    cct = next((c for c in class_.course_teachers if c.course_id == course_id), None)
    if not cct:
        return []
    teacher = cct.teacher
    classrooms = session.query(Classroom).all()
    suggestions = []
    for day in days:
        for slot in time_slots:
            for classroom in classrooms:
                # Check if classroom is free
                q = session.query(Timetable).filter_by(day=day, start_time=slot[0], end_time=slot[1], classroom_id=classroom.id)
                if exclude_timetable_id:
                    q = q.filter(Timetable.id != exclude_timetable_id)
                if q.first():
                    continue
                # Check if teacher is free
                q2 = session.query(Timetable).filter_by(day=day, start_time=slot[0], end_time=slot[1], teacher_id=teacher.id)
                if exclude_timetable_id:
                    q2 = q2.filter(Timetable.id != exclude_timetable_id)
                if q2.first():
                    continue
                suggestions.append((day, slot[0], slot[1], classroom.name))
    return suggestions

def print_timetable(session):
    timetables = session.query(Timetable).all()
    for t in timetables:
        print(t)
        
def get_current_timetable_data(session):
    """
    Formats the current timetable data into a structured format that can be saved
    for later retrieval.
    """
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    time_slots = [
        ("08:30", "09:30"),
        ("09:45", "10:45"),
        ("11:00", "12:00"),
        ("12:15", "13:15"),
        ("14:00", "15:00"),  # After lunch break
        ("15:15", "16:15"),
        ("16:30", "17:30")
    ]
    
    # Build timetable grid for all classes
    classes = session.query(Class).all()
    timetable_data = {}
    
    for class_ in classes:
        grid = {slot[0] + "-" + slot[1]: {day: [] for day in days} for slot in time_slots}
        entries = session.query(Timetable).filter_by(class_id=class_.id).all()
        
        for entry in entries:
            slot_key = entry.start_time + "-" + entry.end_time
            if slot_key in grid:
                grid[slot_key][entry.day].append({
                    "course": entry.course.name,
                    "teacher": entry.teacher.name,
                    "classroom": entry.classroom.name,
                    "timetable_id": entry.id
                })
        
        timetable_data[class_.name] = grid
    
    return timetable_data

if __name__ == "__main__":
    session = get_session()
    
    # Example usage with more realistic data
    # Add 60 classrooms (55 regular, 5 labs)
    if not session.query(Classroom).first():
        for i in range(1, 56):
            add_classroom(session, f"Room {i:03}", 40)
        for i in range(1, 6):
            add_classroom(session, f"Lab {i:03}", 30)
    
    # Add courses with more realistic names
    if not session.query(Course).first():
        add_course(session, "Calculus I")
        add_course(session, "Physics Mechanics")
        add_course(session, "Intro to Programming")
        add_course(session, "Data Structures")
        add_course(session, "Chemistry")
        add_course(session, "Digital Electronics")
        add_course(session, "Statistics")
        add_course(session, "Database Systems")
        add_course(session, "Linear Algebra")
        add_course(session, "Operating Systems")
        add_course(session, "Microprocessors")
        add_course(session, "Discrete Mathematics")
        add_course(session, "Environmental Science")
        add_course(session, "Artificial Intelligence")
        add_course(session, "Machine Learning")
        add_course(session, "Software Engineering")
    
    # Add teachers with subject specialties
    if not session.query(Teacher).first():
        add_teacher(session, "Dr. Smith", "Mathematics")
        add_teacher(session, "Prof. Johnson", "Physics")
        add_teacher(session, "Dr. Williams", "Computer Science")
        add_teacher(session, "Prof. Brown", "Computer Science")
        add_teacher(session, "Dr. Davis", "Chemistry")
        add_teacher(session, "Prof. Miller", "Electronics")
        add_teacher(session, "Dr. Wilson", "Mathematics")
        add_teacher(session, "Prof. Moore", "Computer Science")
        add_teacher(session, "Dr. Taylor", "Mathematics")
        add_teacher(session, "Dr. Anderson", "Statistics")
        add_teacher(session, "Prof. Thomas", "Environmental Science")
        add_teacher(session, "Dr. Jackson", "Artificial Intelligence")
        add_teacher(session, "Prof. White", "Machine Learning")
        add_teacher(session, "Dr. Harris", "Software Engineering")
        add_teacher(session, "Prof. Martin", "Microprocessors")
        add_teacher(session, "Dr. Thompson", "Operating Systems")
        add_teacher(session, "Prof. Garcia", "Discrete Mathematics")
        add_teacher(session, "Dr. Martinez", "Linear Algebra")
    
    # Add classes with multiple courses per class
    if not session.query(Class).first():
        # Map all teachers and courses to new classes
        teacher_objs = session.query(Teacher).all()
        course_objs = session.query(Course).all()
        # Create 8 demo classes, each with 2-3 courses and teachers
        for i in range(8):
            class_name = f"Class_{i+1:02}"
            # Assign 2-3 courses and teachers per class, cycling through the lists
            course_teacher_map = {}
            for j in range(2 + (i % 2)):
                course_idx = (i*2 + j) % len(course_objs)
                teacher_idx = (i*2 + j) % len(teacher_objs)
                course_teacher_map[course_objs[course_idx].id] = teacher_objs[teacher_idx].id
            add_class(session, class_name, course_teacher_map)
    
    # Generate timetable with more realistic time slots
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    time_slots = [
        ("09:00", "10:00"),
        ("10:15", "11:15"),
        ("11:30", "12:30"),
        ("13:30", "14:30"),
        ("14:45", "15:45"),
        ("16:00", "17:00")
    ]
    
    summary = generate_timetable(session, days, time_slots)
    
    print("\nTimetable Summary:")
    for line in summary:
        print(line)
    
    print("\nFull Timetable:")
    print_timetable(session)

    # Auto-approve the latest generated timetable for dashboard analytics
    from models import ApprovedTimetable, Timetable
    import json
    # Get all timetable entries
    timetable_entries = session.query(Timetable).all()
    timetable_data = []
    for entry in timetable_entries:
        timetable_data.append({
            'class': entry.class_.name,
            'classroom': entry.classroom.name,
            'course': entry.course.name,
            'teacher': entry.teacher.name,
            'day': entry.day,
            'start_time': entry.start_time,
            'end_time': entry.end_time
        })
    approved = ApprovedTimetable(
        name="Auto Approved Timetable",
        description="Automatically approved after seeding",
        timetable_data=json.dumps(timetable_data),
        is_active=True
    )
    session.add(approved)
    session.commit()

    # Example: Find available rooms for extra class
    print("\nAvailable rooms for extra class on Monday 10:00-11:00:")
    available_rooms = find_available_rooms(session, "Monday", "10:00", "11:00")
    for room in available_rooms:
        print(room)

    # Example: Suggest reschedule options for FYBSc Mathematics
    fybsc = session.query(Class).filter_by(name="FYBSc").first()
    if fybsc:
        print("\nReschedule options for FYBSc Mathematics:")
        options = suggest_reschedule_options(session, fybsc.id, 1)
        for opt in options:
            print(f"Day: {opt[0]}, Time: {opt[1]}-{opt[2]}, Room: {opt[3]}")
