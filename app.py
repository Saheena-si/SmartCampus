"""
SmartCampus - Intelligent Classroom Availability & Booking System
Flask Application Controller and REST API with Role-Based Authentication & Dashboards.
"""

import os
from functools import wraps
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, session

from database import (
    init_db, seed_demo_data, get_classrooms, get_classroom_by_id,
    get_classroom_by_number, add_classroom, update_classroom, delete_classroom,
    get_scheduled_classes, get_scheduled_class_by_id, add_scheduled_class, delete_scheduled_class,
    get_bookings, get_booking_by_code, get_booking_by_id, create_booking, update_booking_status,
    get_maintenance_blocks, add_maintenance_block, delete_maintenance_block,
    get_system_stats, verify_user_credentials, get_user_by_id, get_user_by_username,
    get_all_users, update_user_role, add_manual_update, get_manual_updates, delete_manual_update,
    add_class_cancellation, get_class_cancellations, delete_class_cancellation,
    add_audit_log, get_audit_logs, get_db_connection
)
from services import (
    get_dashboard_rooms_availability, validate_booking_request,
    recommend_classrooms, check_room_status_for_slot, times_overlap, parse_time_str
)

app = Flask(__name__)
# Secret key configured via environment variable with secure fallback for local demonstration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'smartcampus-hackathon-secure-key-2026')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Ensure database tables exist and seed demo data
init_db()
seed_demo_data(force=False)

# ============================================================
# AUTHENTICATION HELPERS & DECORATORS
# ============================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"success": False, "error": "Authentication required. Please log in."}), 401
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*allowed_roles):
    """Enforce strict role-based access control on the backend."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({"success": False, "error": "Authentication required. Please log in."}), 401
            user = get_user_by_id(session['user_id'])
            if not user or user['role'].lower() not in [r.lower() for r in allowed_roles]:
                return jsonify({
                    "success": False,
                    "error": f"Permission Denied. This operation requires one of: {', '.join(allowed_roles)}. Your role is '{user.get('role', 'unknown')}'."
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ============================================================
# FRONTEND ROUTE
# ============================================================

@app.route('/')
def index():
    """Render main application dashboard."""
    return render_template('index.html')

# ============================================================
# AUTHENTICATION API
# ============================================================

@app.route('/api/auth/login', methods=['POST'])
def api_auth_login():
    """Authenticate demo user using secure hashed password check."""
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password are required."}), 400

    user = verify_user_credentials(username, password)
    if not user:
        return jsonify({"success": False, "error": "Invalid username or password."}), 401

    # Store user identity in server session
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['full_name'] = user['full_name']
    session['assigned_class'] = user.get('assigned_class')

    add_audit_log(user['id'], user['full_name'], "USER_LOGIN", f"User {username} logged in with role {user['role']}.")

    return jsonify({
        "success": True,
        "message": f"Welcome, {user['full_name']}!",
        "user": user
    })

@app.route('/api/auth/logout', methods=['POST'])
def api_auth_logout():
    """Log out current user and clear server session."""
    user_id = session.get('user_id')
    user_name = session.get('full_name', 'Unknown')
    if user_id:
        add_audit_log(user_id, user_name, "USER_LOGOUT", "User logged out.")
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."})

@app.route('/api/auth/me', methods=['GET'])
def api_auth_me():
    """Return currently authenticated user profile."""
    if 'user_id' not in session:
        return jsonify({"success": True, "authenticated": False, "user": None})

    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        return jsonify({"success": True, "authenticated": False, "user": None})

    return jsonify({
        "success": True,
        "authenticated": True,
        "user": {
            "id": user['id'],
            "username": user['username'],
            "full_name": user['full_name'],
            "email": user['email'],
            "role": user['role'],
            "assigned_class": user.get('assigned_class')
        }
    })

# ============================================================
# CLASSROOMS & LABS API
# ============================================================

@app.route('/api/classrooms', methods=['GET'])
def api_get_classrooms():
    """Return all active classrooms."""
    include_inactive = request.args.get('all', '0') == '1'
    rooms = get_classrooms(include_inactive=include_inactive)
    return jsonify({"success": True, "classrooms": rooms})

@app.route('/api/classrooms/<int:room_id>', methods=['GET'])
def api_get_classroom_detail(room_id):
    """Return classroom detail along with full timetable and bookings."""
    room = get_classroom_by_id(room_id)
    if not room:
        return jsonify({"success": False, "error": "Classroom not found"}), 404

    classes = get_scheduled_classes(classroom_id=room_id)
    bookings = get_bookings(classroom_id=room_id)
    maintenance = get_maintenance_blocks(classroom_id=room_id)
    manual_updates = get_manual_updates(classroom_id=room_id)

    return jsonify({
        "success": True,
        "classroom": room,
        "classes": classes,
        "bookings": bookings,
        "maintenance": maintenance,
        "manual_updates": manual_updates
    })

@app.route('/api/classrooms', methods=['POST'])
@roles_required('admin')
def api_add_classroom():
    """Admin endpoint to create a new classroom."""
    data = request.get_json() or {}
    room_number = data.get('room_number', '').strip().upper()
    building = data.get('building', '').strip()
    room_type = data.get('room_type', 'Classroom').strip()
    facilities = data.get('facilities', '').strip()
    notes = data.get('notes', '').strip()

    if not room_number or not building:
        return jsonify({"success": False, "error": "Room number and Building are required."}), 400

    try:
        floor = int(data.get('floor', 1))
        capacity = int(data.get('capacity', 30))
        if capacity <= 0:
            return jsonify({"success": False, "error": "Capacity must be greater than zero."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Floor and Capacity must be valid integers."}), 400

    existing = get_classroom_by_number(room_number)
    if existing:
        return jsonify({"success": False, "error": f"Room number '{room_number}' already exists."}), 409

    new_id = add_classroom(room_number, building, floor, capacity, room_type, facilities, notes)
    add_audit_log(session['user_id'], session.get('full_name'), "CLASSROOM_ADD", f"Created classroom {room_number} in {building}.")
    return jsonify({"success": True, "message": f"Classroom {room_number} added successfully.", "classroom_id": new_id}), 201

@app.route('/api/classrooms/<int:room_id>', methods=['PUT'])
@roles_required('admin')
def api_update_classroom(room_id):
    """Admin endpoint to update classroom details."""
    data = request.get_json() or {}
    room = get_classroom_by_id(room_id)
    if not room:
        return jsonify({"success": False, "error": "Classroom not found"}), 404

    room_number = data.get('room_number', room['room_number']).strip().upper()
    building = data.get('building', room['building']).strip()
    room_type = data.get('room_type', room['room_type']).strip()
    facilities = data.get('facilities', room['facilities']).strip()
    notes = data.get('notes', room.get('notes', '')).strip()
    is_active = int(data.get('is_active', room['is_active']))

    try:
        floor = int(data.get('floor', room['floor']))
        capacity = int(data.get('capacity', room['capacity']))
        if capacity <= 0:
            return jsonify({"success": False, "error": "Capacity must be greater than zero."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Floor and Capacity must be integers."}), 400

    if room_number != room['room_number']:
        existing = get_classroom_by_number(room_number)
        if existing and existing['id'] != room_id:
            return jsonify({"success": False, "error": f"Room number '{room_number}' is taken."}), 409

    update_classroom(room_id, room_number, building, floor, capacity, room_type, facilities, notes, is_active)
    add_audit_log(session['user_id'], session.get('full_name'), "CLASSROOM_UPDATE", f"Updated classroom {room_number}.")
    return jsonify({"success": True, "message": f"Classroom {room_number} updated successfully."})

@app.route('/api/classrooms/<int:room_id>', methods=['DELETE'])
@roles_required('admin')
def api_delete_classroom(room_id):
    """Admin endpoint to deactivate a classroom."""
    room = get_classroom_by_id(room_id)
    if not room:
        return jsonify({"success": False, "error": "Classroom not found"}), 404

    delete_classroom(room_id)
    add_audit_log(session['user_id'], session.get('full_name'), "CLASSROOM_DEACTIVATE", f"Deactivated classroom {room['room_number']}.")
    return jsonify({"success": True, "message": f"Classroom {room['room_number']} deactivated."})

# ============================================================
# AVAILABILITY API
# ============================================================

@app.route('/api/availability', methods=['GET'])
def api_get_availability():
    """
    Evaluates classroom availability for a requested date and time slot.
    Returns categorized counts and room cards.
    """
    now = datetime.now()
    default_date = now.strftime('%Y-%m-%d')
    default_start = now.strftime('%H:00')
    default_end = f"{(now.hour + 1) % 24:02d}:00"

    query_date = request.args.get('date', default_date).strip()
    start_time = request.args.get('start_time', default_start).strip()
    end_time = request.args.get('end_time', default_end).strip()
    building = request.args.get('building', 'All').strip()
    search = request.args.get('search', '').strip()

    min_cap = request.args.get('min_capacity')
    max_cap = request.args.get('max_capacity')
    try:
        min_cap = int(min_cap) if min_cap else None
        max_cap = int(max_cap) if max_cap else None
    except ValueError:
        min_cap, max_cap = None, None

    facilities_raw = request.args.get('facilities', '').strip()
    facilities_filter = [f.strip() for f in facilities_raw.split(',') if f.strip()] if facilities_raw else None

    try:
        datetime.strptime(query_date, '%Y-%m-%d')
    except ValueError:
        return jsonify({"success": False, "error": "Invalid date format. Expected YYYY-MM-DD."}), 400

    result = get_dashboard_rooms_availability(
        query_date=query_date,
        start_time=start_time,
        end_time=end_time,
        building_filter=building,
        min_cap=min_cap,
        max_cap=max_cap,
        facilities_filter=facilities_filter,
        search_query=search
    )
    result["success"] = True
    return jsonify(result)

# ============================================================
# SMART RECOMMENDATION API
# ============================================================

@app.route('/api/recommend', methods=['POST'])
def api_recommend_rooms():
    """
    Transparent Heuristic Room Recommendation endpoint.
    Computes best matching rooms based on time, capacity efficiency, and requested facilities.
    """
    data = request.get_json() or {}
    booking_date = data.get('date', '').strip()
    start_time = data.get('start_time', '').strip()
    end_time = data.get('end_time', '').strip()
    attendees = data.get('attendees', 1)
    required_facilities = data.get('required_facilities', [])
    preferred_building = data.get('preferred_building', '').strip()

    if not booking_date or not start_time or not end_time:
        return jsonify({"success": False, "error": "Date, start time, and end time are required."}), 400

    try:
        attendees = int(attendees)
        if attendees <= 0:
            return jsonify({"success": False, "error": "Attendees count must be greater than zero."}), 400
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid attendee count."}), 400

    res = recommend_classrooms(
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        attendees=attendees,
        required_facilities=required_facilities,
        preferred_building=preferred_building
    )
    res["success"] = True
    return jsonify(res)

# ============================================================
# BOOKING SUBMISSION & MANAGEMENT API
# ============================================================

@app.route('/api/bookings', methods=['GET'])
def api_get_bookings():
    """Retrieve bookings list with optional filtering and student isolation."""
    status = request.args.get('status', 'All')
    booking_date = request.args.get('date')
    search = request.args.get('search')
    my_only = request.args.get('my', '0') == '1'

    user_id = None
    if my_only:
        if 'user_id' not in session:
            return jsonify({"success": False, "error": "Please log in to view your bookings."}), 401
        user_id = session['user_id']
    elif 'user_id' in session and session.get('role') == 'student':
        # Default student view to their own bookings
        user_id = session['user_id']

    bookings = get_bookings(status=status, booking_date=booking_date, user_id=user_id, search=search)
    return jsonify({"success": True, "bookings": bookings})

@app.route('/api/bookings/<booking_ref>', methods=['GET'])
def api_get_booking_detail(booking_ref):
    """Retrieve a booking by code or ID."""
    if booking_ref.isdigit():
        bk = get_booking_by_id(int(booking_ref))
    else:
        bk = get_booking_by_code(booking_ref)

    if not bk:
        return jsonify({"success": False, "error": "Booking reference not found."}), 404

    return jsonify({"success": True, "booking": bk})

@app.route('/api/bookings', methods=['POST'])
def api_submit_booking():
    """
    Submit a classroom booking request.
    Validates capacity and checks schedule conflicts.
    """
    data = request.get_json() or {}
    
    # Auto-fill user credentials if authenticated
    curr_user_id = session.get('user_id')
    curr_user = get_user_by_id(curr_user_id) if curr_user_id else None
    if curr_user:
        if not data.get('user_name'):
            data['user_name'] = curr_user['full_name']
        if not data.get('user_email'):
            data['user_email'] = curr_user['email']
        if not data.get('user_role'):
            data['user_role'] = curr_user['role'].capitalize()

    is_valid, error_msg = validate_booking_request(data)
    if not is_valid:
        return jsonify({"success": False, "error": error_msg}), 400

    classroom_id = int(data['classroom_id'])
    user_name = data['user_name']
    user_email = data['user_email']
    user_role = data.get('user_role', 'Student')
    purpose = data['purpose']
    booking_date = data['booking_date']
    start_time = data['start_time']
    end_time = data['end_time']
    attendees = int(data['attendees'])

    booking_id, booking_code = create_booking(
        classroom_id=classroom_id,
        user_name=user_name,
        user_email=user_email,
        user_role=user_role,
        purpose=purpose,
        booking_date=booking_date,
        start_time=start_time,
        end_time=end_time,
        attendees=attendees,
        user_id=curr_user_id
    )

    room = get_classroom_by_id(classroom_id)
    if curr_user_id:
        add_audit_log(curr_user_id, user_name, "BOOKING_SUBMIT", f"Submitted booking {booking_code} for {room['room_number']}.")

    return jsonify({
        "success": True,
        "message": f"Booking request submitted successfully! Reference Code: {booking_code}",
        "booking_id": booking_id,
        "booking_code": booking_code,
        "status": "Pending",
        "room_number": room['room_number'] if room else ""
    }), 201

@app.route('/api/bookings/<int:booking_id>/action', methods=['POST'])
@roles_required('staff', 'admin')
def api_booking_action(booking_id):
    """
    Staff / Admin approval or rejection of a booking request.
    Uses SQLite transaction to re-validate conflict at time of approval.
    """
    data = request.get_json() or {}
    action = data.get('action', '').strip().capitalize() # 'Approved' or 'Rejected'
    admin_notes = data.get('admin_notes', '').strip()
    rejection_reason = data.get('rejection_reason', admin_notes).strip()

    if action not in ['Approved', 'Rejected']:
        return jsonify({"success": False, "error": "Action must be 'Approved' or 'Rejected'."}), 400

    if action == 'Rejected' and not rejection_reason:
        return jsonify({"success": False, "error": "A rejection reason is required when rejecting a booking request."}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE TRANSACTION")

        cursor.execute("""
        SELECT b.*, c.room_number FROM bookings b
        JOIN classrooms c ON b.classroom_id = c.id
        WHERE b.id = ?
        """, (booking_id,))
        bk_row = cursor.fetchone()
        if not bk_row:
            conn.rollback()
            conn.close()
            return jsonify({"success": False, "error": "Booking request not found."}), 404

        bk = dict(bk_row)

        if action == 'Approved':
            # Recheck conflicts using transaction state
            status_info = check_room_status_for_slot(
                classroom_id=bk['classroom_id'],
                query_date=bk['booking_date'],
                start_time=bk['start_time'],
                end_time=bk['end_time']
            )
            if status_info['status'] not in ['available', 'unconfirmed']:
                conn.rollback()
                conn.close()
                return jsonify({
                    "success": False,
                    "error": f"Cannot approve booking: Classroom {bk['room_number']} already has a conflicting {status_info['badge_label']} ({status_info['conflict_reason']})."
                }), 409

        cursor.execute("""
        UPDATE bookings
        SET status = ?, admin_notes = ?, rejection_reason = ?
        WHERE id = ?
        """, (action, admin_notes or rejection_reason, rejection_reason if action == 'Rejected' else None, booking_id))

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"success": False, "error": f"Transaction failed: {str(e)}"}), 500

    conn.close()

    add_audit_log(
        session.get('user_id'),
        session.get('full_name'),
        f"BOOKING_{action.upper()}",
        f"Booking {bk['booking_code']} {action.lower()}. Reason/Notes: {admin_notes or rejection_reason}"
    )

    return jsonify({
        "success": True,
        "message": f"Booking request {bk['booking_code']} has been {action.lower()}."
    })

# ============================================================
# STAFF MANUAL AVAILABILITY UPDATES API
# ============================================================

@app.route('/api/staff/manual-updates', methods=['GET'])
@roles_required('staff', 'admin')
def api_get_manual_updates():
    """Retrieve manual availability updates list."""
    query_date = request.args.get('date')
    updates = get_manual_updates(query_date=query_date)
    return jsonify({"success": True, "manual_updates": updates})

@app.route('/api/staff/manual-updates', methods=['POST'])
@roles_required('staff', 'admin')
def api_add_manual_update():
    """
    Staff / Admin endpoint to record confirmed occupancy or reserve for extra class/meeting.
    Checks for overlapping approved bookings and maintenance to prevent silent overrides.
    """
    data = request.get_json() or {}
    classroom_id = data.get('classroom_id')
    update_date = (data.get('update_date') or '').strip()
    start_time = (data.get('start_time') or '').strip()
    end_time = (data.get('end_time') or '').strip()
    status_type = data.get('status_type', 'Occupied — Manual Update').strip()
    reason = (data.get('reason') or '').strip()

    if not classroom_id or not update_date or not start_time or not end_time or not reason:
        return jsonify({"success": False, "error": "Classroom, date, start time, end time, and reason are required."}), 400

    try:
        classroom_id = int(classroom_id)
        datetime.strptime(update_date, '%Y-%m-%d')
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid classroom or date format."}), 400

    t_start = parse_time_str(start_time)
    t_end = parse_time_str(end_time)
    if not t_start or not t_end or t_start >= t_end:
        return jsonify({"success": False, "error": "Start time must be strictly before end time."}), 400

    room = get_classroom_by_id(classroom_id)
    if not room:
        return jsonify({"success": False, "error": "Classroom not found."}), 404

    # Check that manual update does NOT create an overlap with an existing approved booking or maintenance
    existing_status = check_room_status_for_slot(classroom_id, update_date, start_time, end_time)
    if existing_status['status'] in ['reserved', 'maintenance']:
        return jsonify({
            "success": False,
            "error": f"Cannot record update: Slot has conflicting {existing_status['badge_label']} ({existing_status['conflict_reason']})."
        }), 409

    uid = add_manual_update(
        classroom_id=classroom_id,
        update_date=update_date,
        start_time=start_time,
        end_time=end_time,
        status_type=status_type,
        reason=reason,
        user_id=session.get('user_id'),
        user_name=session.get('full_name')
    )

    add_audit_log(session.get('user_id'), session.get('full_name'), "MANUAL_UPDATE_ADD",
                  f"Recorded manual update for {room['room_number']} on {update_date} ({start_time}-{end_time}): {reason}")

    return jsonify({"success": True, "message": "Manual availability update saved successfully.", "update_id": uid}), 201

@app.route('/api/staff/manual-updates/<int:update_id>', methods=['DELETE'])
@roles_required('staff', 'admin')
def api_delete_manual_update(update_id):
    """Remove a manual availability update."""
    delete_manual_update(update_id)
    add_audit_log(session.get('user_id'), session.get('full_name'), "MANUAL_UPDATE_DELETE", f"Deleted manual update ID {update_id}.")
    return jsonify({"success": True, "message": "Manual update removed."})

# ============================================================
# CLASS / LAB SESSION CANCELLATIONS API (Staff & CR)
# ============================================================

@app.route('/api/cancellations', methods=['GET'])
def api_get_cancellations():
    """Retrieve recorded single-session cancellations."""
    query_date = request.args.get('date')
    cancellations = get_class_cancellations(query_date=query_date)
    return jsonify({"success": True, "cancellations": cancellations})

@app.route('/api/cancellations', methods=['POST'])
@roles_required('staff', 'cr', 'admin')
def api_add_cancellation():
    """
    Record a single-session class or lab cancellation.
    CRs may ONLY cancel sessions for their explicitly assigned class!
    """
    data = request.get_json() or {}
    scheduled_class_id = data.get('scheduled_class_id')
    cancellation_date = (data.get('cancellation_date') or '').strip()
    reason = (data.get('reason') or '').strip()

    if not scheduled_class_id or not cancellation_date or not reason:
        return jsonify({"success": False, "error": "Scheduled class ID, cancellation date, and reason are required."}), 400

    try:
        scheduled_class_id = int(scheduled_class_id)
        datetime.strptime(cancellation_date, '%Y-%m-%d')
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid class ID or date format."}), 400

    cls = get_scheduled_class_by_id(scheduled_class_id)
    if not cls:
        return jsonify({"success": False, "error": "Scheduled class not found."}), 404

    # Strict CR Permission Enforcement on Backend
    user_role = session.get('role', '').lower()
    if user_role == 'cr':
        user = get_user_by_id(session['user_id'])
        assigned_class = (user.get('assigned_class') or '').strip().lower()
        class_group = (cls.get('class_group') or '').strip().lower()

        if not assigned_class or assigned_class != class_group:
            return jsonify({
                "success": False,
                "error": f"Permission Denied: As Class Representative for '{user.get('assigned_class')}', you are only authorized to report cancellations for your assigned class. This class belongs to '{cls.get('class_group')}'."
            }), 403

    cid = add_class_cancellation(
        scheduled_class_id=scheduled_class_id,
        cancellation_date=cancellation_date,
        reason=reason,
        user_id=session.get('user_id'),
        user_name=session.get('full_name')
    )

    add_audit_log(
        session.get('user_id'),
        session.get('full_name'),
        "CLASS_CANCEL",
        f"Cancelled session {cls['course_code']} ({cls['course_name']}) in {cls['room_number']} on {cancellation_date}. Reason: {reason}"
    )

    return jsonify({
        "success": True,
        "message": f"Session {cls['course_code']} cancelled for {cancellation_date}. Room {cls['room_number']} conflict is cleared for this slot.",
        "cancellation_id": cid
    }), 201

@app.route('/api/cancellations/<int:cancellation_id>', methods=['DELETE'])
@roles_required('staff', 'admin')
def api_delete_cancellation(cancellation_id):
    """Restore a cancelled class session."""
    delete_class_cancellation(cancellation_id)
    add_audit_log(session.get('user_id'), session.get('full_name'), "CLASS_RESTORE", f"Restored class cancellation ID {cancellation_id}.")
    return jsonify({"success": True, "message": "Cancellation removed. Session restored to active timetable."})

# ============================================================
# CLASS REPRESENTATIVE SPECIFIC API
# ============================================================

@app.route('/api/cr/assigned-timetable', methods=['GET'])
@roles_required('cr', 'admin')
def api_get_cr_timetable():
    """Retrieve full weekly timetable for CR's assigned class group."""
    user = get_user_by_id(session['user_id'])
    assigned_class = user.get('assigned_class') if user['role'] == 'cr' else request.args.get('class_group', 'III Year CSE A')

    if not assigned_class:
        return jsonify({"success": False, "error": "No assigned class found for this Class Representative."}), 400

    classes = get_scheduled_classes(class_group=assigned_class)
    return jsonify({
        "success": True,
        "assigned_class": assigned_class,
        "classes": classes
    })

# ============================================================
# MAINTENANCE API
# ============================================================

@app.route('/api/maintenance', methods=['GET'])
def api_get_maintenance():
    """List maintenance blocks."""
    blocks = get_maintenance_blocks()
    return jsonify({"success": True, "maintenance_blocks": blocks})

@app.route('/api/maintenance', methods=['POST'])
@roles_required('admin')
def api_add_maintenance():
    """Admin endpoint to block a room for maintenance."""
    data = request.get_json() or {}
    classroom_id = data.get('classroom_id')
    start_date = data.get('start_date', '').strip()
    start_time = data.get('start_time', '').strip()
    end_date = data.get('end_date', '').strip()
    end_time = data.get('end_time', '').strip()
    reason = data.get('reason', '').strip()

    if not classroom_id or not start_date or not start_time or not end_date or not end_time or not reason:
        return jsonify({"success": False, "error": "All maintenance fields are required."}), 400

    block_id = add_maintenance_block(
        classroom_id=int(classroom_id),
        start_date=start_date,
        start_time=start_time,
        end_date=end_date,
        end_time=end_time,
        reason=reason
    )

    room = get_classroom_by_id(int(classroom_id))
    add_audit_log(session.get('user_id'), session.get('full_name'), "MAINTENANCE_ADD",
                  f"Scheduled maintenance for {room['room_number']} ({start_date} to {end_date}): {reason}")

    return jsonify({"success": True, "message": "Maintenance window scheduled successfully.", "block_id": block_id}), 201

@app.route('/api/maintenance/<int:block_id>', methods=['DELETE'])
@roles_required('admin')
def api_delete_maintenance(block_id):
    """Admin endpoint to remove a maintenance block."""
    delete_maintenance_block(block_id)
    add_audit_log(session.get('user_id'), session.get('full_name'), "MAINTENANCE_DELETE", f"Removed maintenance block ID {block_id}.")
    return jsonify({"success": True, "message": "Maintenance block removed."})

# ============================================================
# ADMIN MASTER TIMETABLE & USER MANAGEMENT API
# ============================================================

@app.route('/api/admin/classes', methods=['POST'])
@roles_required('admin')
def api_admin_add_class():
    """Admin endpoint to add a new scheduled class."""
    data = request.get_json() or {}
    classroom_id = data.get('classroom_id')
    class_group = (data.get('class_group') or 'General').strip()
    course_code = (data.get('course_code') or '').strip().upper()
    course_name = (data.get('course_name') or '').strip()
    instructor = (data.get('instructor') or '').strip()
    day_of_week = (data.get('day_of_week') or '').strip()
    start_time = (data.get('start_time') or '').strip()
    end_time = (data.get('end_time') or '').strip()
    session_name = (data.get('session_name') or '').strip()

    if not classroom_id or not course_code or not course_name or not instructor or not day_of_week or not start_time or not end_time:
        return jsonify({"success": False, "error": "All timetable entry fields are required."}), 400

    cid = add_scheduled_class(
        classroom_id=int(classroom_id),
        class_group=class_group,
        course_code=course_code,
        course_name=course_name,
        instructor=instructor,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        session_name=session_name
    )

    room = get_classroom_by_id(int(classroom_id))
    add_audit_log(session.get('user_id'), session.get('full_name'), "TIMETABLE_ADD",
                  f"Added class {course_code} ({day_of_week} {start_time}-{end_time}) in {room['room_number']}.")

    return jsonify({"success": True, "message": f"Class {course_code} added to timetable.", "class_id": cid}), 201

@app.route('/api/admin/classes/<int:class_id>', methods=['DELETE'])
@roles_required('admin')
def api_admin_delete_class(class_id):
    """Admin endpoint to remove a timetable entry."""
    delete_scheduled_class(class_id)
    add_audit_log(session.get('user_id'), session.get('full_name'), "TIMETABLE_DELETE", f"Removed timetable entry ID {class_id}.")
    return jsonify({"success": True, "message": "Class timetable entry removed."})

@app.route('/api/admin/users', methods=['GET'])
@roles_required('admin')
def api_admin_get_users():
    """Retrieve all users and their role assignments."""
    users = get_all_users()
    return jsonify({"success": True, "users": users})

@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@roles_required('admin')
def api_admin_update_user(user_id):
    """Admin endpoint to update user role and CR assigned class."""
    data = request.get_json() or {}
    role = (data.get('role') or 'student').strip().lower()
    assigned_class = (data.get('assigned_class') or '').strip() or None

    if role not in ['student', 'staff', 'cr', 'admin']:
        return jsonify({"success": False, "error": "Invalid role specified."}), 400

    update_user_role(user_id, role, assigned_class)
    target_user = get_user_by_id(user_id)
    add_audit_log(session.get('user_id'), session.get('full_name'), "USER_ROLE_UPDATE",
                  f"Updated user {target_user['username']} role to {role} (Assigned Class: {assigned_class or 'None'}).")

    return jsonify({"success": True, "message": f"User {target_user['username']} updated successfully."})

@app.route('/api/admin/audit-logs', methods=['GET'])
@roles_required('admin')
def api_admin_get_audit_logs():
    """Retrieve system audit activity trail."""
    logs = get_audit_logs(limit=100)
    return jsonify({"success": True, "audit_logs": logs})

# ============================================================
# SYSTEM STATS & DEMO RESET API
# ============================================================

@app.route('/api/stats', methods=['GET'])
def api_get_stats():
    """Returns high-level statistics for dashboards."""
    stats = get_system_stats()
    return jsonify({"success": True, "stats": stats})

@app.route('/api/demo/reset', methods=['POST'])
def api_reset_demo():
    """Resets database to pristine demonstration seed data."""
    seed_demo_data(force=True)
    add_audit_log(session.get('user_id'), session.get('full_name', 'System'), "DEMO_RESET", "Reset demonstration database.")
    return jsonify({"success": True, "message": "Demonstration data reset successfully!"})

if __name__ == '__main__':
    print("Starting SmartCampus Application on http://127.0.0.1:5000 ...")
    app.run(host='127.0.0.1', port=5000, debug=True)
