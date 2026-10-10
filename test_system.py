"""
SmartCampus Comprehensive Verification Test Suite
Validates:
1. Login and role-based authorization (Student, Staff, CR, Admin)
2. Student permission boundaries (cannot alter availability or approve)
3. CR permission boundaries (strictly restricted to assigned class)
4. Staff manual availability updates & conflict checks
5. Admin classroom and timetable management
6. Availability engine with 6 distinct status labels
7. Single-session cancellation (frees slot, preserves recurring timetable)
8. Approved bookings vs Pending bookings behavior
9. Maintenance window restrictions
10. Capacity and date/time input validations
11. Approval conflict re-validation in SQLite transaction
12. Transparent heuristic room recommendation scoring
"""

import unittest
import json
from datetime import date, timedelta
from app import app
from database import (
    init_db, seed_demo_data, get_classrooms, get_classroom_by_number,
    get_scheduled_classes, get_bookings, get_maintenance_blocks, get_db_connection
)

class SmartCampusTestSuite(unittest.TestCase):

    def setUp(self):
        """Configure test client and initialize fresh seed data."""
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        init_db()
        seed_demo_data(force=True)

    def login(self, username, password):
        """Helper to authenticate a test session."""
        return self.client.post('/api/auth/login', json={
            "username": username,
            "password": password
        })

    def logout(self):
        """Helper to clear test session."""
        return self.client.post('/api/auth/logout')

    # =========================================================================
    # 1. AUTHENTICATION & ROLE-BASED ACCESS CONTROL TESTS
    # =========================================================================

    def test_login_and_role_authorization(self):
        """Verify password hash verification, session setup, and logout."""
        # 1. Invalid password
        res = self.login("student1", "WrongPassword")
        self.assertEqual(res.status_code, 401)
        self.assertFalse(res.get_json()['success'])

        # 2. Valid Student login
        res = self.login("student1", "Password@123")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['role'], 'student')

        # 3. Check /api/auth/me
        res_me = self.client.get('/api/auth/me')
        self.assertEqual(res_me.status_code, 200)
        self.assertEqual(res_me.get_json()['user']['username'], 'student1')

        # 4. Logout
        res_logout = self.logout()
        self.assertEqual(res_logout.status_code, 200)
        res_me2 = self.client.get('/api/auth/me')
        self.assertFalse(res_me2.get_json()['authenticated'])

    def test_student_cannot_modify_room_status_or_approve(self):
        """Verify student is forbidden from calling admin/staff endpoints."""
        self.login("student1", "Password@123")

        # Student attempts to create classroom
        res_room = self.client.post('/api/classrooms', json={
            "room_number": "HACK-999", "building": "Secret", "capacity": 50
        })
        self.assertEqual(res_room.status_code, 403)

        # Student attempts to add staff manual update
        res_manual = self.client.post('/api/staff/manual-updates', json={
            "classroom_id": 1, "update_date": "2026-10-12", "start_time": "10:00",
            "end_time": "11:00", "reason": "Student takeover"
        })
        self.assertEqual(res_manual.status_code, 403)

        # Student attempts to approve a booking
        res_act = self.client.post('/api/bookings/1/action', json={"action": "Approved"})
        self.assertEqual(res_act.status_code, 403)

    def test_cr_cannot_modify_unassigned_class_schedule(self):
        """Verify Class Representative may ONLY report cancellations for their assigned class."""
        # cr_csea is assigned to 'III Year CSE A' (D309)
        self.login("cr_csea", "Password@123")

        # Find a class belonging to 'III Year CSE B' in D310
        classes_b = get_scheduled_classes(class_group="III Year CSE B")
        self.assertGreater(len(classes_b), 0)
        target_b_class = classes_b[0]

        # CR for CSE A attempts to cancel CSE B's class -> MUST BE FORBIDDEN (403)
        res_forbidden = self.client.post('/api/cancellations', json={
            "scheduled_class_id": target_b_class['id'],
            "cancellation_date": "2026-10-12",
            "reason": "Unauthorized attempt by other section CR"
        })
        self.assertEqual(res_forbidden.status_code, 403)
        self.assertIn("Permission Denied", res_forbidden.get_json()['error'])

        # CR for CSE A cancels their OWN assigned class (III Year CSE A) -> MUST SUCCEED (201)
        classes_a = get_scheduled_classes(class_group="III Year CSE A")
        self.assertGreater(len(classes_a), 0)
        target_a_class = classes_a[0]

        res_success = self.client.post('/api/cancellations', json={
            "scheduled_class_id": target_a_class['id'],
            "cancellation_date": "2026-10-12",
            "reason": "Faculty attending research conference"
        })
        self.assertEqual(res_success.status_code, 201)
        self.assertTrue(res_success.get_json()['success'])

    def test_staff_can_update_authorized_slot(self):
        """Verify Staff can record manual occupancy and that overlaps with approved bookings are blocked."""
        self.login("staff1", "Password@123")

        # CC2 on Monday evening (17:00 - 18:30) is free
        cc2 = get_classroom_by_number("CC2")
        self.assertIsNotNone(cc2)

        res_update = self.client.post('/api/staff/manual-updates', json={
            "classroom_id": cc2['id'],
            "update_date": "2026-10-12",
            "start_time": "17:00",
            "end_time": "18:30",
            "status_type": "Occupied — Manual Update",
            "reason": "Faculty extra lecture on Cryptography"
        })
        self.assertEqual(res_update.status_code, 201)
        self.assertTrue(res_update.get_json()['success'])

        # Verify availability query returns 'Occupied — Manual Update'
        res_avail = self.client.get('/api/availability?date=2026-10-12&start_time=17:15&end_time=18:00')
        data_avail = res_avail.get_json()
        rooms_by_num = {r['room_number']: r for r in data_avail['rooms']}
        self.assertEqual(rooms_by_num['CC2']['availability']['status'], 'manual_occupied')
        self.assertEqual(rooms_by_num['CC2']['availability']['badge_label'], 'Occupied — Manual Update')

        # Now attempt to record manual update on a slot with an approved booking (TECH-101 has approved booking today 17:00-19:30)
        today_str = date.today().strftime('%Y-%m-%d')
        tech = get_classroom_by_number("TECH-101")
        res_conflict = self.client.post('/api/staff/manual-updates', json={
            "classroom_id": tech['id'],
            "update_date": today_str,
            "start_time": "17:30",
            "end_time": "18:30",
            "reason": "Conflicting staff reservation"
        })
        self.assertEqual(res_conflict.status_code, 409)
        self.assertIn("conflicting", res_conflict.get_json()['error'].lower())

    def test_admin_can_manage_classrooms(self):
        """Verify Admin can add, update, and deactivate classrooms."""
        self.login("admin", "AdminPassword@123")

        # 1. Add classroom
        res_add = self.client.post('/api/classrooms', json={
            "room_number": "D401",
            "building": "Department Block D",
            "floor": 4,
            "capacity": 55,
            "room_type": "Seminar Hall",
            "facilities": "Projector, AC, Smart Board",
            "notes": "Newly built seminar room"
        })
        self.assertEqual(res_add.status_code, 201)
        new_id = res_add.get_json()['classroom_id']

        # 2. Update classroom
        res_upd = self.client.put(f'/api/classrooms/{new_id}', json={
            "room_number": "D401",
            "building": "Department Block D",
            "floor": 4,
            "capacity": 60,
            "room_type": "Smart Classroom",
            "facilities": "Projector, AC, Smart Board, Audio System",
            "is_active": 1
        })
        self.assertEqual(res_upd.status_code, 200)

        # 3. Soft delete / deactivate
        res_del = self.client.delete(f'/api/classrooms/{new_id}')
        self.assertEqual(res_del.status_code, 200)

        room_check = get_classroom_by_number("D401")
        self.assertEqual(room_check['is_active'], 0)

    # =========================================================================
    # 2. AVAILABILITY ENGINE & CANCELLATION TESTS
    # =========================================================================

    def test_availability_for_scheduled_classes(self):
        """Verify timetable classes report 'Occupied — Scheduled Class'."""
        # On Monday 09:00 - 09:55:
        # D309 has CS3501 Compiler Design (Session I)
        # D310 has CS3591 Computer Networks (Session I)
        res = self.client.get('/api/availability?date=2026-10-12&start_time=09:15&end_time=09:45')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        rooms_by_num = {r['room_number']: r for r in data['rooms']}

        d309 = rooms_by_num.get('D309')
        self.assertIsNotNone(d309)
        self.assertEqual(d309['availability']['status'], 'occupied')
        self.assertEqual(d309['availability']['badge_label'], 'Occupied — Scheduled Class')
        self.assertIn('CS3501', d309['availability']['conflict_reason'])

    def test_cancelled_session_availability_does_not_delete_timetable(self):
        """Verify cancelling a single session clears conflict on that date without altering recurring timetable."""
        # Find Monday Session I for D309
        classes = get_scheduled_classes(classroom_id=get_classroom_by_number("D309")['id'], day_of_week="Monday")
        session_1 = [c for c in classes if c['start_time'] == '09:00'][0]

        # Login as staff and cancel for specific date (2026-10-12)
        self.login("staff1", "Password@123")
        res_cancel = self.client.post('/api/cancellations', json={
            "scheduled_class_id": session_1['id'],
            "cancellation_date": "2026-10-12",
            "reason": "Instructor on medical leave"
        })
        self.assertEqual(res_cancel.status_code, 201)

        # Check availability on cancelled date -> D309 should now be Available!
        res_avail_cancelled = self.client.get('/api/availability?date=2026-10-12&start_time=09:15&end_time=09:45')
        rooms_cancelled = {r['room_number']: r for r in res_avail_cancelled.get_json()['rooms']}
        self.assertEqual(rooms_cancelled['D309']['availability']['status'], 'available')
        self.assertEqual(rooms_cancelled['D309']['availability']['badge_label'], 'Available According to Timetable')

        # Check availability on NEXT Monday (2026-10-19) -> Should STILL be Occupied!
        res_avail_next = self.client.get('/api/availability?date=2026-10-19&start_time=09:15&end_time=09:45')
        rooms_next = {r['room_number']: r for r in res_avail_next.get_json()['rooms']}
        self.assertEqual(rooms_next['D309']['availability']['status'], 'occupied')
        self.assertIn('CS3501', rooms_next['D309']['availability']['conflict_reason'])

    def test_pending_booking_does_not_reserve_room(self):
        """Verify pending bookings do not prematurely block room availability."""
        # Submit a pending booking for CC1
        cc1 = get_classroom_by_number("CC1")
        res_book = self.client.post('/api/bookings', json={
            "classroom_id": cc1['id'],
            "user_name": "Test Student",
            "user_email": "test@campus.edu",
            "purpose": "Study Session",
            "booking_date": "2026-10-16", # Friday evening
            "start_time": "17:00",
            "end_time": "18:00",
            "attendees": 15
        })
        self.assertEqual(res_book.status_code, 201)
        self.assertEqual(res_book.get_json()['status'], 'Pending')

        # Room availability check must still show Available (not reserved)
        res_avail = self.client.get('/api/availability?date=2026-10-16&start_time=17:00&end_time=18:00')
        rooms = {r['room_number']: r for r in res_avail.get_json()['rooms']}
        self.assertEqual(rooms['CC1']['availability']['status'], 'available')

    def test_approved_booking_conflicts(self):
        """Verify approving a booking creates 'Reserved' status and blocks conflicting submissions."""
        cc1 = get_classroom_by_number("CC1")
        res_book = self.client.post('/api/bookings', json={
            "classroom_id": cc1['id'],
            "user_name": "Dr. Watson",
            "user_email": "watson@campus.edu",
            "purpose": "Faculty Meeting",
            "booking_date": "2026-10-16",
            "start_time": "17:00",
            "end_time": "18:00",
            "attendees": 15
        })
        booking_id = res_book.get_json()['booking_id']

        # Staff approves the booking
        self.login("staff1", "Password@123")
        res_appr = self.client.post(f'/api/bookings/{booking_id}/action', json={
            "action": "Approved", "admin_notes": "Official meeting approved."
        })
        self.assertEqual(res_appr.status_code, 200)

        # Room status is now 'Reserved'
        res_avail = self.client.get('/api/availability?date=2026-10-16&start_time=17:15&end_time=17:45')
        rooms = {r['room_number']: r for r in res_avail.get_json()['rooms']}
        self.assertEqual(rooms['CC1']['availability']['status'], 'reserved')
        self.assertEqual(rooms['CC1']['availability']['badge_label'], 'Reserved')

        # Submitting another booking for the same slot must fail
        res_conflict = self.client.post('/api/bookings', json={
            "classroom_id": cc1['id'],
            "user_name": "Second Requester",
            "user_email": "sec@campus.edu",
            "purpose": "Conflicting event",
            "booking_date": "2026-10-16",
            "start_time": "17:30",
            "end_time": "18:30",
            "attendees": 10
        })
        self.assertEqual(res_conflict.status_code, 400)
        self.assertIn("Reserved", res_conflict.get_json()['error'])

    def test_maintenance_restrictions(self):
        """Verify rooms under maintenance return 'Unavailable — Maintenance' and reject bookings."""
        # CC3 has seeded maintenance today 08:00 to 12:00
        today_str = date.today().strftime('%Y-%m-%d')
        res_avail = self.client.get(f'/api/availability?date={today_str}&start_time=09:00&end_time=11:00')
        rooms = {r['room_number']: r for r in res_avail.get_json()['rooms']}
        self.assertEqual(rooms['CC3']['availability']['status'], 'maintenance')
        self.assertEqual(rooms['CC3']['availability']['badge_label'], 'Unavailable — Maintenance')

        # Attempt to book CC3 during maintenance must fail
        cc3 = get_classroom_by_number("CC3")
        res_book = self.client.post('/api/bookings', json={
            "classroom_id": cc3['id'],
            "user_name": "Student A",
            "user_email": "a@campus.edu",
            "purpose": "Lab practice",
            "booking_date": today_str,
            "start_time": "09:30",
            "end_time": "10:30",
            "attendees": 15
        })
        self.assertEqual(res_book.status_code, 400)
        self.assertIn("Maintenance", res_book.get_json()['error'])

    # =========================================================================
    # 3. INPUT VALIDATIONS & RECOMMENDATION ENGINE TESTS
    # =========================================================================

    def test_capacity_validation(self):
        """Ensure booking fails when attendee count exceeds room capacity."""
        # D309 has capacity 65
        d309 = get_classroom_by_number("D309")
        res = self.client.post('/api/bookings', json={
            "classroom_id": d309['id'],
            "user_name": "Event Organizer",
            "user_email": "org@campus.edu",
            "purpose": "Megaconference",
            "booking_date": "2026-10-18",
            "start_time": "10:00",
            "end_time": "12:00",
            "attendees": 200 # Exceeds 65
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("exceeds classroom capacity", res.get_json()['error'])

    def test_invalid_date_time_validation(self):
        """Ensure booking fails when start_time >= end_time or attendees <= 0."""
        d309 = get_classroom_by_number("D309")
        
        # Start time after end time
        res1 = self.client.post('/api/bookings', json={
            "classroom_id": d309['id'],
            "user_name": "User", "user_email": "u@campus.edu",
            "purpose": "Test", "booking_date": "2026-10-18",
            "start_time": "14:00", "end_time": "12:00", "attendees": 20
        })
        self.assertEqual(res1.status_code, 400)

        # Zero attendees
        res2 = self.client.post('/api/bookings', json={
            "classroom_id": d309['id'],
            "user_name": "User", "user_email": "u@campus.edu",
            "purpose": "Test", "booking_date": "2026-10-18",
            "start_time": "10:00", "end_time": "12:00", "attendees": 0
        })
        self.assertEqual(res2.status_code, 400)

    def test_smart_room_recommendation(self):
        """Verify transparent heuristic ranking scores rooms by capacity fit, facilities, and preferences."""
        payload = {
            "date": "2026-10-18", # Sunday (all rooms free of recurring classes)
            "start_time": "10:00",
            "end_time": "12:00",
            "attendees": 50,
            "required_facilities": ["Projector", "Air Conditioning"],
            "preferred_building": "Department Block D"
        }
        res = self.client.post('/api/recommend', json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(data['total_matches'], 0)

        # Scores should be sorted descending
        scores = [r['match_score'] for r in data['recommendations']]
        self.assertEqual(scores, sorted(scores, reverse=True))

        top_rec = data['recommendations'][0]
        self.assertIn('reasons', top_rec)
        self.assertGreater(len(top_rec['reasons']), 0)
        self.assertGreaterEqual(top_rec['classroom']['capacity'], 50)

    def test_concurrent_approval_conflict_prevention(self):
        """Verify transaction safety: second approval on overlapping slot is rejected with 409."""
        cc1 = get_classroom_by_number("CC1")
        # Submit booking 1
        res1 = self.client.post('/api/bookings', json={
            "classroom_id": cc1['id'],
            "user_name": "Applicant 1",
            "user_email": "app1@campus.edu",
            "purpose": "AI Study Group",
            "booking_date": "2026-10-18",
            "start_time": "14:00",
            "end_time": "16:00",
            "attendees": 20
        })
        self.assertEqual(res1.status_code, 201)
        b1_id = res1.get_json()['booking_id']

        # Submit booking 2 (overlapping slot)
        res2 = self.client.post('/api/bookings', json={
            "classroom_id": cc1['id'],
            "user_name": "Applicant 2",
            "user_email": "app2@campus.edu",
            "purpose": "Web Dev Workshop",
            "booking_date": "2026-10-18",
            "start_time": "15:00",
            "end_time": "17:00",
            "attendees": 20
        })
        self.assertEqual(res2.status_code, 201)
        b2_id = res2.get_json()['booking_id']

        # Staff approves Booking 1 -> Succeeds (200)
        self.login("staff1", "Password@123")
        res_app1 = self.client.post(f'/api/bookings/{b1_id}/action', json={"action": "Approved"})
        self.assertEqual(res_app1.status_code, 200)

        # Staff attempts to approve Booking 2 -> Must be rejected with 409 Conflict
        res_app2 = self.client.post(f'/api/bookings/{b2_id}/action', json={"action": "Approved"})
        self.assertEqual(res_app2.status_code, 409)
        self.assertIn("conflicting", res_app2.get_json()['error'].lower())

if __name__ == '__main__':
    unittest.main()
