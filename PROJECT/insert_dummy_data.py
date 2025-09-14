
from scheduler import get_session, add_classroom, add_course, add_teacher, add_class, Course, Teacher, Class

session = get_session()


# Add dummy classrooms if not exist

from scheduler import Classroom
if not session.query(Classroom).filter_by(name="Room 201").first():
    add_classroom(session, "Room 201", 50)
if not session.query(Classroom).filter_by(name="Room 202").first():
    add_classroom(session, "Room 202", 35)

# Add dummy courses if not exist
if not session.query(Course).filter_by(name="Biology").first():
    add_course(session, "Biology")
if not session.query(Course).filter_by(name="Chemistry").first():
    add_course(session, "Chemistry")

# Add dummy teachers if not exist
if not session.query(Teacher).filter_by(name="Dr. Green").first():
    add_teacher(session, "Dr. Green", "Biology")
if not session.query(Teacher).filter_by(name="Dr. Blue").first():
    add_teacher(session, "Dr. Blue", "Chemistry")

# Add dummy classes with course-teacher mapping
bio_course = session.query(Course).filter_by(name="Biology").first()
chem_course = session.query(Course).filter_by(name="Chemistry").first()
green_teacher = session.query(Teacher).filter_by(name="Dr. Green").first()
blue_teacher = session.query(Teacher).filter_by(name="Dr. Blue").first()

from scheduler import Class
if bio_course and green_teacher and not session.query(Class).filter_by(name="FYBSc").first():
    add_class(session, "FYBSc", {bio_course.id: green_teacher.id})
if chem_course and blue_teacher and not session.query(Class).filter_by(name="SYBSc").first():
    add_class(session, "SYBSc", {chem_course.id: blue_teacher.id})


# Insert 200 more dummy classrooms, courses, teachers, and classes
for i in range(1, 201):
    cname = f"Room_{300+i}"
    if not session.query(Classroom).filter_by(name=cname).first():
        add_classroom(session, cname, 20 + (i % 40))

    course_name = f"Course_{i}"
    if not session.query(Course).filter_by(name=course_name).first():
        add_course(session, course_name)

    teacher_name = f"Teacher_{i}"
    if not session.query(Teacher).filter_by(name=teacher_name).first():
        add_teacher(session, teacher_name, f"Subject_{i}")

    # Add a class for each, mapping the course to the teacher
    course = session.query(Course).filter_by(name=course_name).first()
    teacher = session.query(Teacher).filter_by(name=teacher_name).first()
    class_name = f"Class_{i}"
    if not session.query(Class).filter_by(name=class_name).first() and course and teacher:
        add_class(session, class_name, {course.id: teacher.id})

print("Dummy data inserted successfully.")
