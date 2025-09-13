import datetime
from werkzeug.security import generate_password_hash, check_password_hash
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
def get_session(db_url='sqlite:///scheduler.db'):
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


# Improved timetable generation function
def generate_timetable(session, days, time_slots):
    """
    Automatically generate a timetable for all classes, courses, and teachers.
    Each class has only one teacher per course (enforced by ClassCourseTeacher).
    Avoids conflicts and maximizes classroom/teacher utilization.
    Returns a summary of the generated timetable.
    """
    session.query(Timetable).delete()  # Clear previous schedule
    session.commit()
    classes = session.query(Class).all()
    classrooms = session.query(Classroom).all()
    summary = []

    # Track usage to avoid conflicts
    used = set()  # (day, slot, classroom_id), (day, slot, teacher_id)

    for class_ in classes:
        for cct in class_.course_teachers:
            course = cct.course
            teacher = cct.teacher
            scheduled = False
            for day in days:
                for slot in time_slots:
                    for classroom in classrooms:
                        if (day, slot[0], slot[1], classroom.id) in used:
                            continue
                        if (day, slot[0], slot[1], teacher.id) in used:
                            continue
                        # Schedule
                        timetable = Timetable(
                            class_id=class_.id,
                            classroom_id=classroom.id,
                            course_id=course.id,
                            teacher_id=teacher.id,
                            day=day,
                            start_time=slot[0],
                            end_time=slot[1]
                        )
                        session.add(timetable)
                        session.commit()
                        used.add((day, slot[0], slot[1], classroom.id))
                        used.add((day, slot[0], slot[1], teacher.id))
                        summary.append(f"{class_.name} - {course.name} in {classroom.name} by {teacher.name} on {day} {slot[0]}-{slot[1]}")
                        scheduled = True
                        break
                    if scheduled:
                        break
                if scheduled:
                    break
            if not scheduled:
                summary.append(f"Could not schedule {class_.name} - {course.name}")
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

if __name__ == "__main__":
    session = get_session()
    # Example usage
    # Add classrooms
    if not session.query(Classroom).first():
        add_classroom(session, "Room 101", 40)
        add_classroom(session, "Room 102", 30)
    # Add courses
    if not session.query(Course).first():
        add_course(session, "Mathematics")
        add_course(session, "Physics")
    # Add teachers
    if not session.query(Teacher).first():
        add_teacher(session, "Alice", "Mathematics")
        add_teacher(session, "Bob", "Physics")
    # Add classes with one teacher per course
    if not session.query(Class).first():
        # Map: {course_id: teacher_id}
        add_class(session, "FYBSc", {1: 1})  # Mathematics by Alice
        add_class(session, "SYBSc", {2: 2})  # Physics by Bob
    # Generate timetable
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    time_slots = [("09:00", "10:00"), ("10:00", "11:00"), ("11:00", "12:00")]
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
