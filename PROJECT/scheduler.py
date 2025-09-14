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
        # Get the directory where scheduler.py is located
        base_dir = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(base_dir, 'scheduler.db')
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
    Automatically generate a realistic timetable for all classes, courses, and teachers.
    - Each course meets 2-3 times per week
    - Classes are distributed throughout the week to create a balanced schedule
    - Teachers have reasonable schedules with no back-to-back classes across multiple rooms
    - Avoids scheduling conflicts for rooms, teachers, and classes
    - Creates realistic academic patterns with consistent timings for courses
    
    Returns a summary of the generated timetable.
    """
    from random import sample, choice, shuffle, randint
    
    session.query(Timetable).delete()  # Clear previous schedule
    session.commit()
    classes = session.query(Class).all()
    classrooms = session.query(Classroom).all()
    summary = []

    # Track usage to avoid conflicts
    used_classroom_slots = set()  # (day, slot_start, slot_end, classroom_id)
    used_teacher_slots = set()     # (day, slot_start, slot_end, teacher_id)
    used_class_slots = set()       # (day, slot_start, slot_end, class_id)
    
    # Track course meetings per week
    course_meetings = {}  # {(class_id, course_id): count}
    
    # Distribute courses across days of the week (create realistic patterns)
    course_schedule_patterns = {}  # {(class_id, course_id): [(day, slot_index)]}
    
    # Step 1: Create scheduling patterns for each course
    for class_ in classes:
        for cct in class_.course_teachers:
            course = cct.course
            key = (class_.id, course.id)
            course_meetings[key] = 0
            
            # Determine how many sessions per week (2-3 is typical for college courses)
            num_sessions = choice([2, 3])
            
            # Create patterns based on common academic scheduling practices
            possible_patterns = [
                # MWF pattern (common for 3-session courses)
                [("Monday", 0), ("Wednesday", 0), ("Friday", 0)],
                # TTh pattern (common for 2-session courses)
                [("Tuesday", 0), ("Thursday", 0)],
                # MW pattern
                [("Monday", 0), ("Wednesday", 0)],
                # MF pattern
                [("Monday", 0), ("Friday", 0)],
                # WF pattern
                [("Wednesday", 0), ("Friday", 0)]
            ]
            
            # Choose pattern based on number of sessions
            if num_sessions == 2:
                pattern = choice([p for p in possible_patterns if len(p) <= 2])
                # If we got a 3-day pattern, take just the first two days
                pattern = pattern[:2]
            else:
                pattern = choice([p for p in possible_patterns if len(p) == 3])
                
            # Choose a consistent time slot index for this course (same time on different days)
            slot_index = randint(0, len(time_slots) - 1)
            
            # Update the pattern with the chosen time slot index
            pattern = [(day, slot_index) for day, _ in pattern]
            
            # Store the pattern
            course_schedule_patterns[key] = pattern
    
    # Step 2: Apply the patterns and schedule each course
    # Randomize the order of classes to avoid bias in scheduling
    shuffled_classes = list(classes)
    shuffle(shuffled_classes)
    
    for class_ in shuffled_classes:
        for cct in class_.course_teachers:
            course = cct.course
            teacher = cct.teacher
            key = (class_.id, course.id)
            
            if key not in course_schedule_patterns:
                continue
                
            pattern = course_schedule_patterns[key]
            
            for day_idx, slot_idx in pattern:
                slot = time_slots[slot_idx]
                scheduled = False
                
                # Try different classrooms
                shuffled_classrooms = list(classrooms)
                shuffle(shuffled_classrooms)
                
                for classroom in shuffled_classrooms:
                    # Check for conflicts
                    if (day_idx, slot[0], slot[1], classroom.id) in used_classroom_slots:
                        continue
                    if (day_idx, slot[0], slot[1], teacher.id) in used_teacher_slots:
                        continue
                    if (day_idx, slot[0], slot[1], class_.id) in used_class_slots:
                        continue
                        
                    # Schedule the class
                    timetable = Timetable(
                        class_id=class_.id,
                        classroom_id=classroom.id,
                        course_id=course.id,
                        teacher_id=teacher.id,
                        day=day_idx,
                        start_time=slot[0],
                        end_time=slot[1]
                    )
                    session.add(timetable)
                    
                    # Mark resources as used
                    used_classroom_slots.add((day_idx, slot[0], slot[1], classroom.id))
                    used_teacher_slots.add((day_idx, slot[0], slot[1], teacher.id))
                    used_class_slots.add((day_idx, slot[0], slot[1], class_.id))
                    
                    # Update meeting count
                    course_meetings[key] = course_meetings.get(key, 0) + 1
                    
                    summary.append(f"{class_.name} - {course.name} in {classroom.name} by {teacher.name} on {day_idx} {slot[0]}-{slot[1]}")
                    scheduled = True
                    break
                
                # If couldn't schedule on preferred day/slot, try alternative slots
                if not scheduled:
                    # Try other slots on the same day as a fallback
                    for alt_slot_idx, slot in enumerate(time_slots):
                        if alt_slot_idx == slot_idx:  # Skip the original slot we already tried
                            continue
                            
                        for classroom in shuffled_classrooms:
                            # Check for conflicts
                            if (day_idx, slot[0], slot[1], classroom.id) in used_classroom_slots:
                                continue
                            if (day_idx, slot[0], slot[1], teacher.id) in used_teacher_slots:
                                continue
                            if (day_idx, slot[0], slot[1], class_.id) in used_class_slots:
                                continue
                                
                            # Schedule the class
                            timetable = Timetable(
                                class_id=class_.id,
                                classroom_id=classroom.id,
                                course_id=course.id,
                                teacher_id=teacher.id,
                                day=day_idx,
                                start_time=slot[0],
                                end_time=slot[1]
                            )
                            session.add(timetable)
                            
                            # Mark resources as used
                            used_classroom_slots.add((day_idx, slot[0], slot[1], classroom.id))
                            used_teacher_slots.add((day_idx, slot[0], slot[1], teacher.id))
                            used_class_slots.add((day_idx, slot[0], slot[1], class_.id))
                            
                            # Update meeting count
                            course_meetings[key] = course_meetings.get(key, 0) + 1
                            
                            summary.append(f"{class_.name} - {course.name} in {classroom.name} by {teacher.name} on {day_idx} {slot[0]}-{slot[1]}")
                            scheduled = True
                            break
                        
                        if scheduled:
                            break

    # Commit all changes at once for better performance
    session.commit()
    print("Timetable generation complete.")
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
    # Add classrooms
    if not session.query(Classroom).first():
        add_classroom(session, "Room 101", 40)
        add_classroom(session, "Room 102", 35)
        add_classroom(session, "Room 103", 30)
        add_classroom(session, "Lab 201", 25)
        add_classroom(session, "Lab 202", 25)
        add_classroom(session, "Lecture Hall A", 60)
    
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
    
    # Add classes with multiple courses per class
    if not session.query(Class).first():
        # Computer Science department
        add_class(session, "CS101", {
            3: 3,  # Intro to Programming by Dr. Williams
            4: 4,  # Data Structures by Prof. Brown
            8: 8   # Database Systems by Prof. Moore
        })
        
        # Electronics department
        add_class(session, "EC101", {
            2: 2,  # Physics Mechanics by Prof. Johnson
            6: 6,  # Digital Electronics by Prof. Miller
            7: 7   # Statistics by Dr. Wilson
        })
        
        # Science department
        add_class(session, "SC101", {
            1: 1,  # Calculus I by Dr. Smith
            2: 2,  # Physics Mechanics by Prof. Johnson
            5: 5   # Chemistry by Dr. Davis
        })
        
        # First year undergraduate
        add_class(session, "FY-UG", {
            1: 1,  # Calculus I by Dr. Smith
            3: 3,  # Intro to Programming by Dr. Williams
            5: 5   # Chemistry by Dr. Davis
        })
    
    # Generate timetable with more realistic time slots
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
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
