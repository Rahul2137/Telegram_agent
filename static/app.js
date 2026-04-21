/* ═══════════════════════════════════════════════════════════
   app.js — Student Outreach Dashboard Frontend Logic
   ═══════════════════════════════════════════════════════════ */

// ── State ───────────────────────────────────────────────────
let coursesCache = [];
let studentsCache = [];
let sessionsCache = [];
let assignmentsCache = [];

// ── Init ────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
    setupTabs();
    await loadCourses();
    await loadDropdowns();
    loadAttendanceTab();
    loadHomeworkTab();
    loadUpcomingTab();
    loadLogs();
});

// ── Tab switching ───────────────────────────────────────────
function setupTabs() {
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById("panel-" + btn.dataset.tab).classList.add("active");

            if (btn.dataset.tab === "attendance") loadAttendanceTab();
            if (btn.dataset.tab === "homework") loadHomeworkTab();
            if (btn.dataset.tab === "upcoming") loadUpcomingTab();
            if (btn.dataset.tab === "trigger") loadLogs();
        });
    });
}

// ── Utilities ───────────────────────────────────────────────
async function api(path, options = {}) {
    const resp = await fetch(path, options);
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
}

function showToast(msg, isError = false) {
    const t = document.getElementById("toast");
    t.textContent = msg;
    t.className = "toast show" + (isError ? " error" : "");
    setTimeout(() => t.className = "toast", 3000);
}

function badgeHtml(text, type) {
    return `<span class="badge badge-${type.toLowerCase()}">${text}</span>`;
}

function pctBarHtml(pct) {
    const color = pct >= 80 ? "var(--accent-green)" : pct >= 60 ? "var(--accent-amber)" : "var(--accent-red)";
    return `${pct}%<div class="pct-bar-wrap"><div class="pct-bar" style="width:${pct}%;background:${color}"></div></div>`;
}

// ── Load courses into all course filter dropdowns ───────────
async function loadCourses() {
    coursesCache = await api("/api/courses");
    const courseDropdowns = ["attCourseFilter", "hwCourseFilter"];
    for (const id of courseDropdowns) {
        const sel = document.getElementById(id);
        coursesCache.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c.course_id;
            opt.textContent = c.course_name;
            sel.appendChild(opt);
        });
    }
}

// ═══════════════════════════════════════════════════════════
// ATTENDANCE TAB
// ═══════════════════════════════════════════════════════════

async function onAttCourseChange() {
    const courseId = document.getElementById("attCourseFilter").value;
    // Reload date dropdown based on selected course
    const dateSel = document.getElementById("attDateFilter");
    dateSel.innerHTML = '<option value="">All Dates</option>';
    const dates = await api(`/api/attendance/dates?course_id=${courseId}`);
    // Deduplicate dates
    const seen = new Set();
    dates.forEach(s => {
        if (!seen.has(s.date)) {
            seen.add(s.date);
            const opt = document.createElement("option");
            opt.value = s.date;
            opt.textContent = `${s.date} — ${s.topic}`;
            dateSel.appendChild(opt);
        }
    });
    loadAttendanceTab();
}

async function loadAttendanceTab() {
    const courseId = document.getElementById("attCourseFilter").value;
    const dateVal = document.getElementById("attDateFilter").value;

    // If a specific date is selected, show per-student records for that session
    if (dateVal) {
        await loadAttendanceDateView(courseId, dateVal);
    } else {
        await loadAttendanceSummaryView(courseId);
    }
}

async function loadAttendanceSummaryView(courseId) {
    const data = await api(`/api/attendance/summary?course_id=${courseId}`);

    // Stats
    const totalStudents = data.length;
    const avgPct = totalStudents ? Math.round(data.reduce((s, d) => s + d.percentage, 0) / totalStudents) : 0;
    const atRisk = data.filter(d => d.percentage < 60).length;
    const perfect = data.filter(d => d.percentage === 100).length;

    document.getElementById("attendanceStats").innerHTML = `
        <div class="stat-card"><div class="stat-label">Total Students</div><div class="stat-value blue">${totalStudents}</div></div>
        <div class="stat-card"><div class="stat-label">Avg Attendance</div><div class="stat-value green">${avgPct}%</div></div>
        <div class="stat-card"><div class="stat-label">At Risk (&lt;60%)</div><div class="stat-value red">${atRisk}</div></div>
        <div class="stat-card"><div class="stat-label">Perfect Attendance</div><div class="stat-value purple">${perfect}</div></div>
    `;

    // Table header for summary view
    document.getElementById("attendanceTableHead").innerHTML = `
        <th>Student</th><th>Course</th><th>Sessions Attended</th><th>Absent</th><th>Attendance %</th><th>Status</th>
    `;

    const tbody = document.getElementById("attendanceBody");
    tbody.innerHTML = data.map(d => `
        <tr>
            <td><strong>${d.name}</strong><br><span style="font-size:0.72rem;color:var(--text-muted)">${d.student_id}</span></td>
            <td>${d.course_name}</td>
            <td>${d.present}</td>
            <td>${d.absent}</td>
            <td>${pctBarHtml(d.percentage)}</td>
            <td>${d.percentage >= 80 ? badgeHtml("Good", "present") : d.percentage >= 60 ? badgeHtml("Warning", "pending") : badgeHtml("At Risk", "absent")}</td>
        </tr>
    `).join("");
}

async function loadAttendanceDateView(courseId, date) {
    const data = await api(`/api/attendance?course_id=${courseId}&date=${date}`);

    const present = data.filter(d => d.status === "Present").length;
    const absent = data.filter(d => d.status === "Absent").length;
    const total = data.length;
    const pct = total ? Math.round((present / total) * 100) : 0;

    document.getElementById("attendanceStats").innerHTML = `
        <div class="stat-card"><div class="stat-label">Date</div><div class="stat-value blue">${date}</div></div>
        <div class="stat-card"><div class="stat-label">Present</div><div class="stat-value green">${present}</div></div>
        <div class="stat-card"><div class="stat-label">Absent</div><div class="stat-value red">${absent}</div></div>
        <div class="stat-card"><div class="stat-label">Attendance</div><div class="stat-value purple">${pct}%</div></div>
    `;

    // Table header for date view
    document.getElementById("attendanceTableHead").innerHTML = `
        <th>Student</th><th>Course</th><th>Session Topic</th><th>Date</th><th>Status</th><th>Action</th>
    `;

    const tbody = document.getElementById("attendanceBody");
    tbody.innerHTML = data.map(d => `
        <tr>
            <td><strong>${d.name}</strong><br><span style="font-size:0.72rem;color:var(--text-muted)">${d.student_id}</span></td>
            <td>${d.course_name}</td>
            <td>${d.topic}</td>
            <td>${d.date}</td>
            <td>${badgeHtml(d.status, d.status)}</td>
            <td>
                <button class="btn-inline-mark" onclick="quickMarkAttendance('${d.student_id}', '${d.session_id}', '${d.status === "Present" ? "Absent" : "Present"}')">
                    Mark ${d.status === "Present" ? "Absent" : "Present"}
                </button>
            </td>
        </tr>
    `).join("");
}

async function quickMarkAttendance(studentId, sessionId, newStatus) {
    await api("/api/attendance/mark", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_id: studentId, session_id: sessionId, status: newStatus }),
    });
    showToast(`Marked ${studentId} as ${newStatus}`);
    loadAttendanceTab();
}

// ═══════════════════════════════════════════════════════════
// HOMEWORK TAB
// ═══════════════════════════════════════════════════════════

async function onHwCourseChange() {
    const courseId = document.getElementById("hwCourseFilter").value;
    // Reload assignment dropdown filtered by course
    const assignSel = document.getElementById("hwAssignFilter");
    assignSel.innerHTML = '<option value="">All Assignments</option>';
    const filtered = courseId
        ? assignmentsCache.filter(a => a.course_id === courseId)
        : assignmentsCache;
    filtered.forEach(a => {
        const opt = document.createElement("option");
        opt.value = a.assignment_id;
        opt.textContent = `${a.name} (${a.deadline})`;
        assignSel.appendChild(opt);
    });
    loadHomeworkTab();
}

async function loadHomeworkTab() {
    const courseId = document.getElementById("hwCourseFilter").value;
    const assignId = document.getElementById("hwAssignFilter").value;

    let url = "/api/homework?";
    if (courseId) url += `course_id=${courseId}&`;
    if (assignId) url += `assignment_id=${assignId}&`;

    const data = await api(url);

    // Stats
    const total = data.length;
    const complete = data.filter(d => d.status === "Complete").length;
    const incomplete = data.filter(d => d.status === "Incomplete").length;
    const pending = data.filter(d => d.status === "Pending").length;

    document.getElementById("homeworkStats").innerHTML = `
        <div class="stat-card"><div class="stat-label">Total Records</div><div class="stat-value blue">${total}</div></div>
        <div class="stat-card"><div class="stat-label">Complete</div><div class="stat-value green">${complete}</div></div>
        <div class="stat-card"><div class="stat-label">Incomplete</div><div class="stat-value red">${incomplete}</div></div>
        <div class="stat-card"><div class="stat-label">Pending</div><div class="stat-value amber">${pending}</div></div>
    `;

    const tbody = document.getElementById("homeworkBody");
    tbody.innerHTML = data.map(d => `
        <tr>
            <td><strong>${d.student_name}</strong><br><span style="font-size:0.72rem;color:var(--text-muted)">${d.student_id}</span></td>
            <td>${d.assignment_name || d.assignment_id}</td>
            <td>${d.course_name || ""}</td>
            <td>${d.deadline || ""}</td>
            <td>${badgeHtml(d.status, d.status)}</td>
            <td>
                <button class="btn-inline-mark" onclick="quickMarkHomework('${d.student_id}', '${d.assignment_id}', '${d.status === "Complete" ? "Incomplete" : "Complete"}')">
                    ${d.status === "Complete" ? "Mark Incomplete" : "Mark Complete"}
                </button>
            </td>
        </tr>
    `).join("");
}

async function quickMarkHomework(studentId, assignmentId, newStatus) {
    await api("/api/homework/mark", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ student_id: studentId, assignment_id: assignmentId, status: newStatus }),
    });
    showToast(`Updated ${studentId} → ${newStatus}`);
    loadHomeworkTab();
}

// ═══════════════════════════════════════════════════════════
// TRIGGER TAB
// ═══════════════════════════════════════════════════════════

async function triggerTask(task) {
    const cardMap = { attendance: "triggerAttendance", homework: "triggerHomework", reminders: "triggerReminders", feedback: "triggerFeedback" };

    if (task === "all") {
        Object.values(cardMap).forEach(id => document.getElementById(id).classList.add("sending"));
    } else {
        document.getElementById(cardMap[task])?.classList.add("sending");
    }

    try {
        const result = await api("/api/trigger", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ task }),
        });

        const card = document.getElementById("triggerResultsCard");
        card.style.display = "block";
        const tbody = document.getElementById("triggerResultsBody");

        if (result.results.length === 0) {
            tbody.innerHTML = `<tr><td colspan="3" style="text-align:center;color:var(--text-muted);padding:20px;">No matching students found or no students registered.</td></tr>`;
        } else {
            tbody.innerHTML = result.results.map(r => `
                <tr>
                    <td>${r.student_id}</td>
                    <td style="max-width:400px">${r.scenario}</td>
                    <td>${r.sent ? badgeHtml("Sent", "present") : badgeHtml("Not Sent", "absent")}</td>
                </tr>
            `).join("");
        }

        showToast(`Triggered ${result.triggered} outreach message(s)`);
        loadLogs();
    } catch (e) {
        showToast("Trigger failed: " + e.message, true);
    } finally {
        Object.values(cardMap).forEach(id => {
            const el = document.getElementById(id);
            el.classList.remove("sending");
            el.classList.add("sent");
            setTimeout(() => el.classList.remove("sent"), 3000);
        });
    }
}

async function loadLogs() {
    try {
        const logs = await api("/api/logs");
        const tbody = document.getElementById("logsBody");
        if (logs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:20px;">No interaction logs yet.</td></tr>`;
            return;
        }
        tbody.innerHTML = logs.slice(0, 20).map(l => `
            <tr>
                <td style="font-size:0.75rem;white-space:nowrap">${new Date(l.timestamp).toLocaleString()}</td>
                <td>${l.student_id}</td>
                <td style="max-width:300px;font-size:0.8rem">${l.scenario}</td>
                <td>${badgeHtml(l.status, l.status)}</td>
                <td style="max-width:350px;font-size:0.8rem;color:var(--text-secondary)">${l.summary}</td>
            </tr>
        `).join("");
    } catch (e) { /* no logs yet */ }
}

// ═══════════════════════════════════════════════════════════
// UPCOMING TAB
// ═══════════════════════════════════════════════════════════

async function loadUpcomingTab() {
    const data = await api("/api/upcoming");

    const sessions = data.filter(d => d.type === "Session");
    const deadlines = data.filter(d => d.type === "Deadline");
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    const tomorrowStr = tomorrow.toISOString().split("T")[0];
    const tomorrowItems = data.filter(d => d.event_date === tomorrowStr);

    document.getElementById("upcomingStats").innerHTML = `
        <div class="stat-card"><div class="stat-label">Upcoming Sessions</div><div class="stat-value blue">${sessions.length}</div></div>
        <div class="stat-card"><div class="stat-label">Upcoming Deadlines</div><div class="stat-value amber">${deadlines.length}</div></div>
        <div class="stat-card"><div class="stat-label">Tomorrow</div><div class="stat-value purple">${tomorrowItems.length}</div></div>
    `;

    // Deduplicate
    const seen = new Set();
    const unique = data.filter(d => {
        const key = d.event_date + "|" + d.detail + "|" + d.course_name;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
    });

    const timeline = document.getElementById("upcomingTimeline");
    if (unique.length === 0) {
        timeline.innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-muted)">No upcoming events found.</div>`;
        return;
    }
    timeline.innerHTML = unique.map(d => {
        const date = new Date(d.event_date + "T00:00:00");
        const dayNum = date.getDate();
        const monthName = date.toLocaleString("default", { month: "short" });
        const isTomorrow = d.event_date === tomorrowStr;
        return `
            <div class="timeline-item ${isTomorrow ? "is-tomorrow" : ""}">
                <div class="timeline-date">
                    <div class="day">${dayNum}</div>
                    <div class="month">${monthName}</div>
                </div>
                <div class="timeline-detail">
                    <div class="detail-title">${d.detail}</div>
                    <div class="detail-course">${d.course_name}</div>
                </div>
                ${badgeHtml(d.type, d.type)}
                ${isTomorrow ? badgeHtml("Tomorrow", "pending") : ""}
            </div>
        `;
    }).join("");
}

// ═══════════════════════════════════════════════════════════
// DROPDOWNS & MODALS
// ═══════════════════════════════════════════════════════════

async function loadDropdowns() {
    studentsCache = await api("/api/students");
    sessionsCache = await api("/api/sessions");
    assignmentsCache = await api("/api/assignments");
}

function populateSelect(id, items, valueKey, labelFn) {
    const sel = document.getElementById(id);
    sel.innerHTML = "";
    items.forEach(item => {
        const opt = document.createElement("option");
        opt.value = item[valueKey];
        opt.textContent = labelFn(item);
        sel.appendChild(opt);
    });
}

function openMarkAttendanceModal() {
    populateSelect("modalAttSession", sessionsCache, "session_id", s => `${s.course_name} — ${s.topic} (${s.date})`);
    populateSelect("modalAttStudent", studentsCache, "student_id", s => `${s.name} (${s.student_id})`);
    document.getElementById("attendanceModal").classList.add("open");
}

function openMarkHomeworkModal() {
    populateSelect("modalHwAssign", assignmentsCache, "assignment_id", a => `${a.course_name} — ${a.name} (${a.deadline})`);
    populateSelect("modalHwStudent", studentsCache, "student_id", s => `${s.name} (${s.student_id})`);
    document.getElementById("homeworkModal").classList.add("open");
}

function closeModal(id) {
    document.getElementById(id).classList.remove("open");
}

async function submitMarkAttendance() {
    const payload = {
        student_id: document.getElementById("modalAttStudent").value,
        session_id: document.getElementById("modalAttSession").value,
        status: document.getElementById("modalAttStatus").value,
    };
    await api("/api/attendance/mark", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    closeModal("attendanceModal");
    showToast(`Marked ${payload.student_id} as ${payload.status}`);
    loadAttendanceTab();
}

async function submitMarkHomework() {
    const payload = {
        student_id: document.getElementById("modalHwStudent").value,
        assignment_id: document.getElementById("modalHwAssign").value,
        status: document.getElementById("modalHwStatus").value,
    };
    await api("/api/homework/mark", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    closeModal("homeworkModal");
    showToast(`Updated ${payload.student_id} → ${payload.status}`);
    loadHomeworkTab();
}

// Close modals on overlay click
document.querySelectorAll(".modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", (e) => {
        if (e.target === overlay) overlay.classList.remove("open");
    });
});
