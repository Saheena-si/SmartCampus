"""
SmartCampus Database Management Module
Handles SQLite schema definition, data persistence, and demonstration seed data.
"""

import sqlite3
import os
import json
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'smartcampus.db')

def get_db_connection():
    """Returns a SQLite connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Initializes tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS classrooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT UNIQUE NOT NULL,
        building TEXT NOT NULL,
        floor INTEGER NOT NULL,
        capacity INTEGER NOT NULL,
        room_type TEXT NOT NULL DEFAULT 'Classroom',
        facilities TEXT NOT NULL, -- Stored as comma-separated tags
        notes TEXT DEFAULT '',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'student', -- 'student', 'staff', 'cr', 'admin'
        assigned_class TEXT,                  -- e.g. 'III Year CSE A', 'III Year CSE B'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS scheduled_classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        classroom_id INTEGER NOT NULL,
        class_group TEXT NOT NULL DEFAULT 'General', -- e.g. 'III Year CSE A', 'III Year CSE B'
        course_code TEXT NOT NULL,
        course_name TEXT NOT NULL,
        instructor TEXT NOT NULL,
        day_of_week TEXT NOT NULL, -- 'Monday', 'Tuesday', etc.
        start_time TEXT NOT NULL,  -- 'HH:MM' 24-hr format
        end_time TEXT NOT NULL,    -- 'HH:MM' 24-hr format
        session_name TEXT,         -- 'Session I', 'Session II', etc.
        semester TEXT NOT NULL DEFAULT 'Fall 2026',
        FOREIGN KEY (classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_code TEXT UNIQUE NOT NULL,
        classroom_id INTEGER NOT NULL,
        user_id INTEGER,
        user_name TEXT NOT NULL,
        user_email TEXT NOT NULL,
        user_role TEXT NOT NULL DEFAULT 'Student', -- 'Student', 'Faculty', 'Staff', 'CR'
        purpose TEXT NOT NULL,
        booking_date TEXT NOT NULL, -- 'YYYY-MM-DD'
        start_time TEXT NOT NULL,   -- 'HH:MM'
        end_time TEXT NOT NULL,     -- 'HH:MM'
        attendees INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending', -- 'Pending', 'Approved', 'Rejected'
        admin_notes TEXT,
        rejection_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS maintenance_blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        classroom_id INTEGER NOT NULL,
        start_date TEXT NOT NULL, -- 'YYYY-MM-DD'
        start_time TEXT NOT NULL, -- 'HH:MM'
        end_date TEXT NOT NULL,   -- 'YYYY-MM-DD'
        end_time TEXT NOT NULL,   -- 'HH:MM'
        reason TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS manual_availability_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        classroom_id INTEGER NOT NULL,
        update_date TEXT NOT NULL, -- 'YYYY-MM-DD'
        start_time TEXT NOT NULL,  -- 'HH:MM'
        end_time TEXT NOT NULL,    -- 'HH:MM'
        status_type TEXT NOT NULL DEFAULT 'Occupied — Manual Update',
        reason TEXT NOT NULL,
        updated_by_user_id INTEGER,
        user_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE,
        FOREIGN KEY (updated_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS class_cancellations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scheduled_class_id INTEGER NOT NULL,
        cancellation_date TEXT NOT NULL, -- 'YYYY-MM-DD'
        reason TEXT NOT NULL,
        cancelled_by_user_id INTEGER,
        user_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (scheduled_class_id) REFERENCES scheduled_classes(id) ON DELETE CASCADE,
        FOREIGN KEY (cancelled_by_user_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        user_name TEXT,
        action TEXT NOT NULL,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()

    # Safe column migrations for existing SQLite databases
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(classrooms)")
    cols = {row['name'] for row in cursor.fetchall()}
    if 'notes' not in cols:
        cursor.execute("ALTER TABLE classrooms ADD COLUMN notes TEXT DEFAULT ''")

    cursor.execute("PRAGMA table_info(scheduled_classes)")
    sc_cols = {row['name'] for row in cursor.fetchall()}
    if 'class_group' not in sc_cols:
        cursor.execute("ALTER TABLE scheduled_classes ADD COLUMN class_group TEXT NOT NULL DEFAULT 'General'")
    if 'session_name' not in sc_cols:
        cursor.execute("ALTER TABLE scheduled_classes ADD COLUMN session_name TEXT")

    cursor.execute("PRAGMA table_info(bookings)")
    bk_cols = {row['name'] for row in cursor.fetchall()}
    if 'user_id' not in bk_cols:
        cursor.execute("ALTER TABLE bookings ADD COLUMN user_id INTEGER")
    if 'rejection_reason' not in bk_cols:
        cursor.execute("ALTER TABLE bookings ADD COLUMN rejection_reason TEXT")

    conn.commit()
    conn.close()

def seed_demo_data(force=False):
    """
    Seeds demonstration data safely without creating duplicates.
    Seeds classrooms, users, timetables with official sessions, bookings, and maintenance.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM classrooms")
    count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]

    if count > 0 and user_count > 0 and not force:
        conn.close()
        return False

    # Clear existing if force
    if force:
        cursor.execute("DELETE FROM audit_logs")
        cursor.execute("DELETE FROM class_cancellations")
        cursor.execute("DELETE FROM manual_availability_updates")
        cursor.execute("DELETE FROM maintenance_blocks")
        cursor.execute("DELETE FROM bookings")
        cursor.execute("DELETE FROM scheduled_classes")
        cursor.execute("DELETE FROM users")
        cursor.execute("DELETE FROM classrooms")

    # ========================================================
    # 1. DEMO USERS (Four Distinct Roles + Passwords)
    # ========================================================
    demo_users = [
        (
            "student1",
            generate_password_hash("Password@123"),
            "Aarav Sharma",
            "student1@campus.edu",
            "student",
            None
        ),
        (
            "staff1",
            generate_password_hash("Password@123"),
            "Prof. Rajesh Raman",
            "staff1@campus.edu",
            "staff",
            None
        ),
        (
            "cr_csea",
            generate_password_hash("Password@123"),
            "Pooja Verma",
            "cr_csea@campus.edu",
            "cr",
            "III Year CSE A"
        ),
        (
            "cr_cseb",
            generate_password_hash("Password@123"),
            "Karthik Raja",
            "cr_cseb@campus.edu",
            "cr",
            "III Year CSE B"
        ),
        (
            "admin",
            generate_password_hash("AdminPassword@123"),
            "Campus Facility Admin",
            "admin@campus.edu",
            "admin",
            None
        )
    ]

    cursor.executemany("""
    INSERT INTO users (username, password_hash, full_name, email, role, assigned_class)
    VALUES (?, ?, ?, ?, ?, ?)
    """, demo_users)

    # Fetch user IDs
    user_map = {}
    for r in cursor.execute("SELECT username, id, full_name FROM users").fetchall():
        user_map[r['username']] = r['id']

    # ========================================================
    # 2. DEMO CLASSROOMS & LABS (8 rooms across multiple buildings)
    # ========================================================
    # Explicitly including: D309 (III CSE A), D310 (III CSE B), CC1, CC2, CC3, plus 3 demo rooms
    demo_classrooms = [
        (
            "D309",
            "Department Block D",
            3,
            65,
            "Classroom",
            "Projector,Audio System,Air Conditioning,Smart Board,Whiteboard",
            "Official Classroom for III Year CSE A"
        ),
        (
            "D310",
            "Department Block D",
            3,
            65,
            "Classroom",
            "Projector,Audio System,Air Conditioning,Smart Board,Whiteboard",
            "Official Classroom for III Year CSE B"
        ),
        (
            "CC1",
            "Computing Center",
            1,
            40,
            "Computer Lab",
            "Lab Computers,High-Speed LAN,Projector,Air Conditioning,Whiteboard",
            "Demonstration Data: Central Computer Lab 1 (Invented capacity/schedule)"
        ),
        (
            "CC2",
            "Computing Center",
            2,
            40,
            "Computer Lab",
            "Lab Computers,High-Speed LAN,Projector,Air Conditioning,Whiteboard",
            "Demonstration Data: Central Computer Lab 2 (Invented capacity/schedule)"
        ),
        (
            "CC3",
            "Computing Center",
            3,
            40,
            "Computer Lab",
            "Lab Computers,High-Speed LAN,Projector,Air Conditioning,Whiteboard",
            "Demonstration Data: Central Computer Lab 3 (Invented capacity/schedule)"
        ),
        (
            "ENG-101",
            "Engineering Hall",
            1,
            120,
            "Auditorium",
            "Projector,Audio System,Air Conditioning,Wheelchair Accessible,Microphone,Dual Displays",
            "Demonstration Data: Major Engineering Lecture Hall"
        ),
        (
            "SCI-202",
            "Science Complex",
            2,
            35,
            "Science Lab",
            "Lab Benches,Smart Board,Projector,Air Conditioning,Safety Shower",
            "Demonstration Data: Science Demonstration Laboratory"
        ),
        (
            "TECH-101",
            "Tech Tower",
            1,
            200,
            "Main Auditorium",
            "Projector,Audio System,Air Conditioning,Tiered Seating,Microphone,Stage Lighting",
            "Demonstration Data: Campus Central Auditorium"
        )
    ]

    cursor.executemany("""
    INSERT INTO classrooms (room_number, building, floor, capacity, room_type, facilities, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, demo_classrooms)

    room_map = {}
    for r in cursor.execute("SELECT room_number, id FROM classrooms").fetchall():
        room_map[r['room_number']] = r['id']

    # ========================================================
    # 3. TIMETABLES WITH OFFICIAL SESSION TIMINGS
    # Sessions:
    # Session I:   09:00 - 09:55
    # Session II:  09:55 - 10:50
    # Break:       10:50 - 11:10
    # Session III: 11:10 - 12:00
    # Session IV:  12:00 - 12:50
    # Lunch:       12:50 - 13:40
    # Session V:   01:40 - 02:30 (13:40 - 14:30)
    # Session VI:  02:30 - 03:20 (14:30 - 15:20)
    # Session VII: 03:20 - 04:10 (15:20 - 16:10)
    # ========================================================
    classes_data = [
        # --- MONDAY ---
        # D309 (III Year CSE A)
        (room_map["D309"], "III Year CSE A", "CS3501", "Compiler Design", "Dr. K. Sharma", "Monday", "09:00", "09:55", "Session I"),
        (room_map["D309"], "III Year CSE A", "CS3591", "Computer Networks", "Dr. M. Sundar", "Monday", "09:55", "10:50", "Session II"),
        (room_map["D309"], "III Year CSE A", "CS3551", "Distributed Systems", "Dr. S. Ananth", "Monday", "11:10", "12:00", "Session III"),
        (room_map["D309"], "III Year CSE A", "CS3502", "OOAD", "Dr. N. Gayathri", "Monday", "12:00", "12:50", "Session IV"),
        (room_map["D309"], "III Year CSE A", "CS3511", "Web Technologies", "Prof. A. Joseph", "Monday", "13:40", "14:30", "Session V"),
        (room_map["D309"], "III Year CSE A", "CS3561", "Open Elective", "Prof. V. Priya", "Monday", "14:30", "15:20", "Session VI"),
        (room_map["D309"], "III Year CSE A", "LIB-301", "Library / Mentorship", "Faculty Proctor", "Monday", "15:20", "16:10", "Session VII"),

        # D310 (III Year CSE B)
        (room_map["D310"], "III Year CSE B", "CS3591", "Computer Networks", "Dr. M. Sundar", "Monday", "09:00", "09:55", "Session I"),
        (room_map["D310"], "III Year CSE B", "CS3501", "Compiler Design", "Dr. K. Sharma", "Monday", "09:55", "10:50", "Session II"),
        (room_map["D310"], "III Year CSE B", "CS3502", "OOAD", "Dr. N. Gayathri", "Monday", "11:10", "12:00", "Session III"),
        (room_map["D310"], "III Year CSE B", "CS3551", "Distributed Systems", "Dr. S. Ananth", "Monday", "12:00", "12:50", "Session IV"),
        (room_map["D310"], "III Year CSE B", "CS3561", "Open Elective", "Prof. V. Priya", "Monday", "13:40", "14:30", "Session V"),
        (room_map["D310"], "III Year CSE B", "CS3511", "Web Technologies", "Prof. A. Joseph", "Monday", "14:30", "15:20", "Session VI"),
        (room_map["D310"], "III Year CSE B", "SEM-302", "Technical Seminar", "Faculty Proctor", "Monday", "15:20", "16:10", "Session VII"),

        # --- TUESDAY ---
        # D309 (III Year CSE A)
        (room_map["D309"], "III Year CSE A", "CS3551", "Distributed Systems", "Dr. S. Ananth", "Tuesday", "09:00", "09:55", "Session I"),
        (room_map["D309"], "III Year CSE A", "CS3501", "Compiler Design", "Dr. K. Sharma", "Tuesday", "09:55", "10:50", "Session II"),
        (room_map["D309"], "III Year CSE A", "CS3502", "OOAD", "Dr. N. Gayathri", "Tuesday", "11:10", "12:00", "Session III"),
        (room_map["D309"], "III Year CSE A", "CS3591", "Computer Networks", "Dr. M. Sundar", "Tuesday", "12:00", "12:50", "Session IV"),

        # CC1 Demo Lab for III CSE A Tuesday afternoon
        (room_map["CC1"], "III Year CSE A", "CS3581", "Networks Lab (Demo)", "Dr. M. Sundar / Prof. T. Karthik", "Tuesday", "13:40", "16:10", "Session V-VII"),

        # D310 (III Year CSE B)
        (room_map["D310"], "III Year CSE B", "CS3511", "Web Technologies", "Prof. A. Joseph", "Tuesday", "09:00", "09:55", "Session I"),
        (room_map["D310"], "III Year CSE B", "CS3591", "Computer Networks", "Dr. M. Sundar", "Tuesday", "09:55", "10:50", "Session II"),
        (room_map["D310"], "III Year CSE B", "CS3501", "Compiler Design", "Dr. K. Sharma", "Tuesday", "11:10", "12:00", "Session III"),
        (room_map["D310"], "III Year CSE B", "CS3551", "Distributed Systems", "Dr. S. Ananth", "Tuesday", "12:00", "12:50", "Session IV"),
        (room_map["D310"], "III Year CSE B", "CS3561", "Open Elective", "Prof. V. Priya", "Tuesday", "13:40", "14:30", "Session V"),
        (room_map["D310"], "III Year CSE B", "APT-301", "Placement & Aptitude", "Trainer Lead", "Tuesday", "14:30", "16:10", "Session VI-VII"),

        # --- WEDNESDAY ---
        # D309 (III Year CSE A)
        (room_map["D309"], "III Year CSE A", "CS3511", "Web Technologies", "Prof. A. Joseph", "Wednesday", "09:00", "09:55", "Session I"),
        (room_map["D309"], "III Year CSE A", "CS3502", "OOAD", "Dr. N. Gayathri", "Wednesday", "09:55", "10:50", "Session II"),
        (room_map["D309"], "III Year CSE A", "CS3501", "Compiler Design", "Dr. K. Sharma", "Wednesday", "11:10", "12:00", "Session III"),
        (room_map["D309"], "III Year CSE A", "CS3551", "Distributed Systems", "Dr. S. Ananth", "Wednesday", "12:00", "12:50", "Session IV"),
        (room_map["D309"], "III Year CSE A", "CS3561", "Open Elective", "Prof. V. Priya", "Wednesday", "13:40", "14:30", "Session V"),
        (room_map["D309"], "III Year CSE A", "SEM-301", "Technical Seminar", "Faculty Proctor", "Wednesday", "14:30", "16:10", "Session VI-VII"),

        # D310 (III Year CSE B)
        (room_map["D310"], "III Year CSE B", "CS3551", "Distributed Systems", "Dr. S. Ananth", "Wednesday", "09:00", "09:55", "Session I"),
        (room_map["D310"], "III Year CSE B", "CS3501", "Compiler Design", "Dr. K. Sharma", "Wednesday", "09:55", "10:50", "Session II"),
        (room_map["D310"], "III Year CSE B", "CS3591", "Computer Networks", "Dr. M. Sundar", "Wednesday", "11:10", "12:00", "Session III"),
        (room_map["D310"], "III Year CSE B", "CS3502", "OOAD", "Dr. N. Gayathri", "Wednesday", "12:00", "12:50", "Session IV"),

        # CC2 Demo Lab for III CSE B Wednesday afternoon
        (room_map["CC2"], "III Year CSE B", "CS3582", "Web Tech Lab (Demo)", "Prof. A. Joseph", "Wednesday", "13:40", "16:10", "Session V-VII"),

        # --- THURSDAY ---
        # D309 (III Year CSE A)
        (room_map["D309"], "III Year CSE A", "CS3591", "Computer Networks", "Dr. M. Sundar", "Thursday", "09:00", "09:55", "Session I"),
        (room_map["D309"], "III Year CSE A", "CS3551", "Distributed Systems", "Dr. S. Ananth", "Thursday", "09:55", "10:50", "Session II"),
        (room_map["D309"], "III Year CSE A", "CS3561", "Open Elective", "Prof. V. Priya", "Thursday", "11:10", "12:00", "Session III"),
        (room_map["D309"], "III Year CSE A", "CS3501", "Compiler Design", "Dr. K. Sharma", "Thursday", "12:00", "12:50", "Session IV"),

        # CC2 Demo Lab for III CSE A Thursday afternoon
        (room_map["CC2"], "III Year CSE A", "CS3582", "Web Tech Lab (Demo)", "Prof. A. Joseph", "Thursday", "13:40", "16:10", "Session V-VII"),

        # D310 (III Year CSE B)
        (room_map["D310"], "III Year CSE B", "CS3502", "OOAD", "Dr. N. Gayathri", "Thursday", "09:00", "09:55", "Session I"),
        (room_map["D310"], "III Year CSE B", "CS3511", "Web Technologies", "Prof. A. Joseph", "Thursday", "09:55", "10:50", "Session II"),
        (room_map["D310"], "III Year CSE B", "CS3501", "Compiler Design", "Dr. K. Sharma", "Thursday", "11:10", "12:00", "Session III"),
        (room_map["D310"], "III Year CSE B", "CS3561", "Open Elective", "Prof. V. Priya", "Thursday", "12:00", "12:50", "Session IV"),

        # CC3 Demo Lab for III CSE B Thursday afternoon
        (room_map["CC3"], "III Year CSE B", "CS3581", "Networks Lab (Demo)", "Dr. M. Sundar", "Thursday", "13:40", "16:10", "Session V-VII"),

        # --- FRIDAY ---
        # D309 (III Year CSE A)
        (room_map["D309"], "III Year CSE A", "CS3502", "OOAD", "Dr. N. Gayathri", "Friday", "09:00", "09:55", "Session I"),
        (room_map["D309"], "III Year CSE A", "CS3511", "Web Technologies", "Prof. A. Joseph", "Friday", "09:55", "10:50", "Session II"),
        (room_map["D309"], "III Year CSE A", "CS3501", "Compiler Design", "Dr. K. Sharma", "Friday", "11:10", "12:00", "Session III"),
        (room_map["D309"], "III Year CSE A", "CS3591", "Computer Networks", "Dr. M. Sundar", "Friday", "12:00", "12:50", "Session IV"),
        (room_map["D309"], "III Year CSE A", "PRJ-301", "Mini Project / Mentorship", "Dr. K. Sharma", "Friday", "13:40", "16:10", "Session V-VII"),

        # D310 (III Year CSE B)
        (room_map["D310"], "III Year CSE B", "CS3591", "Computer Networks", "Dr. M. Sundar", "Friday", "09:00", "09:55", "Session I"),
        (room_map["D310"], "III Year CSE B", "CS3551", "Distributed Systems", "Dr. S. Ananth", "Friday", "09:55", "10:50", "Session II"),
        (room_map["D310"], "III Year CSE B", "CS3511", "Web Technologies", "Prof. A. Joseph", "Friday", "11:10", "12:00", "Session III"),
        (room_map["D310"], "III Year CSE B", "CS3502", "OOAD", "Dr. N. Gayathri", "Friday", "12:00", "12:50", "Session IV"),
        (room_map["D310"], "III Year CSE B", "PRJ-302", "Mini Project / Mentorship", "Dr. M. Sundar", "Friday", "13:40", "16:10", "Session V-VII"),

        # Additional Demo Classes in other buildings
        (room_map["ENG-101"], "Demo Engineering", "ENG-101", "Intro to Engineering Systems", "Dr. Alan Turing", "Monday", "09:00", "11:00", "Morning Lecture"),
        (room_map["ENG-101"], "Demo Engineering", "CS-204", "Data Structures & Algorithms", "Dr. Donald Knuth", "Tuesday", "10:00", "12:00", "Morning Lecture"),
        (room_map["TECH-101"], "Demo Tech", "TECH-100", "Dean's Innovation Series", "Dean Hamilton", "Wednesday", "14:00", "16:00", "Afternoon Colloquium"),
        (room_map["SCI-202"], "Demo Science", "SCI-201", "Experimental Physics Lab", "Dr. Rosalind Franklin", "Thursday", "09:30", "12:00", "Morning Lab")
    ]

    cursor.executemany("""
    INSERT INTO scheduled_classes (
        classroom_id, class_group, course_code, course_name, instructor, day_of_week, start_time, end_time, session_name
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, classes_data)

    # ========================================================
    # 4. DEMO BOOKINGS
    # ========================================================
    today_str = date.today().strftime('%Y-%m-%d')
    demo_bookings = [
        (
            "BK-202610-1001",
            room_map["TECH-101"],
            user_map.get("staff1"),
            "Prof. Rajesh Raman",
            "staff1@campus.edu",
            "Staff",
            "Annual Department Research Symposium",
            today_str,
            "17:00",
            "19:30",
            120,
            "Approved",
            "Approved by Academic Dean Office.",
            None
        ),
        (
            "BK-202610-1002",
            room_map["D309"],
            user_map.get("cr_csea"),
            "Pooja Verma",
            "cr_csea@campus.edu",
            "CR",
            "CSE-A Class Committee Meeting",
            today_str,
            "16:30",
            "17:30",
            30,
            "Approved",
            "Approved for official CR review session.",
            None
        ),
        (
            "BK-202610-1003",
            room_map["CC1"],
            user_map.get("student1"),
            "Aarav Sharma",
            "student1@campus.edu",
            "Student",
            "Competitive Coding Group Practice",
            today_str,
            "17:00",
            "18:30",
            20,
            "Pending",
            None,
            None
        ),
        (
            "BK-202610-1004",
            room_map["SCI-202"],
            user_map.get("student1"),
            "Aarav Sharma",
            "student1@campus.edu",
            "Student",
            "Informal Gaming Tournament",
            today_str,
            "18:00",
            "20:00",
            25,
            "Rejected",
            "Rejected: Room is reserved exclusively for academic and recognized campus events.",
            "Rejected: Room is reserved exclusively for academic and recognized campus events."
        )
    ]

    cursor.executemany("""
    INSERT INTO bookings (
        booking_code, classroom_id, user_id, user_name, user_email, user_role,
        purpose, booking_date, start_time, end_time, attendees, status, admin_notes, rejection_reason
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, demo_bookings)

    # ========================================================
    # 5. DEMO MAINTENANCE BLOCKS
    # ========================================================
    demo_maintenance = [
        (
            room_map["CC3"],
            today_str,
            "08:00",
            today_str,
            "12:00",
            "Network switch replacement and server rack maintenance"
        ),
        (
            room_map["SCI-202"],
            today_str,
            "14:00",
            today_str,
            "17:00",
            "Safety fume hood calibration and electrical inspection"
        )
    ]

    cursor.executemany("""
    INSERT INTO maintenance_blocks (classroom_id, start_date, start_time, end_date, end_time, reason)
    VALUES (?, ?, ?, ?, ?, ?)
    """, demo_maintenance)

    # ========================================================
    # 6. DEMO AUDIT LOGS
    # ========================================================
    demo_audits = [
        (user_map.get("admin"), "Campus Facility Admin", "SYSTEM_SEED", "Seeded demonstration database with 8 classrooms, CSE timetables, and demo users."),
        (user_map.get("staff1"), "Prof. Rajesh Raman", "BOOKING_APPROVED", "Approved booking BK-202610-1001 for Tech Tower Auditorium.")
    ]

    cursor.executemany("""
    INSERT INTO audit_logs (user_id, user_name, action, details)
    VALUES (?, ?, ?, ?)
    """, demo_audits)

    conn.commit()
    conn.close()
    return True

# ============================================================
# HELPER QUERY METHODS
# ============================================================

def row_to_dict(row):
    """Convert an sqlite3.Row object to a standard python dict."""
    if row is None:
        return None
    d = dict(row)
    if 'facilities' in d and isinstance(d['facilities'], str):
        d['facilities_list'] = [f.strip() for f in d['facilities'].split(',') if f.strip()]
    return d

# --- USER MANAGEMENT ---

def get_user_by_id(user_id):
    """Fetch user by ID."""
    conn = get_db_connection()
    row = conn.execute("SELECT id, username, full_name, email, role, assigned_class, created_at FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row_to_dict(row)

def get_user_by_username(username):
    """Fetch user by username."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username.strip(),)).fetchone()
    conn.close()
    return row_to_dict(row)

def verify_user_credentials(username, password):
    """Verify username and password against database hashes."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE LOWER(username) = LOWER(?)", (username.strip(),)).fetchone()
    conn.close()
    if not row:
        return None
    if check_password_hash(row['password_hash'], password):
        return {
            "id": row['id'],
            "username": row['username'],
            "full_name": row['full_name'],
            "email": row['email'],
            "role": row['role'],
            "assigned_class": row['assigned_class']
        }
    return None

def get_all_users():
    """Retrieve all users."""
    conn = get_db_connection()
    rows = conn.execute("SELECT id, username, full_name, email, role, assigned_class, created_at FROM users ORDER BY role, username").fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def update_user_role(user_id, role, assigned_class=None):
    """Update user role and class assignment."""
    conn = get_db_connection()
    conn.execute("""
    UPDATE users
    SET role = ?, assigned_class = ?
    WHERE id = ?
    """, (role, assigned_class, user_id))
    conn.commit()
    conn.close()

# --- CLASSROOMS ---

def get_classrooms(include_inactive=False):
    """Fetch all classrooms."""
    conn = get_db_connection()
    if include_inactive:
        rows = conn.execute("SELECT * FROM classrooms ORDER BY building, room_number").fetchall()
    else:
        rows = conn.execute("SELECT * FROM classrooms WHERE is_active = 1 ORDER BY building, room_number").fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def get_classroom_by_id(room_id):
    """Fetch a single classroom by ID."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM classrooms WHERE id = ?", (room_id,)).fetchone()
    conn.close()
    return row_to_dict(row)

def get_classroom_by_number(room_number):
    """Fetch a classroom by room number."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM classrooms WHERE UPPER(room_number) = UPPER(?)", (room_number.strip(),)).fetchone()
    conn.close()
    return row_to_dict(row)

def add_classroom(room_number, building, floor, capacity, room_type, facilities, notes=""):
    """Add a new classroom."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO classrooms (room_number, building, floor, capacity, room_type, facilities, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (room_number.strip().upper(), building.strip(), floor, capacity, room_type.strip(), facilities.strip(), notes.strip()))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def update_classroom(room_id, room_number, building, floor, capacity, room_type, facilities, notes="", is_active=1):
    """Update an existing classroom."""
    conn = get_db_connection()
    conn.execute("""
    UPDATE classrooms
    SET room_number = ?, building = ?, floor = ?, capacity = ?, room_type = ?, facilities = ?, notes = ?, is_active = ?
    WHERE id = ?
    """, (room_number.strip().upper(), building.strip(), floor, capacity, room_type.strip(), facilities.strip(), notes.strip(), is_active, room_id))
    conn.commit()
    conn.close()

def delete_classroom(room_id):
    """Soft delete / deactivate a classroom."""
    conn = get_db_connection()
    conn.execute("UPDATE classrooms SET is_active = 0 WHERE id = ?", (room_id,))
    conn.commit()
    conn.close()

# --- SCHEDULED CLASSES ---

def get_scheduled_classes(classroom_id=None, day_of_week=None, class_group=None):
    """Retrieve scheduled classes with optional filters."""
    conn = get_db_connection()
    query = """
    SELECT s.*, c.room_number, c.building
    FROM scheduled_classes s
    JOIN classrooms c ON s.classroom_id = c.id
    WHERE 1=1
    """
    params = []
    if classroom_id:
        query += " AND s.classroom_id = ?"
        params.append(classroom_id)
    if day_of_week:
        query += " AND LOWER(s.day_of_week) = LOWER(?)"
        params.append(day_of_week)
    if class_group:
        query += " AND LOWER(s.class_group) = LOWER(?)"
        params.append(class_group)
    query += " ORDER BY s.start_time"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def get_scheduled_class_by_id(class_id):
    """Fetch single scheduled class by ID."""
    conn = get_db_connection()
    row = conn.execute("""
    SELECT s.*, c.room_number, c.building
    FROM scheduled_classes s
    JOIN classrooms c ON s.classroom_id = c.id
    WHERE s.id = ?
    """, (class_id,)).fetchone()
    conn.close()
    return row_to_dict(row)

def add_scheduled_class(classroom_id, class_group, course_code, course_name, instructor, day_of_week, start_time, end_time, session_name=None):
    """Admin function to add a scheduled class entry."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO scheduled_classes (
        classroom_id, class_group, course_code, course_name, instructor, day_of_week, start_time, end_time, session_name
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (classroom_id, class_group.strip(), course_code.strip().upper(), course_name.strip(), instructor.strip(),
          day_of_week.strip(), start_time.strip(), end_time.strip(), session_name))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id

def delete_scheduled_class(class_id):
    """Admin function to remove a scheduled class entry."""
    conn = get_db_connection()
    conn.execute("DELETE FROM scheduled_classes WHERE id = ?", (class_id,))
    conn.commit()
    conn.close()

# --- CLASS CANCELLATIONS (Specific session cancellations) ---

def add_class_cancellation(scheduled_class_id, cancellation_date, reason, user_id, user_name):
    """Record a single-session cancellation."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO class_cancellations (scheduled_class_id, cancellation_date, reason, cancelled_by_user_id, user_name)
    VALUES (?, ?, ?, ?, ?)
    """, (scheduled_class_id, cancellation_date.strip(), reason.strip(), user_id, user_name))
    cid = cursor.lastrowid
    conn.commit()
    conn.close()
    return cid

def get_class_cancellations(scheduled_class_id=None, query_date=None):
    """Fetch recorded cancellations."""
    conn = get_db_connection()
    query = """
    SELECT cc.*, s.course_code, s.course_name, s.day_of_week, s.start_time, s.end_time, s.class_group, c.room_number
    FROM class_cancellations cc
    JOIN scheduled_classes s ON cc.scheduled_class_id = s.id
    JOIN classrooms c ON s.classroom_id = c.id
    WHERE 1=1
    """
    params = []
    if scheduled_class_id:
        query += " AND cc.scheduled_class_id = ?"
        params.append(scheduled_class_id)
    if query_date:
        query += " AND cc.cancellation_date = ?"
        params.append(query_date)
    query += " ORDER BY cc.cancellation_date DESC, cc.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def is_class_cancelled(scheduled_class_id, query_date):
    """Checks if a specific scheduled class session is cancelled on query_date."""
    conn = get_db_connection()
    row = conn.execute("""
    SELECT id FROM class_cancellations
    WHERE scheduled_class_id = ? AND cancellation_date = ?
    """, (scheduled_class_id, query_date)).fetchone()
    conn.close()
    return row is not None

def delete_class_cancellation(cancellation_id):
    """Remove a cancellation record."""
    conn = get_db_connection()
    conn.execute("DELETE FROM class_cancellations WHERE id = ?", (cancellation_id,))
    conn.commit()
    conn.close()

# --- MANUAL AVAILABILITY UPDATES (Staff) ---

def add_manual_update(classroom_id, update_date, start_time, end_time, status_type, reason, user_id, user_name):
    """Staff records a confirmed occupancy or manual reservation slot."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO manual_availability_updates (
        classroom_id, update_date, start_time, end_time, status_type, reason, updated_by_user_id, user_name
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (classroom_id, update_date.strip(), start_time.strip(), end_time.strip(), status_type.strip(), reason.strip(), user_id, user_name))
    uid = cursor.lastrowid
    conn.commit()
    conn.close()
    return uid

def get_manual_updates(classroom_id=None, query_date=None):
    """Retrieve manual availability updates."""
    conn = get_db_connection()
    query = """
    SELECT m.*, c.room_number, c.building
    FROM manual_availability_updates m
    JOIN classrooms c ON m.classroom_id = c.id
    WHERE 1=1
    """
    params = []
    if classroom_id:
        query += " AND m.classroom_id = ?"
        params.append(classroom_id)
    if query_date:
        query += " AND m.update_date = ?"
        params.append(query_date)
    query += " ORDER BY m.update_date DESC, m.start_time DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def delete_manual_update(update_id):
    """Remove a manual update."""
    conn = get_db_connection()
    conn.execute("DELETE FROM manual_availability_updates WHERE id = ?", (update_id,))
    conn.commit()
    conn.close()

# --- BOOKINGS ---

def get_bookings(status=None, booking_date=None, classroom_id=None, user_id=None, search=None):
    """Retrieve bookings with optional filters."""
    conn = get_db_connection()
    query = """
    SELECT b.*, c.room_number, c.building, c.capacity
    FROM bookings b
    JOIN classrooms c ON b.classroom_id = c.id
    WHERE 1=1
    """
    params = []
    if status and status != 'All':
        query += " AND b.status = ?"
        params.append(status)
    if booking_date:
        query += " AND b.booking_date = ?"
        params.append(booking_date)
    if classroom_id:
        query += " AND b.classroom_id = ?"
        params.append(classroom_id)
    if user_id:
        query += " AND b.user_id = ?"
        params.append(user_id)
    if search:
        query += " AND (b.booking_code LIKE ? OR b.user_name LIKE ? OR b.purpose LIKE ? OR c.room_number LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param, search_param, search_param])
    query += " ORDER BY b.booking_date DESC, b.start_time DESC, b.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def get_booking_by_code(booking_code):
    """Fetch booking by code."""
    conn = get_db_connection()
    row = conn.execute("""
    SELECT b.*, c.room_number, c.building, c.capacity, c.facilities
    FROM bookings b
    JOIN classrooms c ON b.classroom_id = c.id
    WHERE UPPER(b.booking_code) = UPPER(?)
    """, (booking_code.strip(),)).fetchone()
    conn.close()
    return row_to_dict(row)

def get_booking_by_id(booking_id):
    """Fetch booking by ID."""
    conn = get_db_connection()
    row = conn.execute("""
    SELECT b.*, c.room_number, c.building, c.capacity, c.facilities
    FROM bookings b
    JOIN classrooms c ON b.classroom_id = c.id
    WHERE b.id = ?
    """, (booking_id,)).fetchone()
    conn.close()
    return row_to_dict(row)

def create_booking(classroom_id, user_name, user_email, user_role, purpose, booking_date, start_time, end_time, attendees, user_id=None):
    """Insert a new booking request in Pending status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now_ts = datetime.now()
    cursor.execute("SELECT COUNT(*) FROM bookings")
    seq = cursor.fetchone()[0] + 1001
    booking_code = f"BK-{now_ts.strftime('%Y%m')}-{seq}"

    cursor.execute("""
    INSERT INTO bookings (
        booking_code, classroom_id, user_id, user_name, user_email, user_role,
        purpose, booking_date, start_time, end_time, attendees, status
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
    """, (booking_code, classroom_id, user_id, user_name.strip(), user_email.strip(), user_role.strip(),
          purpose.strip(), booking_date.strip(), start_time.strip(), end_time.strip(), attendees))
    
    booking_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return booking_id, booking_code

def update_booking_status(booking_id, status, admin_notes=None, rejection_reason=None):
    """Approve or reject a booking."""
    conn = get_db_connection()
    conn.execute("""
    UPDATE bookings
    SET status = ?, admin_notes = ?, rejection_reason = ?
    WHERE id = ?
    """, (status, admin_notes, rejection_reason or admin_notes, booking_id))
    conn.commit()
    conn.close()

# --- MAINTENANCE ---

def get_maintenance_blocks(classroom_id=None, query_date=None):
    """Fetch maintenance blocks."""
    conn = get_db_connection()
    query = """
    SELECT m.*, c.room_number, c.building
    FROM maintenance_blocks m
    JOIN classrooms c ON m.classroom_id = c.id
    WHERE 1=1
    """
    params = []
    if classroom_id:
        query += " AND m.classroom_id = ?"
        params.append(classroom_id)
    if query_date:
        query += " AND ? BETWEEN m.start_date AND m.end_date"
        params.append(query_date)
    query += " ORDER BY m.start_date, m.start_time"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

def add_maintenance_block(classroom_id, start_date, start_time, end_date, end_time, reason):
    """Schedule a room maintenance window."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO maintenance_blocks (classroom_id, start_date, start_time, end_date, end_time, reason)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (classroom_id, start_date.strip(), start_time.strip(), end_date.strip(), end_time.strip(), reason.strip()))
    block_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return block_id

def delete_maintenance_block(block_id):
    """Remove a maintenance block."""
    conn = get_db_connection()
    conn.execute("DELETE FROM maintenance_blocks WHERE id = ?", (block_id,))
    conn.commit()
    conn.close()

# --- AUDIT LOGS ---

def add_audit_log(user_id, user_name, action, details):
    """Append entry to system audit trail."""
    conn = get_db_connection()
    conn.execute("""
    INSERT INTO audit_logs (user_id, user_name, action, details)
    VALUES (?, ?, ?, ?)
    """, (user_id, user_name, action, details))
    conn.commit()
    conn.close()

def get_audit_logs(limit=50):
    """Retrieve recent system audit logs."""
    conn = get_db_connection()
    rows = conn.execute("""
    SELECT * FROM audit_logs
    ORDER BY created_at DESC
    LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]

# --- SYSTEM STATS ---

def get_system_stats():
    """Retrieve high-level system summary counts for dashboards."""
    conn = get_db_connection()
    
    total_rooms = conn.execute("SELECT COUNT(*) FROM classrooms WHERE is_active = 1").fetchone()[0]
    total_classes = conn.execute("SELECT COUNT(*) FROM scheduled_classes").fetchone()[0]
    pending_bookings = conn.execute("SELECT COUNT(*) FROM bookings WHERE status = 'Pending'").fetchone()[0]
    approved_bookings = conn.execute("SELECT COUNT(*) FROM bookings WHERE status = 'Approved'").fetchone()[0]
    active_maintenance = conn.execute("SELECT COUNT(*) FROM maintenance_blocks").fetchone()[0]
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    
    conn.close()
    return {
        "total_rooms": total_rooms,
        "total_classes": total_classes,
        "pending_bookings": pending_bookings,
        "approved_bookings": approved_bookings,
        "active_maintenance": active_maintenance,
        "total_users": total_users
    }

if __name__ == "__main__":
    init_db()
    seed_demo_data(force=True)
    print("Database initialized and demo data seeded successfully.")
