from scheduler import get_session, add_classroom, add_course, add_teacher, add_class, Course, Teacher, Class, Classroom, ClassCourseTeacher

session = get_session()

# Clear existing data
session.query(ClassCourseTeacher).delete()
session.query(Class).delete()
session.query(Teacher).delete()
session.query(Course).delete()
session.query(Classroom).delete()
session.commit()

# Add realistic classrooms
classrooms = [
    ("Room 101", 40), ("Room 102", 35), ("Room 103", 60), ("Room 104", 30),
    ("Room 201", 50), ("Room 202", 45), ("Room 203", 65), ("Room 204", 30),
    ("Room 301", 40), ("Room 302", 35), ("Room 303", 60), ("Room 304", 30),
    ("Lab 101", 25), ("Lab 102", 25), ("Lab 103", 25), ("Lab 201", 30),
    ("Lab 202", 30), ("Lab 203", 30), ("Seminar Hall 1", 100), ("Seminar Hall 2", 80)
]

for name, capacity in classrooms:
    add_classroom(session, name, capacity)

# Add realistic courses
courses = [
    # Mathematics and Physics
    "Calculus I", "Calculus II", "Linear Algebra", "Differential Equations", 
    "Probability & Statistics", "Discrete Mathematics", "Real Analysis",
    "Engineering Physics I", "Engineering Physics II", "Quantum Mechanics",
    "Classical Mechanics", "Thermodynamics", "Statistical Mechanics",
    
    # Chemistry
    "General Chemistry", "Organic Chemistry I", "Organic Chemistry II",
    "Inorganic Chemistry", "Physical Chemistry", "Analytical Chemistry",
    
    # Computer Science
    "Computer Programming", "Data Structures", "Algorithms", 
    "Database Management Systems", "Operating Systems", "Computer Networks",
    "Software Engineering", "Artificial Intelligence", "Machine Learning",
    "Web Development", "Computer Graphics",
    
    # Electrical Engineering
    "Circuit Theory", "Digital Logic Design", "Signals and Systems", 
    "Electromagnetic Theory", "Control Systems", "Power Systems",
    
    # Mechanical Engineering
    "Engineering Mechanics", "Fluid Mechanics", "Heat Transfer", 
    "Manufacturing Processes", "Machine Design",
    
    # Civil Engineering
    "Structural Analysis", "Geotechnical Engineering", "Transportation Engineering",
    "Environmental Engineering", "Surveying", "Construction Management",
    
    # Other Engineering Courses
    "Engineering Drawing", "Engineering Economics", "Technical Communication",
    "Professional Ethics"
]

for course_name in courses:
    add_course(session, course_name)

# Add realistic teachers
teachers = [
    # Mathematics Department
    ("Dr. Robert Chen", "Calculus I"),
    ("Dr. Sarah Johnson", "Calculus II"),
    ("Dr. Michael Williams", "Linear Algebra"),
    ("Prof. Emily Davis", "Differential Equations"),
    ("Dr. James Wilson", "Probability & Statistics"),
    ("Prof. Linda Brown", "Discrete Mathematics"),
    ("Dr. Thomas Garcia", "Real Analysis"),
    
    # Physics Department
    ("Dr. Jennifer Lee", "Engineering Physics I"),
    ("Prof. David Martinez", "Engineering Physics II"),
    ("Dr. Elizabeth Taylor", "Quantum Mechanics"),
    ("Prof. Richard Anderson", "Classical Mechanics"),
    ("Dr. Patricia Moore", "Thermodynamics"),
    ("Prof. Charles Wilson", "Statistical Mechanics"),
    
    # Chemistry Department
    ("Dr. Margaret White", "General Chemistry"),
    ("Prof. Daniel Rodriguez", "Organic Chemistry I"),
    ("Dr. Susan Miller", "Organic Chemistry II"),
    ("Prof. Joseph Thomas", "Inorganic Chemistry"),
    ("Dr. Nancy Jackson", "Physical Chemistry"),
    ("Prof. Steven Thompson", "Analytical Chemistry"),
    
    # Computer Science Department
    ("Prof. Karen Lewis", "Computer Programming"),
    ("Dr. Edward Martin", "Data Structures"),
    ("Prof. Dorothy Harris", "Algorithms"),
    ("Dr. John Clark", "Database Management Systems"),
    ("Prof. Lisa Young", "Operating Systems"),
    ("Dr. Kevin Walker", "Computer Networks"),
    ("Prof. Barbara Hall", "Software Engineering"),
    ("Dr. George Allen", "Artificial Intelligence"),
    ("Prof. Deborah King", "Machine Learning"),
    ("Dr. Paul Scott", "Web Development"),
    ("Prof. Betty Adams", "Computer Graphics"),
    
    # Electrical Engineering Department
    ("Dr. Jason Lee", "Circuit Theory"),
    ("Prof. Michelle Turner", "Digital Logic Design"),
    ("Dr. Brian Phillips", "Signals and Systems"),
    ("Prof. Kimberly Mitchell", "Electromagnetic Theory"),
    ("Dr. Christopher Green", "Control Systems"),
    ("Prof. Amanda Roberts", "Power Systems"),
    
    # Mechanical Engineering Department
    ("Dr. Kenneth Cook", "Engineering Mechanics"),
    ("Prof. Carol Baker", "Fluid Mechanics"),
    ("Dr. Ronald Hill", "Heat Transfer"),
    ("Prof. Sharon Wright", "Manufacturing Processes"),
    ("Dr. Laura Evans", "Machine Design"),
    
    # Civil Engineering Department
    ("Prof. Mark Carter", "Structural Analysis"),
    ("Dr. Sandra Morris", "Geotechnical Engineering"),
    ("Prof. Donald Rogers", "Transportation Engineering"),
    ("Dr. Ruth Reed", "Environmental Engineering"),
    ("Prof. Larry Murphy", "Surveying"),
    ("Dr. Emma Nelson", "Construction Management"),
    
    # Other Engineering Courses
    ("Prof. Timothy Cooper", "Engineering Drawing"),
    ("Dr. Donna Rivera", "Engineering Economics"),
    ("Prof. Gary Richardson", "Technical Communication"),
    ("Dr. Helen Nguyen", "Professional Ethics")
]

for name, subject in teachers:
    add_teacher(session, name, subject)

# Add realistic classes (academic programs)
classes = [
    # Engineering Programs
    "B.Tech Civil Engineering", 
    "B.Tech Mechanical Engineering",
    "B.Tech Electrical Engineering", 
    "B.Tech Electronics & Communication",
    "B.Tech Computer Science", 
    "B.Tech Information Technology",
    "B.Tech Aerospace Engineering", 
    "B.Tech Chemical Engineering",
    "B.Tech Biotechnology", 
    "B.Tech Industrial Engineering",
    
    # Science Programs
    "B.Sc Physics",
    "B.Sc Chemistry", 
    "B.Sc Mathematics",
    "B.Sc Computer Science",
    "B.Sc Statistics",
    
    # Graduate Programs
    "M.Tech Structural Engineering",
    "M.Tech Thermal Engineering",
    "M.Tech Power Systems",
    "M.Tech VLSI Design",
    "M.Tech Computer Science",
    "M.Tech Data Science",
    
    # Other Programs
    "B.Arch Architecture",
    "B.Des Design",
    "B.Com Commerce",
    "BBA Business Administration"
]

# Add classes with course-teacher mappings
all_courses = session.query(Course).all()
all_teachers = session.query(Teacher).all()

# Dictionary mapping courses to teachers
course_teacher_map = {}
for teacher in all_teachers:
    course = session.query(Course).filter_by(name=teacher.subject).first()
    if course:
        course_teacher_map[course.id] = teacher.id

# Add classes with appropriate course-teacher mappings
for class_name in classes:
    # Select a subset of appropriate courses for each class based on the program
    class_courses = {}
    
    if "Civil" in class_name:
        relevant_subjects = ["Calculus I", "Engineering Physics I", "Structural Analysis", 
                             "Geotechnical Engineering", "Surveying"]
    elif "Mechanical" in class_name:
        relevant_subjects = ["Calculus I", "Engineering Physics I", "Engineering Mechanics", 
                             "Fluid Mechanics", "Thermodynamics"]
    elif "Electrical" in class_name or "Electronics" in class_name:
        relevant_subjects = ["Calculus I", "Engineering Physics I", "Circuit Theory", 
                             "Digital Logic Design", "Electromagnetic Theory"]
    elif "Computer" in class_name or "Information" in class_name:
        relevant_subjects = ["Calculus I", "Discrete Mathematics", "Computer Programming", 
                             "Data Structures", "Database Management Systems"]
    elif "Physics" in class_name:
        relevant_subjects = ["Calculus I", "Engineering Physics I", "Quantum Mechanics", 
                             "Classical Mechanics", "Thermodynamics"]
    elif "Chemistry" in class_name:
        relevant_subjects = ["Calculus I", "General Chemistry", "Organic Chemistry I", 
                             "Inorganic Chemistry", "Physical Chemistry"]
    elif "Mathematics" in class_name:
        relevant_subjects = ["Calculus I", "Calculus II", "Linear Algebra", 
                             "Differential Equations", "Real Analysis"]
    else:
        # Default set of courses for other programs
        relevant_subjects = ["Calculus I", "Engineering Physics I", "Technical Communication", 
                             "Engineering Economics", "Professional Ethics"]
    
    # Create course-teacher mapping for this class
    for subject in relevant_subjects:
        course = session.query(Course).filter_by(name=subject).first()
        if course:
            teacher = session.query(Teacher).filter_by(subject=subject).first()
            if teacher:
                class_courses[course.id] = teacher.id
    
    # Add the class with its course-teacher mappings
    if class_courses:
        add_class(session, class_name, class_courses)

print("Realistic academic data inserted successfully.")
