# SmartCampus — Intelligent Classroom Availability and Booking System

SmartCampus is a full-stack, hackathon-grade web application built to help college students, faculty, and administrators find, evaluate, and book suitable classrooms across campus. Availability and recommendations are determined by correlating academic timetable schedules, verified reservations, and scheduled maintenance windows.

---

## 🌟 Key Features

### 1. Student Dashboard & Live Slot Availability
- **Live Slot Explorer:** Select any date and time window (e.g., `10:00 - 11:30`) to evaluate classroom status.
- **Dynamic Status Classification:**
  - 🟢 **Available:** Room is free of classes, bookings, and maintenance.
  - 🟡 **Occupied by Class:** Active lecture or lab session from the academic course schedule (displays course code, course name, instructor).
  - 🔵 **Reserved / Booked:** Approved reservation (displays purpose and requester role).
  - 🔴 **Under Maintenance:** Room temporarily closed for repairs or calibration (displays maintenance reason).
- **Multi-Filter Controls:** Filter by building, minimum seating capacity, keyword search, and facility amenities (Projector, Smart Board, AC, Video Conferencing, Lab Computers, Wheelchair Accessible).
- **Weekly Timetable Modal:** View full weekly schedules and upcoming bookings for any classroom with one click.

### 2. Transparent Heuristic Smart Room Recommendation
- **Multi-Criteria Scoring Engine:** Ranks free classrooms based on how closely they fit your event requirements:
  - **Capacity Fit (45%):** Calculates capacity utilization ratio ($\text{attendees} / \text{capacity}$). Rewards optimal room utilization (65%–95%) so auditoriums aren't wasted on small study groups.
  - **Facilities Match (40%):** Matches required equipment (Projector, Smart Board, AC, etc.) with bonus points for extra amenities.
  - **Building Proximity (15%):** Boosts score if room matches preferred building.
  - **Accessibility Bonus (5%):** Priority for ground floor and wheelchair accessible rooms.
- **Transparent Reasoning:** Provides human-readable bullet points explaining *why* each room was recommended.
- *Notice:* Transparent deterministic heuristic algorithm — no opaque black-box AI claims.

### 3. Conflict-Free Booking System
- Submit booking requests with name, campus email, role, purpose, date, time slot, and expected attendee count.
- **Backend Validation:**
  - Validates that attendees do not exceed classroom capacity.
  - Validates start time precedes end time.
  - Validates zero overlaps with scheduled classes, existing approved bookings, and maintenance windows.
- Automatically generates unique tracking codes (e.g., `BK-202610-1004`).
- **Status Lifecycle:** `Pending` $\to$ `Approved` or `Rejected` with administrative remarks.

### 4. Admin Portal & Facilities Management
- **Pending Approvals Queue:** One-click approval or rejection with custom remarks. Re-checks for overlapping bookings before approval to prevent race conditions.
- **Classroom Directory:** Add new classrooms or update room details, capacities, and facilities.
- **Maintenance Scheduler:** Block rooms for scheduled facility maintenance (HVAC repairs, projector replacement, etc.).
- **Live Metric Counters:** Displays active rooms, weekly classes, pending approvals, approved bookings, and maintenance windows.
- **Reset Demo Data:** One-click restore button to reset the database to pristine demonstration seed data anytime.

---

## 🏗️ Project Architecture & File Structure

```text
smartcampus/
├── app.py                  # Flask server controller & REST API routes
├── database.py             # SQLite schema, queries, and demonstration data seeder
├── services.py             # Availability calculator, conflict detector, recommendation engine
├── test_system.py          # Automated verification test suite
├── requirements.txt        # Python dependencies (Flask)
├── README.md               # Setup and architecture documentation
├── templates/
│   └── index.html          # Clean responsive dashboard with modals & tabs
└── static/
    ├── css/
    │   └── styles.css      # Custom Navy blue, electric cyan, and white styling
    └── js/
        └── app.js          # Dynamic UI state, REST API calls, debounced search, toasts
```

---

## 💻 Tech Stack
- **Frontend:** Semantic HTML5, Custom Responsive CSS3 (Navy Blue & Cyan palette), Vanilla JavaScript (ES6+ async/await)
- **Backend:** Python 3 (Flask 3.x REST API)
- **Database:** SQLite 3 (with foreign key enforcement and indexed queries)
- **Testing:** Python `unittest` suite

---

## 🚀 Quickstart: Exact Windows Terminal Commands

Follow these steps in **PowerShell** or **Command Prompt**:

### Step 1: Navigate to the Project Directory
```powershell
cd "c:\Users\ganes\OneDrive\Desktop\SmartCampus\SmartCampus"
```

### Step 2: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 3: Run the Verification Test Suite
```powershell
python test_system.py
```
*Expected output: `Ran 6 tests in ... OK`*

### Step 4: Start the Application
```powershell
python app.py
```

### Step 5: Open in Your Browser
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🧪 Demonstration Data
The system comes pre-seeded with 9 realistic classrooms across 4 campus buildings:
1. **ENG-101** (Engineering Hall, Floor 1, 120 seats, Auditorium)
2. **ENG-204** (Engineering Hall, Floor 2, 45 seats, Computer Lab)
3. **ENG-310** (Engineering Hall, Floor 3, 30 seats, Seminar Room)
4. **SCI-105** (Science Complex, Floor 1, 80 seats, Lecture Hall)
5. **SCI-202** (Science Complex, Floor 2, 35 seats, Science Lab)
6. **TECH-101** (Tech Tower, Floor 1, 200 seats, Main Auditorium)
7. **TECH-405** (Tech Tower, Floor 4, 25 seats, Innovation Studio)
8. **HUM-201** (Humanities Center, Floor 2, 55 seats, Lecture Hall)
9. **HUM-304** (Humanities Center, Floor 3, 20 seats, Discussion Room)

Includes recurring classes across Monday–Saturday, sample bookings (Approved, Pending, Rejected), and active maintenance blocks.
