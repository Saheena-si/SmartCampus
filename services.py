"""
SmartCampus Core Services & Business Logic Module
Contains:
1. Schedule and reservation conflict checking.
2. Slot availability determination engine with cancellation and manual override support.
3. Transparent heuristic smart room recommendation algorithm.
"""

from datetime import datetime, date, time
from database import (
    get_classrooms, get_classroom_by_id, get_scheduled_classes,
    get_bookings, get_maintenance_blocks, get_manual_updates, is_class_cancelled
)

def parse_time_str(time_str):
    """Parse 'HH:MM' string to datetime.time object."""
    try:
        parts = time_str.strip().split(':')
        return time(int(parts[0]), int(parts[1]))
    except Exception:
        return None

def times_overlap(start1_str, end1_str, start2_str, end2_str):
    """
    Determines if two time intervals [start1, end1] and [start2, end2] overlap.
    Assumes all times are within the same 24-hour day in 'HH:MM' format.
    Interval overlap rule: start1 < end2 and start2 < end1.
    """
    t1_start = parse_time_str(start1_str)
    t1_end = parse_time_str(end1_str)
    t2_start = parse_time_str(start2_str)
    t2_end = parse_time_str(end2_str)

    if not all([t1_start, t1_end, t2_start, t2_end]):
        return False

    return t1_start < t2_end and t2_start < t1_end

def get_day_name(date_str):
    """Returns the full weekday name for a given 'YYYY-MM-DD' string (e.g., 'Monday')."""
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    return dt.strftime('%A')

def check_room_status_for_slot(classroom_id, query_date, start_time, end_time):
    """
    Calculates the exact availability status of a classroom during a requested date/time slot.
    Evaluates:
    1. Maintenance blocks -> 'Unavailable — Maintenance'
    2. Staff manual updates -> 'Occupied — Manual Update'
    3. Approved reservations -> 'Reserved'
    4. Scheduled classes (accounting for single-session cancellations) -> 'Occupied — Scheduled Class'
    5. Operating hours boundary -> 'Availability Unconfirmed'
    6. Normal free slot -> 'Available According to Timetable'

    Returns:
    {
        "status": "available" | "occupied" | "manual_occupied" | "reserved" | "maintenance" | "unconfirmed",
        "badge_label": str (exact status name),
        "conflict_reason": str,
        "conflict_details": dict or None
    }
    """
    # 1. Check Maintenance Blocks first
    maintenance_records = get_maintenance_blocks(classroom_id=classroom_id, query_date=query_date)
    for block in maintenance_records:
        if times_overlap(start_time, end_time, block['start_time'], block['end_time']):
            return {
                "status": "maintenance",
                "badge_label": "Unavailable — Maintenance",
                "conflict_reason": f"Maintenance: {block['reason']}",
                "conflict_details": {
                    "type": "maintenance",
                    "reason": block['reason'],
                    "window": f"{block['start_time']} - {block['end_time']}"
                }
            }

    # 2. Check Staff Manual Availability Updates
    manual_updates = get_manual_updates(classroom_id=classroom_id, query_date=query_date)
    for upd in manual_updates:
        if times_overlap(start_time, end_time, upd['start_time'], upd['end_time']):
            return {
                "status": "manual_occupied",
                "badge_label": "Occupied — Manual Update",
                "conflict_reason": f"Manual Update: {upd['reason']} (by {upd['user_name'] or 'Staff'})",
                "conflict_details": {
                    "type": "manual_update",
                    "reason": upd['reason'],
                    "status_type": upd['status_type'],
                    "user_name": upd['user_name'],
                    "window": f"{upd['start_time']} - {upd['end_time']}"
                }
            }

    # 3. Check Approved Booking Reservations
    bookings = get_bookings(status='Approved', booking_date=query_date, classroom_id=classroom_id)
    for bk in bookings:
        if times_overlap(start_time, end_time, bk['start_time'], bk['end_time']):
            return {
                "status": "reserved",
                "badge_label": "Reserved",
                "conflict_reason": f"Reserved: {bk['purpose']} ({bk['user_role']})",
                "conflict_details": {
                    "type": "booking",
                    "booking_code": bk['booking_code'],
                    "purpose": bk['purpose'],
                    "user_role": bk['user_role'],
                    "user_name": bk['user_name'],
                    "window": f"{bk['start_time']} - {bk['end_time']}"
                }
            }

    # 4. Check Timetable Scheduled Classes (recurring on that weekday)
    day_name = get_day_name(query_date)
    classes = get_scheduled_classes(classroom_id=classroom_id, day_of_week=day_name)
    for cls in classes:
        if times_overlap(start_time, end_time, cls['start_time'], cls['end_time']):
            # Check if this specific session has been recorded as cancelled!
            if is_class_cancelled(cls['id'], query_date):
                # Class session was cancelled on this specific date! Slot conflict is cleared.
                continue

            return {
                "status": "occupied",
                "badge_label": "Occupied — Scheduled Class",
                "conflict_reason": f"Class: {cls['course_code']} - {cls['course_name']} ({cls['instructor']})",
                "conflict_details": {
                    "type": "class",
                    "class_id": cls['id'],
                    "course_code": cls['course_code'],
                    "course_name": cls['course_name'],
                    "instructor": cls['instructor'],
                    "class_group": cls.get('class_group', ''),
                    "session_name": cls.get('session_name', ''),
                    "window": f"{cls['start_time']} - {cls['end_time']}"
                }
            }

    # 5. Check Operating Hours Boundary
    t_start = parse_time_str(start_time)
    t_end = parse_time_str(end_time)
    if (t_start and t_start < time(8, 0)) or (t_end and t_end > time(20, 0)):
        return {
            "status": "unconfirmed",
            "badge_label": "Availability Unconfirmed",
            "conflict_reason": "Outside core academic operating hours (08:00 - 20:00). Physical occupancy unconfirmed.",
            "conflict_details": None
        }

    # 6. Available according to timetable
    return {
        "status": "available",
        "badge_label": "Available According to Timetable",
        "conflict_reason": "No schedule conflicts, bookings, or maintenance for this time slot.",
        "conflict_details": None
    }

def get_dashboard_rooms_availability(query_date, start_time, end_time, building_filter=None, min_cap=None, max_cap=None, facilities_filter=None, search_query=None):
    """
    Evaluates availability for all classrooms based on slot criteria and user filters.
    """
    all_rooms = get_classrooms(include_inactive=False)
    results = []
    
    counts = {
        "total": 0,
        "available": 0,
        "occupied": 0,
        "manual_occupied": 0,
        "reserved": 0,
        "maintenance": 0,
        "unconfirmed": 0
    }

    for room in all_rooms:
        # Building filter
        if building_filter and building_filter != 'All' and room['building'].lower() != building_filter.lower():
            continue
        
        # Capacity filter
        if min_cap is not None and room['capacity'] < min_cap:
            continue
        if max_cap is not None and room['capacity'] > max_cap:
            continue

        # Facilities filter (must include all selected facilities)
        room_facs = room.get('facilities_list', [])
        if facilities_filter:
            room_facs_lower = [f.lower().strip() for f in room_facs]
            has_all_facilities = all(req.lower().strip() in room_facs_lower for req in facilities_filter)
            if not has_all_facilities:
                continue

        # Search query (room number, building, facilities, notes)
        if search_query:
            sq = search_query.lower().strip()
            text_corpus = f"{room['room_number']} {room['building']} {room.get('room_type', '')} {room['facilities']} {room.get('notes', '')}".lower()
            if sq not in text_corpus:
                continue

        # Evaluate availability status
        avail_status = check_room_status_for_slot(room['id'], query_date, start_time, end_time)

        counts["total"] += 1
        status_key = avail_status["status"]
        if status_key in counts:
            counts[status_key] += 1
        else:
            counts["available"] += 1

        room_data = dict(room)
        room_data["availability"] = avail_status
        results.append(room_data)

    # Sort: Available first, then by room number
    priority = {"available": 1, "unconfirmed": 2, "reserved": 3, "occupied": 4, "manual_occupied": 5, "maintenance": 6}
    results.sort(key=lambda r: (priority.get(r['availability']['status'], 9), r['room_number']))

    return {
        "query": {
            "date": query_date,
            "start_time": start_time,
            "end_time": end_time,
            "day_of_week": get_day_name(query_date)
        },
        "counts": counts,
        "rooms": results
    }

def validate_booking_request(data):
    """
    Comprehensive validation for booking requests.
    Validates capacity, positive attendees, date/time logic, and schedule conflicts.
    """
    classroom_id = data.get('classroom_id')
    user_name = (data.get('user_name') or '').strip()
    user_email = (data.get('user_email') or '').strip()
    purpose = (data.get('purpose') or '').strip()
    booking_date = (data.get('booking_date') or '').strip()
    start_time = (data.get('start_time') or '').strip()
    end_time = (data.get('end_time') or '').strip()
    attendees = data.get('attendees')

    # 1. Basic field validation
    if not classroom_id:
        return False, "Please select a classroom."
    if not user_name:
        return False, "User name is required."
    if not user_email or '@' not in user_email:
        return False, "A valid email address is required."
    if not purpose:
        return False, "Booking purpose/title is required."
    if not booking_date or not start_time or not end_time:
        return False, "Booking date, start time, and end time are required."

    try:
        attendees = int(attendees)
        if attendees <= 0:
            return False, "Number of attendees must be greater than zero."
    except (ValueError, TypeError):
        return False, "Number of attendees must be a valid positive number."

    # 2. Date and Time format validation
    try:
        b_date = datetime.strptime(booking_date, '%Y-%m-%d').date()
    except ValueError:
        return False, "Invalid date format. Expected YYYY-MM-DD."

    t_start = parse_time_str(start_time)
    t_end = parse_time_str(end_time)
    if not t_start or not t_end:
        return False, "Invalid time format. Expected HH:MM."

    if t_start >= t_end:
        return False, "Start time must be strictly before end time."

    # 3. Classroom existence and capacity verification
    room = get_classroom_by_id(classroom_id)
    if not room or not room.get('is_active', 1):
        return False, "Selected classroom is invalid or currently inactive."

    if attendees > room['capacity']:
        return False, f"Attendee count ({attendees}) exceeds classroom capacity ({room['capacity']}). Please select a larger room."

    # 4. Schedule conflict verification
    # Cannot book if already occupied by a class (unless cancelled), manual update, approved booking, or maintenance
    status_info = check_room_status_for_slot(classroom_id, booking_date, start_time, end_time)
    if status_info['status'] not in ['available', 'unconfirmed']:
        return False, f"Cannot submit booking: Classroom {room['room_number']} is {status_info['badge_label']} during this time ({status_info['conflict_reason']})."

    return True, None

def recommend_classrooms(booking_date, start_time, end_time, attendees, required_facilities=None, preferred_building=None):
    """
    Transparent Heuristic Recommendation Algorithm:
    Ranks classrooms matching the requested time slot, capacity, and facilities.
    
    Formula and Scoring Breakdown:
    - Base filtering: Must be available during slot and capacity >= attendees.
    - Capacity Optimization Score (0-45 pts):
        Calculates occupancy ratio (attendees / capacity).
        Ideal ratio is 65% - 95% (not wasting large halls, but roomy enough).
        - 70% to 100% capacity fit -> 45 points (Highly optimal)
        - 50% to 69% capacity fit  -> 35 points (Comfortable fit)
        - 30% to 49% capacity fit  -> 20 points (Slightly oversized)
        - < 30% capacity fit       -> 10 points (Large hall for small group)
    - Facility Match Score (0-40 pts):
        Percentage of required facilities satisfied * 40.
        Plus 2 bonus points per additional amenity.
    - Preferred Building Score (0-15 pts):
        +15 points if in user's preferred building.
    - Accessibility / Ground Floor Bonus (0-5 pts):
        +5 points for ground floor or wheelchair accessibility.
    """
    if required_facilities is None:
        required_facilities = []

    try:
        attendees = int(attendees)
    except (ValueError, TypeError):
        attendees = 1

    all_rooms = get_classrooms(include_inactive=False)
    recommendations = []

    for room in all_rooms:
        # Check capacity
        if room['capacity'] < attendees:
            continue

        # Check availability for the slot
        status_info = check_room_status_for_slot(room['id'], booking_date, start_time, end_time)
        if status_info['status'] not in ['available', 'unconfirmed']:
            continue

        # 1. Capacity Score
        ratio = attendees / float(room['capacity'])
        if 0.70 <= ratio <= 1.0:
            cap_score = 45
            cap_fit_text = f"Optimal capacity match: {attendees} attendees in a {room['capacity']}-seat room ({int(ratio*100)}% efficiency)."
        elif 0.50 <= ratio < 0.70:
            cap_score = 35
            cap_fit_text = f"Comfortable spacing: {attendees} attendees in a {room['capacity']}-seat room ({int(ratio*100)}% utilization)."
        elif 0.30 <= ratio < 0.50:
            cap_score = 20
            cap_fit_text = f"Spacious room: {attendees} attendees in a {room['capacity']}-seat room ({int(ratio*100)}% utilization)."
        else:
            cap_score = 10
            cap_fit_text = f"Significantly oversized: {attendees} attendees in a {room['capacity']}-seat hall."

        # 2. Facility Score
        room_facs = room.get('facilities_list', [])
        room_facs_lower = [f.lower().strip() for f in room_facs]

        if required_facilities:
            matched_reqs = [rf for rf in required_facilities if rf.lower().strip() in room_facs_lower]
            missing_reqs = [rf for rf in required_facilities if rf.lower().strip() not in room_facs_lower]
            facility_ratio = len(matched_reqs) / float(len(required_facilities))
            fac_score = int(facility_ratio * 40)
            
            # Bonus for extra amenities if all required are met
            if len(missing_reqs) == 0:
                bonus = min(len(room_facs) - len(matched_reqs), 3) * 2
                fac_score += bonus
                fac_fit_text = f"Matches 100% of required facilities ({', '.join(matched_reqs)})."
            else:
                fac_fit_text = f"Matches {len(matched_reqs)}/{len(required_facilities)} required facilities (Missing: {', '.join(missing_reqs)})."
        else:
            fac_score = 30
            fac_fit_text = f"Equipped with {len(room_facs)} amenities including {', '.join(room_facs[:3])}."

        # 3. Building Preference Score
        building_score = 0
        building_fit_text = f"Located in {room['building']} (Floor {room['floor']})."
        if preferred_building and preferred_building.strip():
            if room['building'].lower() == preferred_building.strip().lower():
                building_score = 15
                building_fit_text = f"Exact match for preferred building ({room['building']})."

        # 4. Accessibility Score
        acc_score = 0
        if room['floor'] == 1 or 'wheelchair accessible' in [f.lower() for f in room_facs]:
            acc_score = 5

        total_score = cap_score + fac_score + building_score + acc_score

        # Explanations list
        reasons = [
            cap_fit_text,
            fac_fit_text,
            building_fit_text,
            "100% free of class schedules, bookings, and maintenance during requested slot."
        ]
        if acc_score > 0:
            reasons.append("Convenient ground floor / wheelchair accessible accessibility.")

        recommendations.append({
            "classroom": room,
            "match_score": min(total_score, 100),
            "score_breakdown": {
                "capacity_score": cap_score,
                "facilities_score": fac_score,
                "building_score": building_score,
                "accessibility_score": acc_score,
                "total": min(total_score, 100)
            },
            "reasons": reasons
        })

    # Sort descending by match score, then ascending by capacity (closest fit first)
    recommendations.sort(key=lambda r: (-r['match_score'], r['classroom']['capacity']))

    return {
        "booking_date": booking_date,
        "start_time": start_time,
        "end_time": end_time,
        "attendees": attendees,
        "total_matches": len(recommendations),
        "recommendations": recommendations,
        "algorithm_notice": "Transparent multi-criteria heuristic scoring (Capacity efficiency + Facility matching + Building proximity). Not an opaque AI/ML black-box."
    }
