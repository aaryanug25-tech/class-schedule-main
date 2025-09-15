
# Class Scheduler Web Application


A web-based platform for automated class scheduling in higher education institutions. It allows authorized users to input classrooms, courses, teachers, and class groups, and generates an optimized, color-coded timetable. Teachers can also find available rooms for extra classes and suggest rescheduling options.

**Now safe for public repositories:**
- All file/database paths are relative (no user-specific or absolute paths)
- `.gitignore` excludes the database, cache, and secrets by default
- No sensitive or personal data is included in the codebase

---

## Features
- Add and manage classrooms, courses, teachers, and class groups
- Assign one teacher per course per class group
- Generate a weekly timetable (8am–6pm, Mon–Fri) with no conflicts
- Color-coded, tabular timetable display for each class group
- Find available rooms for extra classes
- Suggest rescheduling options for classes
- Dedicated Teachers Directory page with all teacher details
- Individual teacher timetable views showing personal schedules
- Interactive dashboard with analytics charts showing:
  - Teacher class distribution
  - Room usage statistics
  - Course distribution analysis
- Timetable approval system with admin controls
- Sidebar button for quick access to the Teachers Directory
- Data stored in a local SQLite database
- **Modern GitHub-style dark UI** (deep black, purple accent, crisp layout)
- Light/Dark theme toggle support

## Tech Stack
- Python 3
- Flask (web framework)
- SQLAlchemy (ORM)
- Jinja2 (templating)
- HTML/CSS (GitHub-inspired dark theme)
- Chart.js (for analytics dashboard)
- JavaScript (for interactive features)
- Font Awesome (for icons)

## Getting Started

### 1. Clone the repository
```sh
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
```

### 2. Install dependencies
```sh
python3 -m pip install flask sqlalchemy markupsafe
```

### 3. Run the application
```sh
cd PROJECT/webapp
python3 app.py
```

Or, if you prefer Flask CLI:
```sh
cd PROJECT/webapp
export FLASK_APP=app.py
flask run --port 8080
```

- The app uses only relative paths, so it works on any machine and is safe for public repos.

### 4. Open in your browser
Go to [http://localhost:5001](http://localhost:5001)


## Data Import Format (CSV)

You can add data in bulk using CSV files. Here are the required formats for each type:

### Classroom CSV
```
name,capacity
Room 101,30
Room 102,40
```

### Teacher CSV
```
name,subject
Jane Doe,Mathematics
John Smith,Physics
```

### Course CSV
```
name
Calculus I
Physics II
```

### Class Group CSV
```
name
CSE-A
ECE-B
```

---

## Usage
1. Add classrooms, courses, teachers, and class groups using the forms or by uploading CSVs (see above for format).
2. Assign each course in a class group to a teacher.
3. Click "Generate Timetable" to create the schedule.
4. View, print, or share the color-coded timetable.
5. Use the sidebar to access features like "Find Available Rooms", "Reschedule Class", "Cancel Class", and "Change Room".
6. Click the "View Teachers Directory" button in the sidebar to see a full list of teachers.
7. Click on any teacher's name to view their personal timetable with their assigned classes.
8. Review the dashboard analytics to get insights into teacher workloads, room usage, and course distribution.
9. Use the timetable approval system to review and finalize schedules.

## Project Structure
```
PROJECT/
├── models.py              # Extended database models
├── scheduler.py           # Core scheduling logic and database models
├── webapp/
│   ├── app.py             # Flask web application
│   ├── templates/
│   │   ├── teachers.html         # Teachers Directory page
│   │   ├── teacher_timetable.html # Individual teacher schedules
│   │   ├── index.html           # Dashboard with analytics
│   │   └── ...                  # Other HTML templates (GitHub dark theme)
│   └── static/
│       ├── style.css            # Main stylesheet
│       ├── chart.js             # Dashboard chart functionality
│       ├── dashboard.css        # Dashboard styling
│       └── ...                  # Other static files (GitHub dark theme)
├── scheduler.db           # SQLite database (auto-created)
└── README.md
```


## Notes
- All data is stored locally in `scheduler.db` (which is ignored by git).
- To start fresh, delete `scheduler.db` and restart the app.
- **Privacy:** No personal or sensitive data is included. Do not commit real user data or secrets.

## License
MIT License
