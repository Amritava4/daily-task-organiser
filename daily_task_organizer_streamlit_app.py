# streamlit_app.py

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from datetime import date, datetime, timedelta
import os
import glob

# -------------------- Config --------------------
DATA_DIR = "tasks_data"
HISTORY_CSV = os.path.join(DATA_DIR, "history.csv")
WEEKLY_REPORT = os.path.join(DATA_DIR, "weekly_report.txt")
MONTHLY_REPORT = os.path.join(DATA_DIR, "monthly_report.txt")

os.makedirs(DATA_DIR, exist_ok=True)

# -------------------- Utilities --------------------

def date_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def daily_file_path(d: date) -> str:
    return os.path.join(DATA_DIR, f"{date_str(d)}.txt")


def get_latest_task_file(before_date: date | None = None) -> str | None:
    """Find the most recent daily task file (optionally before a given date)."""
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.txt")))
    # remove report files
    files = [f for f in files if os.path.basename(f) not in {os.path.basename(WEEKLY_REPORT), os.path.basename(MONTHLY_REPORT)}]
    if before_date:
        cutoff = date_str(before_date)
        files = [f for f in files if os.path.basename(f) < f"{cutoff}.txt"]
    if not files:
        return None
    return files[-1]


def parse_txt_day(path: str) -> tuple[list[str], list[str]]:
    """Parse a daily .txt file into (completed, incomplete) lists.
    Supports the format written by this app or earlier CLI versions.
    """
    completed, incomplete = [], []
    if not os.path.exists(path):
        return completed, incomplete
    with open(path, "r", encoding="utf-8") as f:
        lines = [ln.strip() for ln in f.readlines()]
    section = None
    for ln in lines:
        if ln.startswith("✅ Completed Tasks"):
            section = "completed"
            continue
        if ln.startswith("❌ Incomplete Tasks"):
            section = "incomplete"
            continue
        if ln.startswith("- "):
            task = ln[2:].strip()
            if section == "completed":
                completed.append(task)
            elif section == "incomplete":
                incomplete.append(task)
    return completed, incomplete


def load_carry_over_tasks(today: date) -> list[str]:
    """Load incomplete tasks from the most recent previous file."""
    latest_path = get_latest_task_file(before_date=today)
    if not latest_path:
        return []
    _, incom = parse_txt_day(latest_path)
    return incom


def ensure_history_csv():
    if not os.path.exists(HISTORY_CSV):
        pd.DataFrame(columns=["date", "task", "status"]).to_csv(HISTORY_CSV, index=False)


def append_to_history(d: date, completed: list[str], incomplete: list[str]):
    ensure_history_csv()
    rows = []
    for t in completed:
        rows.append({"date": date_str(d), "task": t, "status": "completed"})
    for t in incomplete:
        rows.append({"date": date_str(d), "task": t, "status": "incomplete"})
    if rows:
        df_new = pd.DataFrame(rows)
        if os.path.exists(HISTORY_CSV):
            df_old = pd.read_csv(HISTORY_CSV)
            df = pd.concat([df_old, df_new], ignore_index=True)
        else:
            df = df_new
        df.to_csv(HISTORY_CSV, index=False)


def write_daily_file(d: date, completed: list[str], incomplete: list[str]):
    path = daily_file_path(d)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"===== {date_str(d)} =====\n")
        f.write("✅ Completed Tasks:\n")
        if completed:
            for t in completed:
                f.write(f"- {t}\n")
        else:
            f.write("None\n")
        f.write("❌ Incomplete Tasks:\n")
        if incomplete:
            for t in incomplete:
                f.write(f"- {t}\n")
        else:
            f.write("None\n")


def load_history() -> pd.DataFrame:
    ensure_history_csv()
    try:
        df = pd.read_csv(HISTORY_CSV)
        # coerce date
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df
    except Exception:
        return pd.DataFrame(columns=["date", "task", "status"])  # fallback


def summarize_range(df: pd.DataFrame, start: date, end: date) -> dict:
    mask = (df["date"] >= start) & (df["date"] <= end)
    sub = df.loc[mask]
    completed = (sub["status"] == "completed").sum()
    incomplete = (sub["status"] == "incomplete").sum()
    return {
        "days_tracked": len(sub["date"].unique()),
        "completed": int(completed),
        "incomplete": int(incomplete),
        "total": int(completed + incomplete),
        "completion_rate": float( (completed / (completed + incomplete) * 100) if (completed + incomplete) else 0.0 ),
    }


def save_text_report(path: str, title: str, stats: dict, start: date, end: date):
    lines = []
    lines.append(f"\n📊 {title} ({start} → {end}) 📊\n")
    if stats["total"] == 0:
        lines.append("No tasks recorded in this period.\n")
    else:
        lines.append(f"Days tracked: {stats['days_tracked']}\n")
        lines.append(f"✅ Total Completed: {stats['completed']}\n")
        lines.append(f"❌ Total Incomplete: {stats['incomplete']}\n")
        lines.append(f"📈 Completion Rate: {stats['completion_rate']:.2f}%\n")
    with open(path, "a", encoding="utf-8") as f:
        f.write("".join(lines))
        f.write("\n" + "="*40 + "\n")


# -------------------- Streamlit UI --------------------
st.set_page_config(page_title="Daily Task Organizer", page_icon="✅", layout="wide")
st.title("✅ Daily Task Organizer")
st.caption("Plan in the morning. Review at night. Track weekly & monthly with charts.")

# Sidebar controls
st.sidebar.header("Settings")
selected_date = st.sidebar.date_input("Select date", value=date.today())
show_carry_over = st.sidebar.checkbox("Auto-carry incomplete from previous day", value=True)

# Load carry-over tasks
carry_over = load_carry_over_tasks(selected_date) if show_carry_over else []

# Input new tasks
st.subheader("Today's Checklist")
col1, col2 = st.columns([2, 1])
with col1:
    new_tasks_text = st.text_area("Add NEW tasks (one per line)", height=120, placeholder="e.g. Finish assignment\nRead a book\nWorkout 30 mins")
with col2:
    st.markdown("\n")
    add_example = st.button("Add Example Tasks")

if add_example:
    example = "Finish assignment\nRead a book\nExercise"
    new_tasks_text = (new_tasks_text + "\n" + example).strip() if new_tasks_text else example

new_tasks = [t.strip() for t in (new_tasks_text.splitlines() if new_tasks_text else []) if t.strip()]

all_tasks = carry_over + new_tasks

if not all_tasks:
    st.info("No tasks yet. Add some above, or enable carry-over in the sidebar.")

# Checklist with checkboxes
completed_flags = {}
if all_tasks:
    st.write("Mark completed tasks:")
    for t in all_tasks:
        completed_flags[t] = st.checkbox(t, value=False, key=f"chk_{t}")

# Save button
save_col1, save_col2, save_col3 = st.columns([1,1,2])
with save_col1:
    save_clicked = st.button("💾 Save Day")
with save_col2:
    clear_state = st.button("Reset Checks")
if clear_state:
    for t in all_tasks:
        st.session_state[f"chk_{t}"] = False

if save_clicked and all_tasks:
    completed = [t for t, done in completed_flags.items() if done]
    incomplete = [t for t, done in completed_flags.items() if not done]
    # persist files
    write_daily_file(selected_date, completed, incomplete)
    append_to_history(selected_date, completed, incomplete)
    st.success(f"Saved {len(completed)} completed and {len(incomplete)} incomplete tasks for {date_str(selected_date)}.")
    st.stop()

st.divider()

# -------------------- Reports & Charts --------------------
st.header("Reports & Charts")

df_hist = load_history()
if df_hist.empty:
    st.info("No history yet. Save at least one day to see reports.")
else:
    today = selected_date
    week_start = today - timedelta(days=6)
    month_start = today.replace(day=1)

    stats_week = summarize_range(df_hist, week_start, today)
    stats_month = summarize_range(df_hist, month_start, today)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Days Tracked (W)", stats_week["days_tracked"])
    c2.metric("Completed (W)", stats_week["completed"])
    c3.metric("Incomplete (W)", stats_week["incomplete"])
    c4.metric("Completion % (W)", f"{stats_week['completion_rate']:.1f}%")
    c5.metric("Total (W)", stats_week["total"])

    d1, d2, d3, d4, d5 = st.columns(5)
    d1.metric("Days Tracked (M)", stats_month["days_tracked"])
    d2.metric("Completed (M)", stats_month["completed"])
    d3.metric("Incomplete (M)", stats_month["incomplete"])
    d4.metric("Completion % (M)", f"{stats_month['completion_rate']:.1f}%")
    d5.metric("Total (M)", stats_month["total"])

    st.subheader("Weekly Chart: Completed vs Incomplete")
    # Bar chart via matplotlib
    fig1, ax1 = plt.subplots()
    ax1.bar(["Completed", "Incomplete"], [stats_week["completed"], stats_week["incomplete"]])
    ax1.set_ylabel("Tasks")
    ax1.set_title(f"Week {week_start} → {today}")
    st.pyplot(fig1)

    st.subheader("Monthly Chart: Completed vs Incomplete")
    fig2, ax2 = plt.subplots()
    ax2.bar(["Completed", "Incomplete"], [stats_month["completed"], stats_month["incomplete"]])
    ax2.set_ylabel("Tasks")
    ax2.set_title(f"Month {month_start} → {today}")
    st.pyplot(fig2)

    # Save text reports buttons
    colA, colB = st.columns(2)
    with colA:
        if st.button("📝 Save Weekly Text Report"):
            save_text_report(WEEKLY_REPORT, "Weekly Report", stats_week, week_start, today)
            st.success(f"Saved to {WEEKLY_REPORT}")
    with colB:
        if st.button("📝 Save Monthly Text Report"):
            save_text_report(MONTHLY_REPORT, "Monthly Report", stats_month, month_start, today)
            st.success(f"Saved to {MONTHLY_REPORT}")

    # Download history CSV
    st.download_button(
        label="⬇️ Download Full History CSV",
        data=open(HISTORY_CSV, "rb").read(),
        file_name="task_history.csv",
        mime="text/csv",
    )

st.divider()

# -------------------- Footer --------------------
st.caption("Pro tip: Use one task per line. Re-run daily; incomplete tasks auto-carry to the next day.")
