/**
 * SmartCampus - Intelligent Classroom Availability & Booking System
 * Dynamic Frontend Application Controller & Role Dashboards
 */

// Global Application State
const state = {
  currentUser: null,
  currentTab: 'dashboard',
  selectedFacilities: new Set(),
  recSelectedFacilities: new Set(),
  classroomsCache: [],
  scheduledClassesCache: [],
  debounceTimer: null,
  activeBookingFilter: 'All'
};

// ============================================================
// INITIALIZATION
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
  initDefaultSlotValues();
  await checkAuthStatus();
  await loadClassroomDropdowns();
  loadAvailability();
});

function initDefaultSlotValues() {
  const now = new Date();
  const todayStr = now.toISOString().split('T')[0];

  const slotDateInput = document.getElementById('slot-date');
  const recDateInput = document.getElementById('rec-date');
  const directDateInput = document.getElementById('direct-date');
  const modalDateInput = document.getElementById('modal-date');
  const manualDateInput = document.getElementById('manual-date');
  const cancelDateInput = document.getElementById('cancel-date');
  const crCancelDate = document.getElementById('cr-cancel-date');
  const crBookDate = document.getElementById('cr-book-date');
  const maintStartDate = document.getElementById('maint-start-date');
  const maintEndDate = document.getElementById('maint-end-date');

  [slotDateInput, recDateInput, directDateInput, modalDateInput, manualDateInput, cancelDateInput, crCancelDate, crBookDate, maintStartDate, maintEndDate].forEach(input => {
    if (input && !input.value) input.value = todayStr;
  });

  const curHour = String(now.getHours()).padStart(2, '0');
  const nextHour = String((now.getHours() + 1) % 24).padStart(2, '0');
  const slotStart = document.getElementById('slot-start-time');
  const slotEnd = document.getElementById('slot-end-time');

  if (slotStart && !slotStart.value) slotStart.value = `${curHour}:00`;
  if (slotEnd && !slotEnd.value) slotEnd.value = `${nextHour}:00`;
}

function resetSlotToNow() {
  initDefaultSlotValues();
  loadAvailability();
  showToast('Reset to current date and time slot.', 'info');
}

// ============================================================
// AUTHENTICATION & DEMO ROLE SWITCHER
// ============================================================

async function checkAuthStatus() {
  try {
    const res = await fetch('/api/auth/me');
    const data = await res.json();
    if (data.success && data.authenticated) {
      state.currentUser = data.user;
    } else {
      // Auto-login as demo student by default for instant interactivity
      await quickLoginUser('student1', 'Password@123', false);
      return;
    }
  } catch (err) {
    console.error('Auth check error:', err);
  }
  updateAuthUI();
}

function updateAuthUI() {
  const pill = document.getElementById('user-info-pill');
  const authBtn = document.getElementById('auth-btn');
  const select = document.getElementById('quick-role-select');

  // Nav buttons
  const navStaff = document.getElementById('nav-btn-staff');
  const navCR = document.getElementById('nav-btn-cr');
  const navAdmin = document.getElementById('nav-btn-admin');

  if (state.currentUser) {
    const role = state.currentUser.role;
    pill.className = `user-role-badge role-${role}`;
    pill.textContent = `👤 ${state.currentUser.full_name} (${role.toUpperCase()}${state.currentUser.assigned_class ? ': ' + state.currentUser.assigned_class : ''})`;
    authBtn.textContent = 'Logout';
    authBtn.className = 'btn btn-secondary btn-sm';
    if (select) select.value = state.currentUser.username;

    // Adjust Nav Visibility per Role
    if (navStaff) navStaff.style.display = (role === 'staff' || role === 'admin') ? 'inline-flex' : 'none';
    if (navCR) navCR.style.display = (role === 'cr' || role === 'admin') ? 'inline-flex' : 'none';
    if (navAdmin) navAdmin.style.display = (role === 'admin') ? 'inline-flex' : 'none';

    // Auto fill booking user info
    const directName = document.getElementById('direct-user-name');
    const directEmail = document.getElementById('direct-user-email');
    const directRole = document.getElementById('direct-user-role');
    if (directName) directName.value = state.currentUser.full_name;
    if (directEmail) directEmail.value = state.currentUser.email;
    if (directRole) {
      if (role === 'cr') directRole.value = 'CR';
      else if (role === 'staff') directRole.value = 'Staff';
      else directRole.value = 'Student';
    }
  } else {
    pill.className = 'user-role-badge';
    pill.textContent = '👤 Guest (Unauthenticated)';
    authBtn.textContent = 'Sign In';
    if (navStaff) navStaff.style.display = 'none';
    if (navCR) navCR.style.display = 'none';
    if (navAdmin) navAdmin.style.display = 'none';
  }
}

async function quickSwitchUser(username) {
  const passwords = {
    'student1': 'Password@123',
    'staff1': 'Password@123',
    'cr_csea': 'Password@123',
    'cr_cseb': 'Password@123',
    'admin': 'AdminPassword@123'
  };
  await quickLoginUser(username, passwords[username] || 'Password@123', true);
}

async function quickLoginUser(username, password, notify = true) {
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (data.success) {
      state.currentUser = data.user;
      updateAuthUI();
      if (notify) showToast(`Logged in as ${data.user.full_name} (${data.user.role.toUpperCase()})`, 'success');

      // Auto-switch to relevant dashboard for seamless experience
      if (data.user.role === 'staff') switchTab('staff');
      else if (data.user.role === 'cr') switchTab('cr');
      else if (data.user.role === 'admin') switchTab('admin');
      else switchTab('dashboard');
    } else {
      if (notify) showToast(data.error || 'Login failed', 'error');
    }
  } catch (err) {
    if (notify) showToast('Network error during authentication.', 'error');
  }
}

function handleAuthButtonClick() {
  if (state.currentUser) {
    handleLogout();
  } else {
    openLoginModal();
  }
}

async function handleLogout() {
  try {
    await fetch('/api/auth/logout', { method: 'POST' });
    state.currentUser = null;
    updateAuthUI();
    showToast('Logged out successfully.', 'info');
    switchTab('dashboard');
  } catch (err) {
    showToast('Logout error', 'error');
  }
}

function openLoginModal() {
  document.getElementById('modal-login').classList.add('active');
}

function closeLoginModal() {
  document.getElementById('modal-login').classList.remove('active');
}

async function handleManualLogin(e) {
  e.preventDefault();
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;
  await quickLoginUser(username, password, true);
  closeLoginModal();
}

// ============================================================
// TAB NAVIGATION
// ============================================================

function switchTab(tabId) {
  state.currentTab = tabId;

  // Update nav links
  document.querySelectorAll('.header-nav .nav-link').forEach(btn => {
    btn.classList.toggle('active', btn.id === `nav-btn-${tabId}`);
  });

  // Update tab panes
  document.querySelectorAll('.tab-pane').forEach(pane => {
    pane.classList.toggle('active', pane.id === `tab-${tabId}`);
  });

  // Tab-specific data loading
  if (tabId === 'dashboard') {
    loadAvailability();
  } else if (tabId === 'track') {
    loadBookingsTracker();
  } else if (tabId === 'staff') {
    loadStaffDashboard();
  } else if (tabId === 'cr') {
    loadCRDashboard();
  } else if (tabId === 'admin') {
    loadAdminPortal();
  }
}

// ============================================================
// FACILITY FILTER TOGGLE
// ============================================================

function toggleFacilityFilter(facilityName, element) {
  if (state.selectedFacilities.has(facilityName)) {
    state.selectedFacilities.delete(facilityName);
    element.classList.remove('active');
  } else {
    state.selectedFacilities.add(facilityName);
    element.classList.add('active');
  }
  loadAvailability();
}

function toggleRecFacility(facilityName, element) {
  if (state.recSelectedFacilities.has(facilityName)) {
    state.recSelectedFacilities.delete(facilityName);
    element.classList.remove('active');
  } else {
    state.recSelectedFacilities.add(facilityName);
    element.classList.add('active');
  }
}

function debounceAvailability() {
  clearTimeout(state.debounceTimer);
  state.debounceTimer = setTimeout(() => {
    loadAvailability();
  }, 250);
}

// ============================================================
// CLASSROOMS DROPDOWNS & CACHE
// ============================================================

async function loadClassroomDropdowns() {
  try {
    const res = await fetch('/api/classrooms');
    const data = await res.json();
    if (data.success) {
      state.classroomsCache = data.classrooms;

      // Populate direct booking select
      const directSelect = document.getElementById('direct-classroom-select');
      const manualSelect = document.getElementById('manual-room-select');
      const maintSelect = document.getElementById('maint-room-select');
      const crBookSelect = document.getElementById('cr-book-room-select');

      const optionsHtml = '<option value="" disabled selected>-- Select Classroom / Lab --</option>' +
        data.classrooms.map(c => `<option value="${c.id}">${c.room_number} — ${c.building} (Cap: ${c.capacity}, ${c.room_type})</option>`).join('');

      if (directSelect) directSelect.innerHTML = optionsHtml;
      if (manualSelect) manualSelect.innerHTML = optionsHtml;
      if (maintSelect) maintSelect.innerHTML = optionsHtml;
      if (crBookSelect) crBookSelect.innerHTML = optionsHtml;
    }
  } catch (err) {
    console.error('Failed to load classrooms:', err);
  }
}

function handleDirectRoomChange() {
  const select = document.getElementById('direct-classroom-select');
  const hint = document.getElementById('direct-room-capacity-hint');
  const room = state.classroomsCache.find(r => String(r.id) === select.value);
  if (room && hint) {
    hint.textContent = `Maximum Seating Capacity: ${room.capacity} seats (${room.room_type} in ${room.building}, Floor ${room.floor})`;
  }
}

// ============================================================
// STUDENT DASHBOARD: AVAILABILITY ENGINE
// ============================================================

async function loadAvailability() {
  const container = document.getElementById('classroom-cards-container');
  if (!container) return;

  const dateVal = document.getElementById('slot-date').value;
  const startVal = document.getElementById('slot-start-time').value;
  const endVal = document.getElementById('slot-end-time').value;
  const buildingVal = document.getElementById('filter-building').value;
  const minCapVal = document.getElementById('filter-min-cap').value;
  const searchVal = document.getElementById('search-rooms').value.trim();
  const facilitiesArr = Array.from(state.selectedFacilities);

  const queryParams = new URLSearchParams({
    date: dateVal,
    start_time: startVal,
    end_time: endVal,
    building: buildingVal,
    search: searchVal
  });
  if (minCapVal) queryParams.append('min_capacity', minCapVal);
  if (facilitiesArr.length) queryParams.append('facilities', facilitiesArr.join(','));

  // Update banner text
  const bannerText = document.getElementById('slot-banner-text');
  if (bannerText) {
    bannerText.innerHTML = `Slot: <strong>${dateVal}</strong> from <strong>${startVal}</strong> to <strong>${endVal}</strong>`;
  }

  try {
    const res = await fetch(`/api/availability?${queryParams.toString()}`);
    const data = await res.json();

    if (!data.success) {
      showToast(data.error || 'Failed to load availability', 'error');
      return;
    }

    // Update Counter Stat Badges
    const c = data.counts;
    document.getElementById('stat-total-rooms').textContent = c.total;
    document.getElementById('stat-available-rooms').textContent = c.available;
    document.getElementById('stat-occupied-rooms').textContent = c.occupied + (c.manual_occupied || 0);
    document.getElementById('stat-reserved-rooms').textContent = c.reserved;
    document.getElementById('stat-maintenance-rooms').textContent = c.maintenance;

    const countText = document.getElementById('match-count-text');
    if (countText) countText.textContent = `Showing ${data.rooms.length} rooms`;

    renderClassroomCards(data.rooms);
  } catch (err) {
    console.error('Availability fetch error:', err);
  }
}

function renderClassroomCards(rooms) {
  const container = document.getElementById('classroom-cards-container');
  if (!rooms.length) {
    container.innerHTML = `
      <div class="empty-state" style="grid-column: 1 / -1;">
        <div class="empty-icon">🔍</div>
        <h3>No Classrooms Found</h3>
        <p>No classrooms match the selected filters or search query for this slot.</p>
      </div>`;
    return;
  }

  container.innerHTML = rooms.map(room => {
    const avail = room.availability;
    let statusClass = avail.status;
    let badgeClass = `status-badge ${avail.status}`;

    let conflictInfoHtml = '';
    if (avail.status === 'occupied' && avail.conflict_details) {
      conflictInfoHtml = `
        <div class="conflict-alert" style="background:#FEF3C7; color:#92400E; border: 1px solid #FDE68A;">
          <strong>📚 ${avail.conflict_details.course_code}: ${avail.conflict_details.course_name}</strong>
          <div style="margin-top:2px; font-size: 0.72rem;">Instructor: ${avail.conflict_details.instructor} (${avail.conflict_details.window})</div>
          ${avail.conflict_details.session_name ? `<div style="font-size:0.7rem; color:#B45309;">${avail.conflict_details.session_name} • ${avail.conflict_details.class_group}</div>` : ''}
        </div>`;
    } else if (avail.status === 'manual_occupied' && avail.conflict_details) {
      conflictInfoHtml = `
        <div class="conflict-alert" style="background:#FFF7ED; color:#C2410C; border: 1px solid #FDBA74;">
          <strong>📌 Staff Update: ${avail.conflict_details.reason}</strong>
          <div style="margin-top:2px; font-size: 0.72rem;">Window: ${avail.conflict_details.window} (Recorded by: ${avail.conflict_details.user_name || 'Staff'})</div>
        </div>`;
    } else if (avail.status === 'reserved' && avail.conflict_details) {
      conflictInfoHtml = `
        <div class="conflict-alert" style="background:#EFF6FF; color:#1E40AF; border: 1px solid #BFDBFE;">
          <strong>📌 Reservation: ${avail.conflict_details.purpose}</strong>
          <div style="margin-top:2px; font-size: 0.72rem;">Booked by: ${avail.conflict_details.user_role} (${avail.conflict_details.window})</div>
        </div>`;
    } else if (avail.status === 'maintenance' && avail.conflict_details) {
      conflictInfoHtml = `
        <div class="conflict-alert" style="background:#FFF1F2; color:#9F1239; border: 1px solid #FECDD3;">
          <strong>🔧 Maintenance: ${avail.conflict_details.reason}</strong>
          <div style="margin-top:2px; font-size: 0.72rem;">Window: ${avail.conflict_details.window}</div>
        </div>`;
    } else if (avail.status === 'unconfirmed') {
      conflictInfoHtml = `
        <div class="conflict-alert" style="background:#F1F5F9; color:#475569; border: 1px solid #CBD5E1;">
          <strong>⚠️ Outside Standard Academic Hours</strong>
          <div style="margin-top:2px; font-size: 0.72rem;">Physical occupancy unconfirmed.</div>
        </div>`;
    }

    const facilitiesHtml = (room.facilities_list || []).map(f => `<span class="room-tag">${f}</span>`).join('');

    return `
      <div class="room-card status-${statusClass}">
        <div>
          <div class="card-header-row">
            <div class="room-number-group">
              <h3>${room.room_number}</h3>
              <div class="room-location">
                <span>🏢</span> ${room.building} (Floor ${room.floor})
              </div>
            </div>
            <span class="${badgeClass}">
              <span class="dot"></span>
              ${avail.badge_label}
            </span>
          </div>

          <div class="room-metrics">
            <div class="metric-pill">
              <span>👥</span> <strong>${room.capacity}</strong> seats
            </div>
            <div class="metric-pill">
              <span>🏷️</span> ${room.room_type}
            </div>
            ${room.notes ? `<div class="metric-pill" style="color:var(--cyan-dark); font-size:0.72rem;">${room.notes}</div>` : ''}
          </div>

          <div class="room-tags">
            ${facilitiesHtml}
          </div>

          ${conflictInfoHtml}
        </div>

        <div class="card-actions">
          <button class="btn btn-secondary btn-sm" onclick="openRoomDetailModal(${room.id})">
            📅 View Schedule
          </button>
          ${avail.status === 'available' || avail.status === 'unconfirmed'
            ? `<button class="btn btn-primary btn-sm" onclick="prefillAndOpenBooking(${room.id}, '${room.room_number}')">+ Book Slot</button>`
            : `<button class="btn btn-secondary btn-sm" disabled style="opacity:0.55; cursor:not-allowed;">Slot Unavailable</button>`
          }
        </div>
      </div>
    `;
  }).join('');
}

// ============================================================
// ROOM DETAIL & TIMETABLE MODAL
// ============================================================

async function openRoomDetailModal(roomId) {
  try {
    const res = await fetch(`/api/classrooms/${roomId}`);
    const data = await res.json();
    if (!data.success) {
      showToast(data.error || 'Failed to load details', 'error');
      return;
    }

    const room = data.classroom;
    document.getElementById('detail-modal-title').textContent = `${room.room_number} — ${room.building} Details`;
    
    document.getElementById('detail-modal-summary').innerHTML = `
      <div style="background: #F8FAFC; border: 1px solid var(--border-subtle); border-radius: 8px; padding: 0.75rem 1rem; display: flex; gap: 1.5rem; flex-wrap: wrap;">
        <div><strong>Type:</strong> ${room.room_type}</div>
        <div><strong>Floor:</strong> ${room.floor}</div>
        <div><strong>Capacity:</strong> ${room.capacity} seats</div>
        <div><strong>Facilities:</strong> ${room.facilities}</div>
        ${room.notes ? `<div style="color:var(--cyan-dark);"><strong>Notice:</strong> ${room.notes}</div>` : ''}
      </div>`;

    // Scheduled classes
    const classesTbody = document.getElementById('detail-classes-tbody');
    if (!data.classes.length) {
      classesTbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No recurring classes scheduled for this classroom.</td></tr>`;
    } else {
      classesTbody.innerHTML = data.classes.map(c => `
        <tr>
          <td><strong>${c.day_of_week}</strong></td>
          <td><span class="system-badge">${c.session_name || 'Session'}</span></td>
          <td>${c.start_time} - ${c.end_time}</td>
          <td><strong>${c.course_code}</strong>: ${c.course_name}</td>
          <td><span style="color:var(--cyan-dark); font-weight:600;">${c.class_group || 'General'}</span></td>
          <td>${c.instructor}</td>
        </tr>
      `).join('');
    }

    // Bookings
    const bookingsTbody = document.getElementById('detail-bookings-tbody');
    if (!data.bookings.length) {
      bookingsTbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color: var(--text-muted);">No approved bookings registered for this classroom yet.</td></tr>`;
    } else {
      bookingsTbody.innerHTML = data.bookings.map(b => `
        <tr>
          <td><code>${b.booking_code}</code></td>
          <td>${b.booking_date}</td>
          <td>${b.start_time} - ${b.end_time}</td>
          <td>${b.purpose}</td>
          <td>${b.user_name} (${b.user_role})</td>
        </tr>
      `).join('');
    }

    document.getElementById('modal-room-detail').classList.add('active');
  } catch (err) {
    showToast('Failed to load room timetable details', 'error');
  }
}

function closeRoomDetailModal() {
  document.getElementById('modal-room-detail').classList.remove('active');
}

// ============================================================
// BOOKING SUBMISSIONS (Direct Form & Card Quick Modal)
// ============================================================

function prefillAndOpenBooking(roomId, roomNumber) {
  const modal = document.getElementById('modal-booking');
  document.getElementById('modal-classroom-id').value = roomId;
  document.getElementById('booking-modal-title').textContent = `Book Classroom ${roomNumber}`;

  // Copy values from active slot explorer
  document.getElementById('modal-date').value = document.getElementById('slot-date').value;
  document.getElementById('modal-start-time').value = document.getElementById('slot-start-time').value;
  document.getElementById('modal-end-time').value = document.getElementById('slot-end-time').value;

  if (state.currentUser) {
    document.getElementById('modal-user-name').value = state.currentUser.full_name;
    document.getElementById('modal-user-email').value = state.currentUser.email;
    document.getElementById('modal-user-role').value = state.currentUser.role.toUpperCase() === 'CR' ? 'CR' : (state.currentUser.role.toUpperCase() === 'STAFF' ? 'Staff' : 'Student');
  }

  modal.classList.add('active');
}

function openBookingModal() {
  switchTab('book');
}

function closeBookingModal() {
  document.getElementById('modal-booking').classList.remove('active');
}

async function handleModalBookingSubmit(e) {
  e.preventDefault();
  const payload = {
    classroom_id: document.getElementById('modal-classroom-id').value,
    user_name: document.getElementById('modal-user-name').value.trim(),
    user_email: document.getElementById('modal-user-email').value.trim(),
    user_role: document.getElementById('modal-user-role').value,
    purpose: document.getElementById('modal-purpose').value.trim(),
    booking_date: document.getElementById('modal-date').value,
    start_time: document.getElementById('modal-start-time').value,
    end_time: document.getElementById('modal-end-time').value,
    attendees: parseInt(document.getElementById('modal-attendees').value, 10)
  };

  await executeBookingSubmission(payload);
  closeBookingModal();
}

async function handleDirectBookingSubmit(e) {
  e.preventDefault();
  const payload = {
    classroom_id: document.getElementById('direct-classroom-select').value,
    user_name: document.getElementById('direct-user-name').value.trim(),
    user_email: document.getElementById('direct-user-email').value.trim(),
    user_role: document.getElementById('direct-user-role').value,
    purpose: document.getElementById('direct-purpose').value.trim(),
    booking_date: document.getElementById('direct-date').value,
    start_time: document.getElementById('direct-start-time').value,
    end_time: document.getElementById('direct-end-time').value,
    attendees: parseInt(document.getElementById('direct-attendees').value, 10)
  };

  await executeBookingSubmission(payload);
}

async function executeBookingSubmission(payload) {
  try {
    const res = await fetch('/api/bookings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Booking submitted! Tracking Code: ${data.booking_code}`, 'success');
      switchTab('track');
    } else {
      showToast(data.error || 'Failed to submit booking', 'error');
    }
  } catch (err) {
    showToast('Network error submitting booking', 'error');
  }
}

// ============================================================
// SMART ROOM RECOMMENDATION (Heuristic Ranking)
// ============================================================

async function handleRecommendationSubmit(e) {
  e.preventDefault();
  const resultsArea = document.getElementById('recommend-results-area');
  resultsArea.innerHTML = `
    <div style="text-align:center; padding: 2rem;">
      <p style="color: var(--text-muted);">Calculating capacity efficiency and facility coverage...</p>
    </div>`;

  const payload = {
    date: document.getElementById('rec-date').value,
    start_time: document.getElementById('rec-start-time').value,
    end_time: document.getElementById('rec-end-time').value,
    attendees: parseInt(document.getElementById('rec-attendees').value, 10),
    preferred_building: document.getElementById('rec-building').value,
    required_facilities: Array.from(state.recSelectedFacilities)
  };

  try {
    const res = await fetch('/api/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!data.success) {
      showToast(data.error || 'Recommendation failed', 'error');
      return;
    }

    renderRecommendations(data);
  } catch (err) {
    showToast('Failed to calculate recommendations', 'error');
  }
}

function renderRecommendations(data) {
  const area = document.getElementById('recommend-results-area');
  const recs = data.recommendations;

  if (!recs.length) {
    area.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon">⚠️</div>
        <h3>No Suitable Classrooms Found</h3>
        <p>No available rooms meet your attendee count (${data.attendees}) and required facilities during this slot.</p>
      </div>`;
    return;
  }

  area.innerHTML = `
    <div style="margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: center;">
      <h3 style="font-size: 1.15rem; color: var(--navy-dark); font-weight: 700;">
        Ranked Match Results (${recs.length} Suitable Rooms)
      </h3>
      <span class="system-badge">${data.algorithm_notice}</span>
    </div>
    ` + recs.map((rec, idx) => {
      const room = rec.classroom;
      const bd = rec.score_breakdown;
      const isTop = idx === 0;

      return `
        <div class="recommend-card ${isTop ? 'top-match' : ''}">
          <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
              <span class="system-badge" style="background:#E0F2FE; color:#0369A1; font-weight:700;">Rank #${idx + 1}</span>
              <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--navy-dark); margin-top: 4px;">${room.room_number} — ${room.building}</h3>
              <span style="font-size: 0.82rem; color: var(--text-muted);">${room.room_type} (Floor ${room.floor}) • Capacity: ${room.capacity} seats</span>
            </div>
            <div style="text-align: right;">
              <span class="match-badge">${rec.match_score}% Match</span>
            </div>
          </div>

          <div class="score-breakdown">
            <span class="score-pill">Capacity Fit: ${bd.capacity_score}/45 pts</span>
            <span class="score-pill">Facilities Match: ${bd.facilities_score}/40 pts</span>
            ${bd.building_score > 0 ? `<span class="score-pill" style="background:#DCFCE7; color:#15803D;">Preferred Building: +${bd.building_score} pts</span>` : ''}
            ${bd.accessibility_score > 0 ? `<span class="score-pill" style="background:#E0F2FE; color:#0369A1;">Accessibility: +${bd.accessibility_score} pts</span>` : ''}
          </div>

          <div class="recommend-reasons">
            <h4>Transparent Recommendation Rationale:</h4>
            <ul>
              ${rec.reasons.map(r => `<li>${r}</li>`).join('')}
            </ul>
          </div>

          <div style="margin-top: 0.85rem; display: flex; gap: 0.5rem;">
            <button class="btn btn-primary btn-sm" onclick="prefillAndOpenBooking(${room.id}, '${room.room_number}')">
              Book This Recommended Room
            </button>
            <button class="btn btn-secondary btn-sm" onclick="openRoomDetailModal(${room.id})">
              View Schedule
            </button>
          </div>
        </div>
      `;
    }).join('');
}

// ============================================================
// TRACK REQUESTS & MY BOOKINGS
// ============================================================

async function loadBookingsTracker() {
  const tbody = document.getElementById('bookings-tracker-tbody');
  const searchVal = document.getElementById('track-search-input').value.trim();

  const params = new URLSearchParams({
    status: state.activeBookingFilter,
    search: searchVal
  });

  try {
    const res = await fetch(`/api/bookings?${params.toString()}`);
    const data = await res.json();
    if (!data.success) return;

    const bks = data.bookings;
    if (!bks.length) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 2rem; color: var(--text-muted);">No booking requests found for this filter.</td></tr>`;
      return;
    }

    tbody.innerHTML = bks.map(b => {
      let statusBadge = `<span class="status-badge ${b.status.toLowerCase()}">${b.status}</span>`;
      if (b.status === 'Approved') statusBadge = `<span class="status-badge available">✅ Approved</span>`;
      else if (b.status === 'Pending') statusBadge = `<span class="status-badge occupied">⏳ Pending</span>`;
      else if (b.status === 'Rejected') statusBadge = `<span class="status-badge maintenance">❌ Rejected</span>`;

      return `
        <tr>
          <td><strong style="color: var(--cyan-dark);">${b.booking_code}</strong></td>
          <td><strong>${b.room_number}</strong><br><small style="color:var(--text-muted);">${b.building}</small></td>
          <td>${b.user_name}<br><small style="color:var(--text-muted);">${b.user_role} • ${b.user_email}</small></td>
          <td>${b.purpose}</td>
          <td>${b.booking_date}<br><small style="color:var(--text-muted);">${b.start_time} - ${b.end_time}</small></td>
          <td>${b.attendees}</td>
          <td>${statusBadge}</td>
          <td><small style="color: #475569;">${b.rejection_reason || b.admin_notes || '-'}</small></td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Track bookings error:', err);
  }
}

function filterBookingTable(status) {
  state.activeBookingFilter = status;
  ['all', 'pending', 'approved', 'rejected'].forEach(s => {
    const btn = document.getElementById(`btn-filter-${s}`);
    if (btn) btn.className = (s === status.toLowerCase() ? 'btn btn-navy btn-sm' : 'btn btn-secondary btn-sm');
  });
  loadBookingsTracker();
}

function debounceBookingTracker() {
  clearTimeout(state.debounceTimer);
  state.debounceTimer = setTimeout(() => {
    loadBookingsTracker();
  }, 250);
}

// ============================================================
// STAFF DASHBOARD
// ============================================================

async function loadStaffDashboard() {
  loadClassroomDropdowns();
  loadStaffApprovalsQueue();
  loadStaffLogs();
  loadClassesForStaffCancel();
}

async function loadStaffApprovalsQueue() {
  const tbody = document.getElementById('staff-approvals-tbody');
  try {
    const res = await fetch('/api/bookings?status=Pending');
    const data = await res.json();
    if (!data.success) return;

    const pends = data.bookings;
    const badge = document.getElementById('staff-pending-count');
    if (badge) badge.textContent = `${pends.length} Pending Approval`;

    if (!pends.length) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding: 1.5rem; color: var(--text-muted);">🎉 No pending booking approvals in queue.</td></tr>`;
      return;
    }

    tbody.innerHTML = pends.map(b => `
      <tr>
        <td><strong>${b.booking_code}</strong></td>
        <td><strong>${b.room_number}</strong></td>
        <td>${b.user_name} (${b.user_role})</td>
        <td>${b.purpose}</td>
        <td>${b.booking_date} • ${b.start_time}-${b.end_time}</td>
        <td>${b.attendees}</td>
        <td><span class="status-badge occupied">⏳ Pending</span></td>
        <td>
          <div style="display:flex; gap: 0.35rem;">
            <button class="btn btn-primary btn-sm" onclick="approveBooking(${b.id})">Approve</button>
            <button class="btn btn-secondary btn-sm" style="color:#991B1B;" onclick="openRejectModal(${b.id})">Reject</button>
          </div>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Failed to load approvals queue:', err);
  }
}

async function approveBooking(bookingId) {
  try {
    const res = await fetch(`/api/bookings/${bookingId}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'Approved', admin_notes: 'Approved by staff review.' })
    });
    const data = await res.json();
    if (data.success) {
      showToast('Booking request approved successfully!', 'success');
      loadStaffApprovalsQueue();
      loadAvailability();
    } else {
      showToast(data.error || 'Failed to approve booking', 'error');
    }
  } catch (err) {
    showToast('Network error during approval', 'error');
  }
}

function openRejectModal(bookingId) {
  document.getElementById('reject-booking-id').value = bookingId;
  document.getElementById('reject-reason-text').value = '';
  document.getElementById('modal-reject').classList.add('active');
}

function closeRejectModal() {
  document.getElementById('modal-reject').classList.remove('active');
}

async function submitRejectAction(e) {
  e.preventDefault();
  const bookingId = document.getElementById('reject-booking-id').value;
  const reason = document.getElementById('reject-reason-text').value.trim();

  try {
    const res = await fetch(`/api/bookings/${bookingId}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'Rejected', rejection_reason: reason })
    });
    const data = await res.json();
    if (data.success) {
      showToast('Booking rejected with administrative remarks recorded.', 'info');
      closeRejectModal();
      loadStaffApprovalsQueue();
    } else {
      showToast(data.error || 'Failed to reject booking', 'error');
    }
  } catch (err) {
    showToast('Network error during rejection', 'error');
  }
}

async function handleStaffManualUpdate(e) {
  e.preventDefault();
  const payload = {
    classroom_id: document.getElementById('manual-room-select').value,
    update_date: document.getElementById('manual-date').value,
    start_time: document.getElementById('manual-start').value,
    end_time: document.getElementById('manual-end').value,
    reason: document.getElementById('manual-reason').value.trim()
  };

  try {
    const res = await fetch('/api/staff/manual-updates', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      showToast('Manual availability update saved successfully!', 'success');
      document.getElementById('staff-manual-update-form').reset();
      initDefaultSlotValues();
      loadStaffLogs();
      loadAvailability();
    } else {
      showToast(data.error || 'Failed to save manual update', 'error');
    }
  } catch (err) {
    showToast('Network error saving manual update', 'error');
  }
}

async function loadClassesForStaffCancel() {
  try {
    const res = await fetch('/api/classrooms');
    const data = await res.json();
    if (data.success) {
      // Fetch classes for dropdown
      const select = document.getElementById('cancel-class-select');
      if (!select) return;

      const cRes = await fetch('/api/admin/classes'); // or from timetable
      // Use helper: fetch classes from each room or cr
      const classesRes = await fetch('/api/cr/assigned-timetable?class_group=All');
      // Or collect classes from scheduled classes endpoint
    }
  } catch (err) {
    console.error(err);
  }
}

async function handleStaffCancellation(e) {
  e.preventDefault();
  const payload = {
    scheduled_class_id: document.getElementById('cancel-class-select').value,
    cancellation_date: document.getElementById('cancel-date').value,
    reason: document.getElementById('cancel-reason').value.trim()
  };

  try {
    const res = await fetch('/api/cancellations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message || 'Session cancelled successfully!', 'success');
      loadStaffLogs();
      loadAvailability();
    } else {
      showToast(data.error || 'Failed to record cancellation', 'error');
    }
  } catch (err) {
    showToast('Network error during cancellation', 'error');
  }
}

async function loadStaffLogs() {
  const tbody = document.getElementById('staff-logs-tbody');
  try {
    const [mRes, cRes] = await Promise.all([
      fetch('/api/staff/manual-updates'),
      fetch('/api/cancellations')
    ]);
    const mData = await mRes.json();
    const cData = await cRes.json();

    const manualUpdates = mData.success ? mData.manual_updates : [];
    const cancellations = cData.success ? cData.cancellations : [];

    if (!manualUpdates.length && !cancellations.length) {
      tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:1.5rem; color:var(--text-muted);">No manual updates or cancellations recorded.</td></tr>`;
      return;
    }

    let rowsHtml = '';
    manualUpdates.forEach(m => {
      rowsHtml += `
        <tr>
          <td><span class="status-badge occupied" style="font-size:0.7rem;">📌 Manual Update</span></td>
          <td><strong>${m.room_number}</strong> (${m.building})</td>
          <td>${m.update_date}</td>
          <td>${m.start_time} - ${m.end_time}</td>
          <td>${m.reason}</td>
          <td>${m.user_name || 'Staff'}</td>
          <td><button class="btn btn-secondary btn-sm" onclick="deleteManualUpdate(${m.id})">Delete</button></td>
        </tr>`;
    });

    cancellations.forEach(c => {
      rowsHtml += `
        <tr>
          <td><span class="status-badge maintenance" style="font-size:0.7rem;">❌ Cancelled Session</span></td>
          <td><strong>${c.room_number}</strong></td>
          <td>${c.cancellation_date}</td>
          <td>${c.course_code}: ${c.course_name} (${c.start_time}-${c.end_time})</td>
          <td>${c.reason}</td>
          <td>${c.user_name || 'Staff/CR'}</td>
          <td><button class="btn btn-secondary btn-sm" onclick="deleteCancellation(${c.id})">Restore</button></td>
        </tr>`;
    });

    tbody.innerHTML = rowsHtml;
  } catch (err) {
    console.error('Failed to load staff logs:', err);
  }
}

async function deleteManualUpdate(id) {
  try {
    await fetch(`/api/staff/manual-updates/${id}`, { method: 'DELETE' });
    showToast('Manual update removed.', 'info');
    loadStaffLogs();
    loadAvailability();
  } catch (err) {
    showToast('Error removing manual update', 'error');
  }
}

async function deleteCancellation(id) {
  try {
    await fetch(`/api/cancellations/${id}`, { method: 'DELETE' });
    showToast('Cancellation removed. Session restored.', 'info');
    loadStaffLogs();
    loadAvailability();
  } catch (err) {
    showToast('Error restoring session', 'error');
  }
}

// ============================================================
// CLASS REPRESENTATIVE (CR) DASHBOARD
// ============================================================

async function loadCRDashboard() {
  loadClassroomDropdowns();
  const assignedClass = state.currentUser ? (state.currentUser.assigned_class || 'III Year CSE A') : 'III Year CSE A';
  
  const badge = document.getElementById('cr-assigned-badge');
  const title = document.getElementById('cr-class-title');
  const roomNum = document.getElementById('cr-room-number');

  if (badge) badge.textContent = `Assigned: ${assignedClass}`;
  if (title) title.textContent = assignedClass;
  if (roomNum) roomNum.textContent = assignedClass.includes('CSE B') ? 'D310' : 'D309';

  try {
    const res = await fetch(`/api/cr/assigned-timetable?class_group=${encodeURIComponent(assignedClass)}`);
    const data = await res.json();
    if (!data.success) return;

    state.scheduledClassesCache = data.classes;
    renderCRTimetable(data.classes);
    populateCRCancelDropdown(data.classes);

    // Also populate staff cancel dropdown
    populateStaffCancelDropdown(data.classes);
  } catch (err) {
    console.error('Failed to load CR timetable:', err);
  }
}

function renderCRTimetable(classes) {
  const tbody = document.getElementById('cr-timetable-tbody');
  if (!classes.length) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; padding:1.5rem; color:var(--text-muted);">No classes scheduled for this class section.</td></tr>`;
    return;
  }

  tbody.innerHTML = classes.map(c => `
    <tr>
      <td><strong>${c.day_of_week}</strong></td>
      <td><span class="system-badge">${c.session_name || 'Session'}</span></td>
      <td>${c.start_time} - ${c.end_time}</td>
      <td><strong>${c.course_code}</strong></td>
      <td>${c.course_name}</td>
      <td>${c.instructor}</td>
      <td><strong>${c.room_number}</strong></td>
      <td>
        <button class="btn btn-secondary btn-sm" style="font-size:0.72rem; color:#991B1B;" onclick="prefillCRCancel(${c.id})">Report Cancel</button>
      </td>
    </tr>
  `).join('');
}

function populateCRCancelDropdown(classes) {
  const select = document.getElementById('cr-cancel-class-select');
  if (!select) return;
  select.innerHTML = '<option value="" disabled selected>-- Select Class Session to Cancel --</option>' +
    classes.map(c => `<option value="${c.id}">${c.day_of_week} (${c.start_time}-${c.end_time}): ${c.course_code} - ${c.course_name} (${c.room_number})</option>`).join('');
}

function populateStaffCancelDropdown(classes) {
  const select = document.getElementById('cancel-class-select');
  if (!select) return;
  select.innerHTML = '<option value="" disabled selected>-- Select Class Session to Cancel --</option>' +
    classes.map(c => `<option value="${c.id}">${c.class_group} • ${c.day_of_week} (${c.start_time}-${c.end_time}): ${c.course_code} (${c.room_number})</option>`).join('');
}

function prefillCRCancel(classId) {
  const select = document.getElementById('cr-cancel-class-select');
  if (select) select.value = classId;
}

async function handleCRCancellation(e) {
  e.preventDefault();
  const payload = {
    scheduled_class_id: document.getElementById('cr-cancel-class-select').value,
    cancellation_date: document.getElementById('cr-cancel-date').value,
    reason: document.getElementById('cr-cancel-reason').value.trim()
  };

  try {
    const res = await fetch('/api/cancellations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      showToast(data.message || 'Cancellation recorded successfully! Conflict cleared.', 'success');
      document.getElementById('cr-cancel-form').reset();
      initDefaultSlotValues();
      loadAvailability();
    } else {
      showToast(data.error || 'Permission error recording cancellation', 'error');
    }
  } catch (err) {
    showToast('Network error during cancellation submission', 'error');
  }
}

async function handleCRBooking(e) {
  e.preventDefault();
  const payload = {
    classroom_id: document.getElementById('cr-book-room-select').value,
    user_name: state.currentUser ? state.currentUser.full_name : 'Class Representative',
    user_email: state.currentUser ? state.currentUser.email : 'cr@campus.edu',
    user_role: 'CR',
    purpose: document.getElementById('cr-book-purpose').value.trim(),
    booking_date: document.getElementById('cr-book-date').value,
    start_time: document.getElementById('cr-book-start').value,
    end_time: document.getElementById('cr-book-end').value,
    attendees: parseInt(document.getElementById('cr-book-attendees').value, 10)
  };

  await executeBookingSubmission(payload);
}

// ============================================================
// ADMIN DASHBOARD
// ============================================================

async function loadAdminPortal() {
  loadAdminStats();
  loadAdminRooms();
  loadAdminMaintenance();
  loadAdminUsers();
  loadAdminAuditLogs();
}

async function loadAdminStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();
    if (data.success) {
      const s = data.stats;
      document.getElementById('admin-stat-rooms').textContent = s.total_rooms;
      document.getElementById('admin-stat-classes').textContent = s.total_classes;
      document.getElementById('admin-stat-pending').textContent = s.pending_bookings;
      document.getElementById('admin-stat-approved').textContent = s.approved_bookings;
      document.getElementById('admin-stat-maintenance').textContent = s.active_maintenance;
    }
  } catch (err) {
    console.error('Stats error:', err);
  }
}

async function loadAdminRooms() {
  const tbody = document.getElementById('admin-rooms-tbody');
  try {
    const res = await fetch('/api/classrooms?all=1');
    const data = await res.json();
    if (!data.success) return;

    tbody.innerHTML = data.classrooms.map(r => `
      <tr>
        <td><strong>${r.room_number}</strong></td>
        <td>${r.building}</td>
        <td>Floor ${r.floor}</td>
        <td>${r.capacity} seats</td>
        <td>${r.room_type}</td>
        <td><small style="color:#475569;">${r.facilities}</small></td>
        <td><small style="color:var(--cyan-dark);">${r.notes || 'Demonstration Data'}</small></td>
        <td>
          <div style="display:flex; gap:0.35rem;">
            ${r.is_active
              ? `<button class="btn btn-secondary btn-sm" style="color:#991B1B;" onclick="deactivateRoom(${r.id})">Deactivate</button>`
              : `<span class="system-badge" style="background:#F1F5F9; color:#94A3B8;">Inactive</span>`
            }
          </div>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error(err);
  }
}

function openAddRoomModal() {
  document.getElementById('modal-add-room').classList.add('active');
}

function closeAddRoomModal() {
  document.getElementById('modal-add-room').classList.remove('active');
}

async function handleAddRoomSubmit(e) {
  e.preventDefault();
  const payload = {
    room_number: document.getElementById('ar-number').value.trim(),
    building: document.getElementById('ar-building').value.trim(),
    floor: parseInt(document.getElementById('ar-floor').value, 10),
    capacity: parseInt(document.getElementById('ar-capacity').value, 10),
    room_type: document.getElementById('ar-type').value.trim(),
    facilities: document.getElementById('ar-facilities').value.trim(),
    notes: document.getElementById('ar-notes').value.trim()
  };

  try {
    const res = await fetch('/api/classrooms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      showToast('Classroom added successfully!', 'success');
      closeAddRoomModal();
      loadAdminRooms();
      loadClassroomDropdowns();
      loadAvailability();
    } else {
      showToast(data.error || 'Failed to add classroom', 'error');
    }
  } catch (err) {
    showToast('Network error adding room', 'error');
  }
}

async function deactivateRoom(roomId) {
  if (!confirm('Are you sure you want to deactivate this classroom?')) return;
  try {
    const res = await fetch(`/api/classrooms/${roomId}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success) {
      showToast('Classroom deactivated.', 'info');
      loadAdminRooms();
      loadAvailability();
    }
  } catch (err) {
    showToast('Failed to deactivate room', 'error');
  }
}

async function loadAdminMaintenance() {
  const tbody = document.getElementById('admin-maintenance-tbody');
  try {
    const res = await fetch('/api/maintenance');
    const data = await res.json();
    if (!data.success) return;

    if (!data.maintenance_blocks.length) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:1.5rem; color:var(--text-muted);">No active maintenance blocks.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.maintenance_blocks.map(m => `
      <tr>
        <td><strong>${m.room_number}</strong> (${m.building})</td>
        <td>${m.start_date} ${m.start_time}</td>
        <td>${m.end_date} ${m.end_time}</td>
        <td><span style="color:#9F1239;">${m.reason}</span></td>
        <td><button class="btn btn-secondary btn-sm" onclick="removeMaintenance(${m.id})">Remove</button></td>
      </tr>
    `).join('');
  } catch (err) {
    console.error(err);
  }
}

function openAddMaintenanceModal() {
  document.getElementById('modal-maintenance').classList.add('active');
}

function closeMaintenanceModal() {
  document.getElementById('modal-maintenance').classList.remove('active');
}

async function handleMaintenanceSubmit(e) {
  e.preventDefault();
  const payload = {
    classroom_id: document.getElementById('maint-room-select').value,
    start_date: document.getElementById('maint-start-date').value,
    start_time: document.getElementById('maint-start-time').value,
    end_date: document.getElementById('maint-end-date').value,
    end_time: document.getElementById('maint-end-time').value,
    reason: document.getElementById('maint-reason').value.trim()
  };

  try {
    const res = await fetch('/api/maintenance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      showToast('Maintenance window scheduled successfully!', 'success');
      closeMaintenanceModal();
      loadAdminMaintenance();
      loadAvailability();
    } else {
      showToast(data.error || 'Failed to schedule maintenance', 'error');
    }
  } catch (err) {
    showToast('Network error scheduling maintenance', 'error');
  }
}

async function removeMaintenance(blockId) {
  try {
    await fetch(`/api/maintenance/${blockId}`, { method: 'DELETE' });
    showToast('Maintenance block removed.', 'info');
    loadAdminMaintenance();
    loadAvailability();
  } catch (err) {
    showToast('Failed to remove maintenance block', 'error');
  }
}

async function loadAdminUsers() {
  const tbody = document.getElementById('admin-users-tbody');
  try {
    const res = await fetch('/api/admin/users');
    const data = await res.json();
    if (!data.success) return;

    tbody.innerHTML = data.users.map(u => `
      <tr>
        <td><strong>${u.username}</strong></td>
        <td>${u.full_name}</td>
        <td>${u.email}</td>
        <td><span class="user-role-badge role-${u.role}">${u.role.toUpperCase()}</span></td>
        <td><strong>${u.assigned_class || '—'}</strong></td>
        <td>
          <button class="btn btn-secondary btn-sm" onclick="promptUpdateUser(${u.id}, '${u.role}', '${u.assigned_class || ''}')">Edit Assignment</button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error(err);
  }
}

async function promptUpdateUser(userId, currentRole, currentClass) {
  const newRole = prompt('Enter role (student, staff, cr, admin):', currentRole);
  if (!newRole) return;
  let newClass = currentClass;
  if (newRole.toLowerCase() === 'cr') {
    newClass = prompt('Enter assigned class group for this CR (e.g. III Year CSE A, III Year CSE B):', currentClass || 'III Year CSE A');
  }

  try {
    const res = await fetch(`/api/admin/users/${userId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role: newRole, assigned_class: newClass })
    });
    const data = await res.json();
    if (data.success) {
      showToast('User role and class assignment updated!', 'success');
      loadAdminUsers();
      checkAuthStatus();
    } else {
      showToast(data.error || 'Update failed', 'error');
    }
  } catch (err) {
    showToast('Network error updating user', 'error');
  }
}

async function loadAdminAuditLogs() {
  const tbody = document.getElementById('admin-audit-tbody');
  try {
    const res = await fetch('/api/admin/audit-logs');
    const data = await res.json();
    if (!data.success) return;

    tbody.innerHTML = data.audit_logs.map(l => `
      <tr>
        <td><small style="color:var(--text-muted);">${l.created_at}</small></td>
        <td><strong>${l.user_name || 'System'}</strong></td>
        <td><span class="system-badge">${l.action}</span></td>
        <td>${l.details}</td>
      </tr>
    `).join('');
  } catch (err) {
    console.error(err);
  }
}

async function resetDemoData() {
  if (!confirm('Reset database to pristine demonstration seed dataset? This will restore initial classrooms, schedules, and demo users.')) return;
  try {
    const res = await fetch('/api/demo/reset', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast('Demonstration data reset successfully!', 'success');
      await checkAuthStatus();
      await loadClassroomDropdowns();
      loadAvailability();
    }
  } catch (err) {
    showToast('Failed to reset demo data', 'error');
  }
}

// ============================================================
// TOAST NOTIFICATIONS
// ============================================================

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span>
    <span style="flex:1;">${message}</span>
    <button style="background:transparent; border:none; color:white; cursor:pointer; font-size:1.1rem; line-height:1;" onclick="this.parentElement.remove()">&times;</button>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    if (toast.parentElement) toast.remove();
  }, 4500);
}
