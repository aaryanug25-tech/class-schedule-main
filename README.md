
# Class Schedule Application

This application provides a class scheduling system with drag-and-drop timetable management, conflict detection, and a web interface for administrators and teachers.

## Features

- Interactive timetable with drag-and-drop functionality
- Automatic conflict detection for room and teacher scheduling
- Teacher-specific timetable views
- Room management and scheduling
- GitHub compatibility with relative paths

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/class-schedule.git
cd class-schedule
```

2. Install dependencies:
```bash
pip install flask sqlalchemy
```

## Running the Application

You can run the application using the included start script (recommended):

```bash
./start_server.sh
```

Or run it manually:

```bash
cd PROJECT
python webapp/app.py
```

The application will be available at http://localhost:8081

## Directory Structure

- `PROJECT/`: Main application code
  - `models.py`: Database models
  - `scheduler.py`: Timetable generation logic
  - `scheduler_update.py`: Updates for the scheduler
  - `webapp/`: Flask web application
    - `app.py`: Main Flask application
    - `templates/`: HTML templates
    - `static/`: CSS, JavaScript and other static files
      - `drag-drop-timetable.js`: Implements drag-and-drop functionality
      - `drag-drop.css`: Styling for the drag-and-drop interface


A web-based platform for automated class scheduling in higher education institutions. It allows authorized users to input classrooms, courses, teachers, and class groups, and generates an optimized, color-coded timetable. Teachers can also find available rooms for extra classes and suggest rescheduling options.


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
# Using the start script (recommended)
./start_server.sh
```

Or manually:
```sh
cd PROJECT
python3 webapp/app.py
```

Alternative with Flask CLI:
```sh
cd PROJECT
export FLASK_APP=webapp/app.py
flask run --port 8081
```

- The app uses only relative paths, so it works on any machine and is safe for GitHub repositories.

### 4. Open in your browser
Go to [http://localhost:8081](http://localhost:8081)


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
5. Use the drag-and-drop interface to rearrange classes:
   - Simply drag a class from one timeslot to another
   - Automatic conflict detection will alert if there are teacher or room conflicts
   - Conflicts are highlighted at the top of the page for easy resolution
6. Use the sidebar to access features like "Find Available Rooms", "Reschedule Class", "Cancel Class", and "Change Room".
7. Click the "View Teachers Directory" button in the sidebar to see a full list of teachers.
8. Click on any teacher's name to view their personal timetable with their assigned classes.
9. Review the dashboard analytics to get insights into teacher workloads, room usage, and course distribution.
10. Use the timetable approval system to review and finalize schedules.

## Project Structure
```
PROJECT/
├── models.py              # Extended database models
├── scheduler.py           # Core scheduling logic and database models
├── scheduler_update.py    # Updates for the scheduler
├── webapp/
│   ├── app.py             # Flask web application
│   ├── templates/
│   │   ├── admin.html            # Admin controls page
│   │   ├── cancel_class.html     # Class cancellation page
│   │   ├── change_room.html      # Room change page
│   │   ├── find_rooms.html       # Room finder page
│   │   ├── index.html            # Dashboard with analytics
│   │   ├── layout.html           # Base layout template
│   │   ├── login.html            # Login page
│   │   ├── register.html         # Registration page
│   │   ├── reschedule.html       # Class rescheduling page
│   │   ├── teacher_timetable.html # Individual teacher schedules
│   │   └── timetable.html        # Main timetable with drag-and-drop
│   └── static/
│       ├── style.css             # Main stylesheet
│       ├── chart.js              # Dashboard chart functionality
│       ├── dashboard.css         # Dashboard styling
│       ├── drag-drop.css         # Styling for drag-and-drop interface
│       ├── drag-drop-timetable.js # Drag-and-drop functionality with conflict detection
│       └── theme-styles.css      # Theme styling (light/dark modes)
├── scheduler.db           # SQLite database (auto-created)
└── README.md
```

`start_server.sh` - Script to run the application with proper working directory


## Notes
- To start fresh, delete `scheduler.db` and restart the app.
- The application uses relative paths throughout, making it compatible with GitHub repositories.
- The drag-and-drop interface requires a modern browser that supports HTML5 drag-and-drop API.
- Automatic conflict detection helps prevent scheduling errors in real-time.

## License
MIT License
