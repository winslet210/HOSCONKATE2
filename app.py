# hoscon_app.py
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import json, os

DB_PATH = "hoscon_demo.db"

# --- DB utilities ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        status TEXT,
        notes TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY,
        name TEXT,
        role TEXT,
        department_id INTEGER,
        present INTEGER DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY,
        type TEXT,
        description TEXT,
        timestamp TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        incident_id INTEGER,
        title TEXT,
        assigned_to INTEGER,
        status TEXT,
        timestamp TEXT
    )""")

    conn.commit()
    return conn

conn = init_db()

def query_df(query, params=()):
    return pd.read_sql_query(query, conn, params=params)

# --- Export ---
def export_all():
    os.makedirs("exports", exist_ok=True)
    bundle = {}
    for t in ["departments","staff","incidents","tasks"]:
        df = query_df(f"SELECT * FROM {t}")
        df.to_csv(f"exports/{t}.csv", index=False)
        bundle[t] = df.to_dict(orient="records")
    with open("exports/bundle.json","w") as f:
        json.dump(bundle, f, indent=2)
    return os.listdir("exports")

# --- UI ---
st.title("🏥 HOSCON – Hospital Situational Control")

menu = st.sidebar.radio("Navigation", [
    "Dashboard", "Role & Tasks", "Incidents", "Staff Muster", "Export"
])

if menu == "Dashboard":
    st.subheader("Department Status")
    df = query_df("SELECT * FROM departments")
    st.dataframe(df)

    dept = st.selectbox("Select Department", df["name"])
    status = st.radio("Status", ["Green","Yellow","Red"])
    notes = st.text_area("Notes")
    if st.button("Update Department"):
        conn.execute("UPDATE departments SET status=?, notes=? WHERE name=?",
                     (status, notes, dept))
        conn.commit()
        st.success("Updated!")
        st.dataframe(query_df("SELECT * FROM departments"))

elif menu == "Role & Tasks":
    st.subheader("Assign Roles / Create Tasks")
    staff = query_df("SELECT * FROM staff")
    staff_name = st.selectbox("Assign To", staff["name"] if not staff.empty else [])
    inc_type = st.text_input("Incident Type")
    inc_desc = st.text_area("Incident Description")
    if st.button("Log Incident"):
        ts = datetime.utcnow().isoformat()
        conn.execute("INSERT INTO incidents(type,description,timestamp) VALUES (?,?,?)",
                     (inc_type, inc_desc, ts))
        inc_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO tasks(incident_id,title,assigned_to,status,timestamp) VALUES (?,?,?,?,?)",
                     (inc_id,"Initial Response",
                      staff[staff["name"]==staff_name]["id"].values[0] if not staff.empty else None,
                      "Open", ts))
        conn.commit()
        st.success("Incident logged.")

elif menu == "Incidents":
    st.subheader("Incidents & Tasks")
    st.dataframe(query_df("SELECT * FROM incidents"))
    tasks = query_df("SELECT * FROM tasks")
    st.dataframe(tasks)
    if not tasks.empty:
        task_id = st.selectbox("Select Task", tasks["id"])
        new_status = st.radio("Update Status", ["Open","In Progress","Completed"])
        if st.button("Update Task"):
            conn.execute("UPDATE tasks SET status=?, timestamp=? WHERE id=?",
                         (new_status, datetime.utcnow().isoformat(), task_id))
            conn.commit()
            st.success("Task updated.")
            st.dataframe(query_df("SELECT * FROM tasks"))

elif menu == "Staff Muster":
    st.subheader("Staff Check-in")

    st.subheader("Register New Staff")
    new_staff_name = st.text_input("New Staff Name")
    new_staff_role = st.text_input("New Staff Role")
    dept_list = query_df("SELECT * FROM departments")
    new_staff_dept_id = st.selectbox("New Staff Department", dept_list["id"] if not dept_list.empty else [])
    if st.button("Add New Staff"):
        if new_staff_name and new_staff_role and new_staff_dept_id:
            try:
                conn.execute("INSERT INTO staff(name, role, department_id, present) VALUES (?, ?, ?, ?)",
                             (new_staff_name, new_staff_role, new_staff_dept_id, 0))
                conn.commit()
                st.success(f"Staff member {new_staff_name} added.")
            except sqlite3.IntegrityError:
                st.error(f"Staff member {new_staff_name} already exists.")
        else:
            st.warning("Please fill in all fields to add new staff.")

    st.subheader("Update Existing Staff Status")
    staff = query_df("SELECT * FROM staff")
    staff_to_update_name = st.selectbox("Select Staff to Update", staff["name"] if not staff.empty else [])
    if staff_to_update_name:
        current_staff_info = staff[staff["name"] == staff_to_update_name].iloc[0]
        updated_role = st.text_input("Role", value=current_staff_info["role"])
        updated_dept_id = st.selectbox("Department", dept_list["id"] if not dept_list.empty else [], index=dept_list[dept_list["id"] == current_staff_info["department_id"]].index[0] if not dept_list.empty else 0)
        updated_present = st.checkbox("Present?", value=bool(current_staff_info["present"]))

        if st.button("Update Staff Status"):
            staff_id_to_update = current_staff_info["id"]
            conn.execute("UPDATE staff SET role=?, department_id=?, present=? WHERE id=?",
                         (updated_role, updated_dept_id, int(updated_present), staff_id_to_update))
            conn.commit()
            st.success(f"Staff member {staff_to_update_name} updated.")

    st.subheader("All Staff")
    st.dataframe(query_df("SELECT * FROM staff"))


elif menu == "Export":
    st.subheader("Export Data")
    if st.button("Export to CSV + JSON"):
        files = export_all()
        st.write("Exported files:", files)
        st.info("Use the file browser to download from the `exports/` folder.")
