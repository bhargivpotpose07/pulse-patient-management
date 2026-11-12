import streamlit as st
import sqlite3
from datetime import date, datetime, timedelta

DB = "pulse.db"
ROOMS = 74
FEVER_THRESHOLD = 38.0  # Demonstration assumption; validate with clinical team.

def connect():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS patients(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, age INTEGER, room INTEGER UNIQUE,
            admitted_on TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Admitted',
            outcome TEXT DEFAULT 'Pending')""")
        c.execute("""CREATE TABLE IF NOT EXISTS temperatures(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL, recorded_on TEXT NOT NULL,
            temperature REAL NOT NULL, nurse TEXT,
            UNIQUE(patient_id, recorded_on),
            FOREIGN KEY(patient_id) REFERENCES patients(id))""")
        c.execute("""CREATE TABLE IF NOT EXISTS visits(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL, visited_on TEXT NOT NULL,
            doctor TEXT, notes TEXT,
            UNIQUE(patient_id, visited_on),
            FOREIGN KEY(patient_id) REFERENCES patients(id))""")

def rows(query, params=()):
    with connect() as c:
        return c.execute(query, params).fetchall()

def run(query, params=()):
    with connect() as c:
        c.execute(query, params)
        c.commit()

def active_patients():
    return rows("SELECT * FROM patients WHERE status='Admitted' ORDER BY room")

def fever_free_streak(pid):
    readings = rows("SELECT recorded_on, temperature FROM temperatures WHERE patient_id=? ORDER BY recorded_on DESC", (pid,))
    streak, expected = 0, date.today()
    by_day = {date.fromisoformat(r["recorded_on"]): r["temperature"] for r in readings}
    while expected in by_day and by_day[expected] < FEVER_THRESHOLD:
        streak += 1
        expected -= timedelta(days=1)
    return streak

st.set_page_config(page_title="PULSE | Patient Operations", page_icon="🩺", layout="wide")
init_db()
st.title("🩺 PULSE")
st.caption("Patient Updates, Logs, Scheduling & Evaluation")
st.info("Demonstration prototype only — not for clinical use. The 38°C fever threshold is an assumption and must be clinically validated.")

role = st.sidebar.selectbox("Demo role", ["Operations Manager", "Administrator", "Nurse", "Doctor"])
st.sidebar.caption("Demo role selector only; this is not secure authentication.")
page = st.sidebar.radio("Navigate", ["Overview", "Patients", "Temperature Checks", "Doctor Visits", "Discharge", "Performance"])

patients = active_patients()
occupied = len(patients)
available = ROOMS - occupied

if page == "Overview":
    st.subheader("Facility overview")
    a,b,c,d = st.columns(4)
    a.metric("Occupied rooms", f"{occupied}/{ROOMS}")
    b.metric("Available rooms", available)
    today = date.today().isoformat()
    temp_done = rows("SELECT COUNT(*) n FROM temperatures WHERE recorded_on=?", (today,))[0]["n"]
    visit_done = rows("SELECT COUNT(*) n FROM visits WHERE visited_on=?", (today,))[0]["n"]
    c.metric("Temperature checks today", temp_done)
    d.metric("Doctor visits today", visit_done)
    st.subheader("Today's workflow")
    st.write(f"**Temperature checks pending:** {max(occupied-temp_done, 0)}")
    st.write(f"**Doctor visits pending:** {max(temp_done-visit_done, 0)}")
    st.caption("Counts are facility-wide and assume one daily record per admitted patient.")

elif page == "Patients":
    st.subheader("Patient management")
    if role in ["Administrator", "Operations Manager"]:
        with st.form("add_patient"):
            name = st.text_input("Patient name")
            age = st.number_input("Age", min_value=0, max_value=120, value=30)
            used = {r["room"] for r in patients}
            free_rooms = [x for x in range(1, ROOMS+1) if x not in used]
            room = st.selectbox("Available room", free_rooms) if free_rooms else None
            submitted = st.form_submit_button("Register patient", disabled=not free_rooms)
            if submitted:
                if not name.strip():
                    st.error("Enter a patient name.")
                else:
                    try:
                        run("INSERT INTO patients(name,age,room,admitted_on) VALUES(?,?,?,?)",
                            (name.strip(), int(age), room, date.today().isoformat()))
                        st.success(f"Patient registered and assigned to room {room}.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("That room is already occupied.")
    else:
        st.caption("Patient registration is restricted to administrators.")
    st.dataframe([dict(r) for r in patients], use_container_width=True) if patients else st.info("No admitted patients yet.")

elif page == "Temperature Checks":
    st.subheader("Daily temperature monitoring")
    if role == "Nurse":
        if patients:
            patient_map = {f'{p["name"]} — Room {p["room"]} (ID {p["id"]})': p["id"] for p in patients}
            selected = st.selectbox("Select patient", list(patient_map))
            temp = st.number_input("Temperature (°C)", min_value=30.0, max_value=45.0, value=37.0, step=0.1)
            nurse = st.text_input("Nurse name")
            if st.button("Save temperature"):
                try:
                    run("INSERT INTO temperatures(patient_id,recorded_on,temperature,nurse) VALUES(?,?,?,?)",
                        (patient_map[selected], date.today().isoformat(), temp, nurse.strip()))
                    st.success("Temperature recorded.")
                except sqlite3.IntegrityError:
                    st.error("A temperature entry already exists for this patient today.")
        else:
            st.info("Register a patient first.")
    else:
        st.caption("Temperature entry is available to the Nurse demo role.")
    st.subheader("Temperature history")
    history = rows("""SELECT p.name,p.room,t.recorded_on,t.temperature,t.nurse
                      FROM temperatures t JOIN patients p ON p.id=t.patient_id
                      ORDER BY t.recorded_on DESC,t.id DESC""")
    st.dataframe([dict(r) for r in history], use_container_width=True) if history else st.info("No temperature readings recorded yet.")

elif page == "Doctor Visits":
    st.subheader("Doctor visit management")
    today = date.today().isoformat()
    eligible = rows("""SELECT p.* FROM patients p
        JOIN temperatures t ON t.patient_id=p.id AND t.recorded_on=?
        WHERE p.status='Admitted'
        AND NOT EXISTS (SELECT 1 FROM visits v WHERE v.patient_id=p.id AND v.visited_on=?)""", (today,today))
    if role == "Doctor":
        if eligible:
            pm = {f'{p["name"]} — Room {p["room"]}': p["id"] for p in eligible}
            selected = st.selectbox("Patient with temperature recorded today", list(pm))
            doctor = st.text_input("Doctor name")
            notes = st.text_area("Visit notes")
            if st.button("Record doctor visit"):
                run("INSERT INTO visits(patient_id,visited_on,doctor,notes) VALUES(?,?,?,?)",
                    (pm[selected], today, doctor.strip(), notes.strip()))
                st.success("Doctor visit recorded.")
                st.rerun()
        else:
            st.info("No patients are currently awaiting a doctor visit after today's temperature check.")
    else:
        st.caption("Visit recording is available to the Doctor demo role.")
    st.subheader("Visit history")
    visits = rows("""SELECT p.name,p.room,v.visited_on,v.doctor,v.notes
                     FROM visits v JOIN patients p ON p.id=v.patient_id
                     ORDER BY v.visited_on DESC,v.id DESC""")
    st.dataframe([dict(r) for r in visits], use_container_width=True) if visits else st.info("No visits recorded yet.")

elif page == "Discharge":
    st.subheader("Discharge management")
    st.caption("Eligibility is calculated from three consecutive calendar days of recorded temperatures below the demo threshold, including today.")
    candidates = []
    for p in patients:
        streak = fever_free_streak(p["id"])
        if streak >= 3:
            candidates.append((p, streak))
    if candidates:
        for p, streak in candidates:
            with st.expander(f'{p["name"]} — Room {p["room"]} — {streak} fever-free days'):
                st.write("Doctor confirmation is required before discharge.")
                if role == "Doctor":
                    if st.button("Confirm discharge eligibility", key=f"confirm{p['id']}"):
                        run("UPDATE patients SET outcome='Recovered' WHERE id=?", (p["id"],))
                        st.success("Eligibility confirmed. Administrator can now complete discharge.")
                elif role == "Administrator":
                    if p["outcome"] == "Recovered":
                        if st.button("Complete discharge", key=f"discharge{p['id']}"):
                            run("UPDATE patients SET status='Discharged' WHERE id=?", (p["id"],))
                            st.success("Patient discharged; room released.")
                            st.rerun()
                    else:
                        st.warning("Awaiting doctor confirmation.")
                else:
                    st.caption("Switch to Doctor for confirmation or Administrator to complete discharge.")
    else:
        st.info("No patients currently meet the three-day fever-free rule.")
    st.subheader("Discharged patients")
    discharged = rows("SELECT * FROM patients WHERE status='Discharged' ORDER BY id DESC")
    st.dataframe([dict(r) for r in discharged], use_container_width=True) if discharged else st.caption("No discharges recorded.")

elif page == "Performance":
    st.subheader("Treatment outcomes")
    outcomes = rows("SELECT outcome,COUNT(*) n FROM patients WHERE status='Discharged' GROUP BY outcome")
    recovered = sum(r["n"] for r in outcomes if r["outcome"] == "Recovered")
    deceased = sum(r["n"] for r in outcomes if r["outcome"] == "Deceased")
    total = recovered + deceased
    x,y,z = st.columns(3)
    x.metric("Recorded outcomes", total)
    y.metric("Success rate", f"{(recovered/total*100):.1f}%" if total else "N/A")
    z.metric("Mortality rate", f"{(deceased/total*100):.1f}%" if total else "N/A")
    st.caption("Rates are calculated only from discharged patients with recorded Recovered or Deceased outcomes. Pending outcomes are excluded.")
    if role == "Administrator":
        with st.form("outcome_form"):
            all_patients = rows("SELECT * FROM patients ORDER BY id DESC")
            if all_patients:
                pm = {f'{p["name"]} — Room {p["room"]} — {p["status"]}': p["id"] for p in all_patients}
                chosen = st.selectbox("Patient", list(pm))
                outcome = st.selectbox("Outcome", ["Recovered", "Deceased"])
                if st.form_submit_button("Save outcome"):
                    run("UPDATE patients SET outcome=? WHERE id=?", (outcome, pm[chosen]))
                    st.success("Outcome saved.")
            else:
                st.info("No patient records available.")
    else:
        st.caption("Only administrators can update patient outcomes.")
    st.write("**Benchmarks:** 85% success rate and 15% mortality rate (from the assessment).")

st.divider()
st.caption("PULSE prototype • Sample/demo workflow • SQLite database")
