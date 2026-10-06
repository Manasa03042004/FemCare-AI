from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import sqlite3
import secrets
import hashlib
from functools import wraps
from datetime import date, datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from recommendation_engine import build_wellness_plan, build_personalized_meal_plan
from recipe_data import RECIPE_BY_SLUG

app = Flask(__name__)
app.secret_key = "femcare_ai_secret_key"
app.config["SATTVIC_UPLOAD_FOLDER"] = os.path.join("static", "uploads", "sattvic")
os.makedirs(app.config["SATTVIC_UPLOAD_FOLDER"], exist_ok=True)


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect("femcare.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # -----------------------------------------------------
    # USERS
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)


    # -----------------------------------------------------
    # MOBILE API TOKENS
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            last_used_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -----------------------------------------------------
    # HEALTH CONNECT SYNC DATA
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_sync_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            steps INTEGER DEFAULT 0,
            distance_meters REAL DEFAULT 0,
            active_calories REAL DEFAULT 0,
            exercise_minutes INTEGER DEFAULT 0,
            sleep_minutes INTEGER DEFAULT 0,
            source TEXT DEFAULT 'health_connect',
            synced_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, log_date),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -----------------------------------------------------
    # HEALTH PROFILES
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            pregnancies INTEGER,
            glucose INTEGER,
            blood_pressure INTEGER,
            skin_thickness INTEGER,
            insulin INTEGER,
            bmi REAL,
            diabetes_pedigree REAL,
            age INTEGER,
            height_cm REAL,
            weight INTEGER,
            cycle_length INTEGER,
            hair_growth INTEGER,
            skin_darkening INTEGER,
            weight_gain INTEGER,
            hemoglobin REAL,
            fatigue INTEGER,
            dizziness INTEGER,
            pale_skin INTEGER,
            thyroid_weight INTEGER,
            thyroid_fatigue INTEGER,
            hair_loss INTEGER,
            mood_swings INTEGER,
            screening_diabetes INTEGER DEFAULT 1,
            screening_pcos INTEGER DEFAULT 1,
            screening_anemia INTEGER DEFAULT 1,
            screening_thyroid INTEGER DEFAULT 1,
            diet_preference TEXT DEFAULT 'Vegetarian',
            allergies TEXT DEFAULT '',
            food_dislikes TEXT DEFAULT '',
            profile_completed INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -----------------------------------------------------
    # HEALTH PROFILE PREFERENCE MIGRATION
    # -----------------------------------------------------
    existing_columns = {
        row["name"]
        for row in cursor.execute(
            "PRAGMA table_info(health_profiles)"
        ).fetchall()
    }

    for column_name, column_type, default_value in [
        ("height_cm", "REAL", "NULL"),
        ("screening_diabetes", "INTEGER", "1"),
        ("screening_pcos", "INTEGER", "1"),
        ("screening_anemia", "INTEGER", "1"),
        ("screening_thyroid", "INTEGER", "1"),
        ("diet_preference", "TEXT", "'Vegetarian'"),
        ("allergies", "TEXT", "''"),
        ("food_dislikes", "TEXT", "''"),
        ("sattvic_enabled", "INTEGER", "0")
    ]:
        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE health_profiles "
                f"ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"
            )

    # -----------------------------------------------------
    # SATTVIC DAILY TRACKING
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sattvic_daily_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            sunlight_completed INTEGER DEFAULT 0,
            sunlight_minutes INTEGER DEFAULT 0,
            morning_water_completed INTEGER DEFAULT 0,
            breakfast_completed INTEGER DEFAULT 0,
            snack_completed INTEGER DEFAULT 0,
            lunch_completed INTEGER DEFAULT 0,
            evening_completed INTEGER DEFAULT 0,
            dinner_completed INTEGER DEFAULT 0,
            movement_completed INTEGER DEFAULT 0,
            progress_photo TEXT,
            notes TEXT DEFAULT "",
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, log_date),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -----------------------------------------------------
    # HEALTH PREDICTIONS
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS health_predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            diabetes_percentage INTEGER,
            pcos_percentage INTEGER,
            anemia_percentage INTEGER,
            thyroid_percentage INTEGER,
            diabetes_prediction INTEGER,
            pcos_prediction INTEGER,
            anemia_prediction INTEGER,
            thyroid_prediction INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -----------------------------------------------------
    # WATER
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS water_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            glasses INTEGER DEFAULT 0,
            total_ml INTEGER DEFAULT 0,
            UNIQUE(user_id, log_date),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -----------------------------------------------------
    # ACTIVITY CHECKLIST
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            activity_name TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            UNIQUE(user_id, log_date, activity_name),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -----------------------------------------------------
    # STEPS
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS steps_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            steps INTEGER DEFAULT 0,
            UNIQUE(user_id, log_date),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -----------------------------------------------------
    # STRESS
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stress_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            log_date TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            minutes INTEGER DEFAULT 0,
            UNIQUE(user_id, log_date, activity_type),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -----------------------------------------------------
    # MENSTRUAL CYCLE
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS menstrual_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT,
            cycle_length INTEGER DEFAULT 28,
            flow TEXT,
            mood TEXT,
            symptoms TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # -----------------------------------------------------
    # DOCTORS
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialization TEXT NOT NULL,
            clinic TEXT NOT NULL,
            address TEXT NOT NULL,
            experience TEXT NOT NULL,
            phone TEXT
        )
    """)

    # -----------------------------------------------------
    # APPOINTMENTS
    # -----------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            doctor_id INTEGER NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'Requested',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        )
    """)

    # -----------------------------------------------------
    # SEED DOCTORS
    # -----------------------------------------------------
    cursor.execute("SELECT COUNT(*) AS count FROM doctors")

    if cursor.fetchone()["count"] == 0:

        doctors = [
            (
                "Dr. Ananya Rao",
                "Gynecologist",
                "WomenCare Clinic",
                "MG Road, Bengaluru",
                "12 years",
                "080-4000-1001"
            ),
            (
                "Dr. Priya Sharma",
                "Endocrinologist",
                "Wellness Medical Centre",
                "Indiranagar, Bengaluru",
                "10 years",
                "080-4000-1002"
            ),
            (
                "Dr. Meera Nair",
                "Gynecologist & Women's Health",
                "FemHealth Hospital",
                "Koramangala, Bengaluru",
                "15 years",
                "080-4000-1003"
            ),
            (
                "Dr. Kavya Iyer",
                "Nutrition & Lifestyle Medicine",
                "HealthyHer Clinic",
                "Jayanagar, Bengaluru",
                "8 years",
                "080-4000-1004"
            )
        ]

        cursor.executemany("""
            INSERT INTO doctors
            (name, specialization, clinic, address, experience, phone)
            VALUES (?, ?, ?, ?, ?, ?)
        """, doctors)

    conn.commit()
    conn.close()


# =========================================================
# LOGIN REQUIRED
# =========================================================

def login_required(route_function):

    @wraps(route_function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        return route_function(*args, **kwargs)

    return wrapper


# =========================================================
# MACHINE LEARNING MODELS
# =========================================================

def load_diabetes_model():
    """
    Load the diabetes model. If the repository still contains the old
    8-feature model, automatically retrain the new 6-feature binary-risk
    model from diabetes.csv so the app and questionnaire stay compatible.
    """
    model = joblib.load("diabetes_model.pkl")

    if getattr(model, "n_features_in_", None) == 6:
        return model

    data = pd.read_csv("diabetes.csv")

    X = pd.DataFrame({
        "high_glucose": (data["Glucose"] >= 126).astype(int),
        "high_blood_pressure": (data["BloodPressure"] >= 80).astype(int),
        "high_insulin": (data["Insulin"] >= 166).astype(int),
        "pregnancy_history": (data["Pregnancies"] > 0).astype(int),
        "bmi_risk": (data["BMI"] >= 25).astype(int),
        "age_risk": (data["Age"] >= 45).astype(int)
    })

    y = data["Outcome"]

    X_train, _, y_train, _ = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=6,
        random_state=42,
        class_weight="balanced"
    )
    model.fit(X_train, y_train)
    joblib.dump(model, "diabetes_model.pkl")

    print("Diabetes model upgraded to the new 6-feature Yes/No risk model.")

    return model


diabetes_model = load_diabetes_model()
pcos_model = joblib.load("pcos_model.pkl")
anemia_model = joblib.load("anemia_model.pkl")
thyroid_model = joblib.load("thyroid_model.pkl")


# =========================================================
# HELPERS
# =========================================================

def today_string():
    return date.today().isoformat()


def risk_level(percentage):

    if percentage < 30:
        return "Low Risk"

    if percentage < 70:
        return "Moderate Risk"

    return "High Risk"


def safe_percent(value):
    return max(0, min(100, int(value or 0)))




# =========================================================
# MOBILE API / HEALTH CONNECT SYNC
# =========================================================

def _hash_api_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _issue_api_token(user_id):
    token = secrets.token_urlsafe(48)
    token_hash = _hash_api_token(token)
    expires_at = datetime.utcnow() + timedelta(days=90)

    conn = get_db()
    conn.execute(
        "INSERT INTO api_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
        (user_id, token_hash, expires_at.isoformat())
    )
    conn.commit()
    conn.close()
    return token, expires_at


def _api_user():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None

    raw_token = header.split(" ", 1)[1].strip()
    if not raw_token:
        return None

    token_hash = _hash_api_token(raw_token)
    conn = get_db()
    row = conn.execute("""
        SELECT api_tokens.user_id, api_tokens.expires_at
        FROM api_tokens
        WHERE token_hash=?
    """, (token_hash,)).fetchone()

    if not row:
        conn.close()
        return None

    try:
        expires_at = datetime.fromisoformat(row["expires_at"])
    except (TypeError, ValueError):
        conn.close()
        return None

    if expires_at <= datetime.utcnow():
        conn.close()
        return None

    conn.execute(
        "UPDATE api_tokens SET last_used_at=CURRENT_TIMESTAMP WHERE token_hash=?",
        (token_hash,)
    )
    conn.commit()
    conn.close()
    return row["user_id"]


def _api_auth_required():
    user_id = _api_user()
    if user_id is None:
        return None, (jsonify({
            "success": False,
            "error": "Unauthorized. Please login again from the FemCare Android app."
        }), 401)
    return user_id, None


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))

    if not username or not password:
        return jsonify({
            "success": False,
            "error": "Username and password are required."
        }), 400

    conn = get_db()
    user = conn.execute("""
        SELECT id, username, password
        FROM users
        WHERE username=?
    """, (username,)).fetchone()
    conn.close()

    if not user or not check_password_hash(user["password"], password):
        return jsonify({
            "success": False,
            "error": "Invalid username or password."
        }), 401

    token, expires_at = _issue_api_token(user["id"])

    return jsonify({
        "success": True,
        "user_id": user["id"],
        "username": user["username"],
        "token": token,
        "expires_at": expires_at.isoformat()
    })


@app.route("/api/health-sync", methods=["POST"])
def api_health_sync():
    user_id, error = _api_auth_required()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    log_date = str(data.get("date", today_string())).strip()

    try:
        parsed_date = datetime.strptime(log_date, "%Y-%m-%d").date()
        log_date = parsed_date.isoformat()
        steps = max(0, int(data.get("steps", 0)))
        distance_meters = max(0.0, float(data.get("distance_meters", 0)))
        active_calories = max(0.0, float(data.get("active_calories", 0)))
        exercise_minutes = max(0, int(data.get("exercise_minutes", 0)))
        sleep_minutes = max(0, int(data.get("sleep_minutes", 0)))
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "error": "Invalid sync payload."
        }), 400

    conn = get_db()

    conn.execute("""
        INSERT INTO health_sync_logs (
            user_id, log_date, steps, distance_meters,
            active_calories, exercise_minutes, sleep_minutes,
            source, synced_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, 'health_connect', CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, log_date)
        DO UPDATE SET
            steps=excluded.steps,
            distance_meters=excluded.distance_meters,
            active_calories=excluded.active_calories,
            exercise_minutes=excluded.exercise_minutes,
            sleep_minutes=excluded.sleep_minutes,
            source='health_connect',
            synced_at=CURRENT_TIMESTAMP
    """, (
        user_id, log_date, steps, distance_meters,
        active_calories, exercise_minutes, sleep_minutes
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "date": log_date,
        "steps": steps,
        "distance_meters": distance_meters,
        "active_calories": active_calories,
        "exercise_minutes": exercise_minutes,
        "sleep_minutes": sleep_minutes,
        "source": "health_connect"
    })


@app.route("/api/activity/today", methods=["GET"])
def api_activity_today():
    user_id, error = _api_auth_required()
    if error:
        return error

    day = today_string()
    conn = get_db()
    synced = conn.execute("""
        SELECT *
        FROM health_sync_logs
        WHERE user_id=? AND log_date=?
    """, (user_id, day)).fetchone()

    manual = conn.execute("""
        SELECT steps
        FROM steps_logs
        WHERE user_id=? AND log_date=?
    """, (user_id, day)).fetchone()
    conn.close()

    if synced:
        payload = dict(synced)
        payload["source"] = "health_connect"
    else:
        payload = {
            "log_date": day,
            "steps": int(manual["steps"]) if manual else 0,
            "distance_meters": 0,
            "active_calories": 0,
            "exercise_minutes": 0,
            "sleep_minutes": 0,
            "source": "manual"
        }

    return jsonify({"success": True, "activity": payload})


@app.route("/api/activity/weekly", methods=["GET"])
def api_activity_weekly():
    user_id, error = _api_auth_required()
    if error:
        return error

    end_day = date.today()
    start_day = end_day - timedelta(days=6)

    conn = get_db()
    synced_rows = conn.execute("""
        SELECT *
        FROM health_sync_logs
        WHERE user_id=? AND log_date BETWEEN ? AND ?
        ORDER BY log_date
    """, (user_id, start_day.isoformat(), end_day.isoformat())).fetchall()
    conn.close()

    return jsonify({
        "success": True,
        "start_date": start_day.isoformat(),
        "end_date": end_day.isoformat(),
        "days": [dict(row) for row in synced_rows]
    })


@app.route("/api/logout", methods=["POST"])
def api_logout():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return jsonify({"success": True})

    token_hash = _hash_api_token(header.split(" ", 1)[1].strip())
    conn = get_db()
    conn.execute("DELETE FROM api_tokens WHERE token_hash=?", (token_hash,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.")
            return redirect(url_for("register"))

        try:

            conn = get_db()

            conn.execute(
                """
                INSERT INTO users (username, password)
                VALUES (?, ?)
                """,
                (
                    username,
                    generate_password_hash(password)
                )
            )

            conn.commit()
            conn.close()

            flash("Account created successfully. Please login.")

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:

            flash("Username already exists.")

            return redirect(url_for("register"))

    return render_template("register.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db()

        user = conn.execute(
            """
            SELECT id, username, password
            FROM users
            WHERE username = ?
            """,
            (username,)
        ).fetchone()

        profile = None

        if user:

            profile = conn.execute(
                """
                SELECT profile_completed
                FROM health_profiles
                WHERE user_id = ?
                """,
                (user["id"],)
            ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):

            session["user_id"] = user["id"]
            session["username"] = user["username"]

            if profile is None or profile["profile_completed"] == 0:
                return redirect(url_for("health_assessment"))

            return redirect(url_for("dashboard"))

        flash("Invalid username or password.")

        return redirect(url_for("login"))

    return render_template("login.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out successfully.")

    return redirect(url_for("login"))


# =========================================================
# HEALTH ASSESSMENT
# =========================================================

@app.route("/health-assessment")
@login_required
def health_assessment():

    # The assessment can also be reopened by existing users
    # so they can update their profile or choose different screenings.
    return render_template("index.html")


# =========================================================
# PREDICT + SAVE HEALTH PROFILE
# =========================================================

@app.route("/predict", methods=["POST"])
@login_required
def predict():

    # -----------------------------------------------------
    # BASIC PROFILE + SCREENING CHOICES
    # -----------------------------------------------------

    screening_diabetes = request.form.get("screening_diabetes") == "1"
    screening_pcos = request.form.get("screening_pcos") == "1"
    screening_anemia = request.form.get("screening_anemia") == "1"
    screening_thyroid = request.form.get("screening_thyroid") == "1"

    try:
        age = int(request.form["basic_age"])
        height_cm = float(request.form["height_cm"])
        weight = int(request.form["basic_weight"])
        cycle_length = int(request.form["basic_cycle_length"])

        if age < 13 or age > 100:
            raise ValueError("Invalid age")

        if height_cm < 100 or height_cm > 250:
            raise ValueError("Invalid height")

        if weight < 25 or weight > 300:
            raise ValueError("Invalid weight")

        if cycle_length < 15 or cycle_length > 90:
            raise ValueError("Invalid cycle length")

        # BMI is calculated from height and weight and stored automatically.
        bmi = round(
            weight / ((height_cm / 100) ** 2),
            1
        )

        # The BMI value displayed in About You is the same server-side
        # value used by the prediction model and saved in health_profiles.

        # Diabetes now uses simple Yes/No wellness questions.
        diabetes_high_glucose = int(request.form.get("diabetes_high_glucose", 0))
        diabetes_high_bp = int(request.form.get("diabetes_high_bp", 0))
        diabetes_high_insulin = int(request.form.get("diabetes_high_insulin", 0))
        diabetes_pregnancy_history = int(request.form.get("diabetes_pregnancy_history", 0))

        # Legacy database columns are retained for compatibility.
        pregnancies = diabetes_pregnancy_history
        glucose = 0
        blood_pressure = 0
        skin_thickness = 0
        insulin = 0
        diabetes_pedigree = 0.0

        hair_growth = int(request.form.get("hair_growth", 0))
        skin_darkening = int(request.form.get("skin_darkening", 0))
        weight_gain = int(request.form.get("weight_gain", 0))

        hemoglobin = float(request.form.get("hemoglobin", 0))
        fatigue = int(request.form.get("fatigue", 0))
        dizziness = int(request.form.get("dizziness", 0))
        pale_skin = int(request.form.get("pale_skin", 0))

        thyroid_weight = int(request.form.get("thyroid_weight", 0))
        thyroid_fatigue = int(request.form.get("thyroid_fatigue", 0))
        hair_loss = int(request.form.get("hair_loss", 0))
        mood_swings = int(request.form.get("mood_swings", 0))

        diet_preference = request.form.get(
            "diet_preference",
            "Vegetarian"
        ).strip() or "Vegetarian"

        allergy_values = request.form.getlist("allergies")
        if "none" in allergy_values:
            allergy_values = []

        allergy_other = request.form.get(
            "allergy_other",
            ""
        ).strip()

        if allergy_other:
            allergy_values.append(
                f"other: {allergy_other}"
            )

        allergies = ", ".join(allergy_values)

        food_dislikes = request.form.get(
            "food_dislikes",
            ""
        ).strip()

        sattvic_enabled = 1 if request.form.get("sattvic_enabled") == "1" else 0

        # Server-side validation mirrors the progressive UI.
        # Only the selected screening needs its disease-specific data.
        if screening_diabetes:
            for flag in (
                diabetes_high_glucose,
                diabetes_high_bp,
                diabetes_high_insulin,
                diabetes_pregnancy_history
            ):
                if flag not in (0, 1):
                    raise ValueError("Invalid diabetes screening values")

        if screening_anemia:
            if hemoglobin <= 0:
                raise ValueError("Invalid hemoglobin")

        if screening_thyroid:
            if thyroid_fatigue not in (0, 1) or hair_loss not in (0, 1) or mood_swings not in (0, 1):
                raise ValueError("Invalid thyroid screening values")

        if screening_pcos:
            if hair_growth not in (0, 1) or skin_darkening not in (0, 1) or weight_gain not in (0, 1):
                raise ValueError("Invalid PCOS screening values")

    except (KeyError, ValueError, ZeroDivisionError):

        flash("Please enter valid values in the required fields.")

        return redirect(url_for("health_assessment"))

    # -----------------------------------------------------
    # RUN ONLY THE SCREENINGS CHOSEN BY THE USER
    # -----------------------------------------------------

    diabetes_prediction = np.array([0])
    diabetes_percentage = 0

    if screening_diabetes:
        diabetes_input = np.array([[
            diabetes_high_glucose,
            diabetes_high_bp,
            diabetes_high_insulin,
            diabetes_pregnancy_history,
            int(bmi >= 25),
            int(age >= 45)
        ]])

        diabetes_prediction = diabetes_model.predict(diabetes_input)

        diabetes_prob = diabetes_model.predict_proba(
            diabetes_input
        )[0][1]

        diabetes_percentage = safe_percent(
            diabetes_prob * 100
        )

    pcos_prediction = np.array([0])
    pcos_percentage = 0

    if screening_pcos:
        pcos_input = np.array([[
            age,
            weight,
            cycle_length,
            hair_growth,
            skin_darkening,
            weight_gain
        ]])

        pcos_prediction = pcos_model.predict(pcos_input)

        pcos_prob = pcos_model.predict_proba(
            pcos_input
        )[0][1]

        pcos_percentage = safe_percent(
            pcos_prob * 100
        )

    anemia_prediction = np.array([0])
    anemia_percentage = 0

    if screening_anemia:
        anemia_input = np.array([[
            age,
            hemoglobin,
            fatigue,
            dizziness,
            pale_skin
        ]])

        anemia_prediction = anemia_model.predict(anemia_input)

        anemia_prob = anemia_model.predict_proba(
            anemia_input
        )[0][1]

        anemia_percentage = safe_percent(
            anemia_prob * 100
        )

    thyroid_prediction = np.array([0])
    thyroid_percentage = 0

    if screening_thyroid:
        thyroid_input = np.array([[
            age,
            thyroid_weight,
            thyroid_fatigue,
            hair_loss,
            mood_swings
        ]])

        thyroid_prediction = thyroid_model.predict(thyroid_input)

        thyroid_prob = thyroid_model.predict_proba(
            thyroid_input
        )[0][1]

        thyroid_percentage = safe_percent(
            thyroid_prob * 100
        )

    # -----------------------------------------------------
    # DIET SUGGESTION
    # -----------------------------------------------------

    diet_suggestion = []

    if diabetes_prediction[0] == 1:
        diet_suggestion.append(
            "Prefer balanced, lower-added-sugar meals."
        )

    if pcos_prediction[0] == 1:
        diet_suggestion.append(
            "Choose balanced meals with vegetables, protein and high-fibre carbohydrates."
        )

    if anemia_prediction[0] == 1:
        diet_suggestion.append(
            "Include iron-rich foods and discuss abnormal results with a clinician."
        )

    if thyroid_prediction[0] == 1:
        diet_suggestion.append(
            "Use a balanced diet and seek medical evaluation for thyroid symptoms."
        )

    if not diet_suggestion:

        diet_suggestion.append(
            "Maintain a balanced diet, regular activity and adequate sleep."
        )

    # -----------------------------------------------------
    # SAVE PROFILE
    # -----------------------------------------------------

    conn = get_db()

    conn.execute("""
        INSERT INTO health_profiles (
            user_id,
            pregnancies,
            glucose,
            blood_pressure,
            skin_thickness,
            insulin,
            bmi,
            diabetes_pedigree,
            age,
            height_cm,
            weight,
            cycle_length,
            hair_growth,
            skin_darkening,
            weight_gain,
            hemoglobin,
            fatigue,
            dizziness,
            pale_skin,
            thyroid_weight,
            thyroid_fatigue,
            hair_loss,
            mood_swings,
            screening_diabetes,
            screening_pcos,
            screening_anemia,
            screening_thyroid,
            diet_preference,
            allergies,
            food_dislikes,
            profile_completed
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1
        )

        ON CONFLICT(user_id)
        DO UPDATE SET
            pregnancies=excluded.pregnancies,
            glucose=excluded.glucose,
            blood_pressure=excluded.blood_pressure,
            skin_thickness=excluded.skin_thickness,
            insulin=excluded.insulin,
            bmi=excluded.bmi,
            diabetes_pedigree=excluded.diabetes_pedigree,
            age=excluded.age,
            height_cm=excluded.height_cm,
            weight=excluded.weight,
            cycle_length=excluded.cycle_length,
            hair_growth=excluded.hair_growth,
            skin_darkening=excluded.skin_darkening,
            weight_gain=excluded.weight_gain,
            hemoglobin=excluded.hemoglobin,
            fatigue=excluded.fatigue,
            dizziness=excluded.dizziness,
            pale_skin=excluded.pale_skin,
            thyroid_weight=excluded.thyroid_weight,
            thyroid_fatigue=excluded.thyroid_fatigue,
            hair_loss=excluded.hair_loss,
            mood_swings=excluded.mood_swings,
            screening_diabetes=excluded.screening_diabetes,
            screening_pcos=excluded.screening_pcos,
            screening_anemia=excluded.screening_anemia,
            screening_thyroid=excluded.screening_thyroid,
            diet_preference=excluded.diet_preference,
            allergies=excluded.allergies,
            food_dislikes=excluded.food_dislikes,
            profile_completed=1
    """, (
        session["user_id"],
        pregnancies,
        glucose,
        blood_pressure,
        skin_thickness,
        insulin,
        bmi,
        diabetes_pedigree,
        age,
        height_cm,
        weight,
        cycle_length,
        hair_growth,
        skin_darkening,
        weight_gain,
        hemoglobin,
        fatigue,
        dizziness,
        pale_skin,
        thyroid_weight,
        thyroid_fatigue,
        hair_loss,
        mood_swings,
        int(screening_diabetes),
        int(screening_pcos),
        int(screening_anemia),
        int(screening_thyroid),
        diet_preference,
        allergies,
        food_dislikes
    ))

    # Save the optional Sattvic wellness pathway separately so
    # existing health-profile rows remain compatible.
    conn.execute("""
        UPDATE health_profiles
        SET sattvic_enabled=?
        WHERE user_id=?
    """, (sattvic_enabled, session["user_id"]))

    # -----------------------------------------------------
    # SAVE PREDICTIONS
    # -----------------------------------------------------

    conn.execute("""
        INSERT INTO health_predictions (
            user_id,
            diabetes_percentage,
            pcos_percentage,
            anemia_percentage,
            thyroid_percentage,
            diabetes_prediction,
            pcos_prediction,
            anemia_prediction,
            thyroid_prediction
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            diabetes_percentage=excluded.diabetes_percentage,
            pcos_percentage=excluded.pcos_percentage,
            anemia_percentage=excluded.anemia_percentage,
            thyroid_percentage=excluded.thyroid_percentage,
            diabetes_prediction=excluded.diabetes_prediction,
            pcos_prediction=excluded.pcos_prediction,
            anemia_prediction=excluded.anemia_prediction,
            thyroid_prediction=excluded.thyroid_prediction
    """, (
        session["user_id"],
        diabetes_percentage,
        pcos_percentage,
        anemia_percentage,
        thyroid_percentage,
        int(diabetes_prediction[0]),
        int(pcos_prediction[0]),
        int(anemia_prediction[0]),
        int(thyroid_prediction[0])
    ))

    conn.commit()
    conn.close()

    return render_template(
        "result.html",
        diabetes_result=(
            f"{'⚠ High' if diabetes_prediction[0] == 1 else '✅ Low'} "
            f"Diabetes Risk ({diabetes_percentage}%)"
        ),
        pcos_result=(
            f"{'⚠ High' if pcos_prediction[0] == 1 else '✅ Low'} "
            f"PCOS Risk ({pcos_percentage}%)"
        ),
        anemia_result=(
            f"{'⚠ High' if anemia_prediction[0] == 1 else '✅ Low'} "
            f"Anemia Risk ({anemia_percentage}%)"
        ),
        thyroid_result=(
            f"{'⚠ High' if thyroid_prediction[0] == 1 else '✅ Low'} "
            f"Thyroid Risk ({thyroid_percentage}%)"
        ),
        diabetes_percentage=diabetes_percentage,
        pcos_percentage=pcos_percentage,
        anemia_percentage=anemia_percentage,
        thyroid_percentage=thyroid_percentage,
        diabetes_prediction=int(diabetes_prediction[0]),
        pcos_prediction=int(pcos_prediction[0]),
        anemia_prediction=int(anemia_prediction[0]),
        thyroid_prediction=int(thyroid_prediction[0]),
        screening_diabetes=screening_diabetes,
        screening_pcos=screening_pcos,
        screening_anemia=screening_anemia,
        screening_thyroid=screening_thyroid,
        diet_suggestion=diet_suggestion
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
@login_required
def dashboard():

    user_id = session["user_id"]
    today = today_string()

    conn = get_db()

    # -----------------------------------------------------
    # HEALTH PREDICTIONS
    # -----------------------------------------------------

    prediction = conn.execute("""
        SELECT *
        FROM health_predictions
        WHERE user_id=?
    """, (user_id,)).fetchone()

    profile = conn.execute("""
        SELECT *
        FROM health_profiles
        WHERE user_id=?
    """, (user_id,)).fetchone()

    if prediction is None or profile is None:

        conn.close()

        return redirect(url_for("health_assessment"))

    # -----------------------------------------------------
    # WATER
    # -----------------------------------------------------

    water = conn.execute("""
        SELECT glasses, total_ml
        FROM water_logs
        WHERE user_id=? AND log_date=?
    """, (user_id, today)).fetchone()

    water_glasses = water["glasses"] if water else 0

    water_progress = min(
        100,
        int((water_glasses / 8) * 100)
    )

    # -----------------------------------------------------
    # STEPS
    # -----------------------------------------------------

    synced_steps = conn.execute("""
        SELECT steps, distance_meters, active_calories,
               exercise_minutes, sleep_minutes, synced_at
        FROM health_sync_logs
        WHERE user_id=? AND log_date=?
    """, (user_id, today)).fetchone()

    steps_data = conn.execute("""
        SELECT steps
        FROM steps_logs
        WHERE user_id=? AND log_date=?
    """, (user_id, today)).fetchone()

    step_count = (
        int(synced_steps["steps"])
        if synced_steps
        else (int(steps_data["steps"]) if steps_data else 0)
    )

    health_connect_synced = bool(synced_steps)
    health_connect_distance_km = (
        round(float(synced_steps["distance_meters"] or 0) / 1000, 2)
        if synced_steps else 0
    )
    health_connect_calories = (
        round(float(synced_steps["active_calories"] or 0))
        if synced_steps else 0
    )
    health_connect_exercise_minutes = (
        int(synced_steps["exercise_minutes"] or 0)
        if synced_steps else 0
    )
    health_connect_sleep_minutes = (
        int(synced_steps["sleep_minutes"] or 0)
        if synced_steps else 0
    )

    step_progress = min(
        100,
        int((step_count / 8000) * 100)
    )

    # -----------------------------------------------------
    # DIET
    # -----------------------------------------------------
    # FOUR meals:
    # Breakfast
    # Lunch
    # Evening
    # Dinner
    # -----------------------------------------------------

    meal_names = [
        "breakfast",
        "lunch",
        "evening",
        "dinner"
    ]

    meals_done = 0

    for meal in meal_names:

        row = conn.execute("""
            SELECT completed
            FROM activity_logs
            WHERE user_id=?
            AND log_date=?
            AND activity_name=?
        """, (
            user_id,
            today,
            f"meal_{meal}"
        )).fetchone()

        if row and row["completed"] == 1:
            meals_done += 1

    meal_total = len(meal_names)

    meal_progress = min(
        100,
        int((meals_done / meal_total) * 100)
    )

    # -----------------------------------------------------
    # WELLNESS ACTIVITIES
    # -----------------------------------------------------
    # IMPORTANT:
    # Meal checkboxes are NOT counted here.
    # -----------------------------------------------------

    activity_data = conn.execute("""
        SELECT COUNT(*) AS count
        FROM activity_logs
        WHERE user_id=?
        AND log_date=?
        AND completed=1
        AND activity_name NOT LIKE 'meal_%'
    """, (user_id, today)).fetchone()

    activity_done = activity_data["count"] if activity_data else 0

    activity_progress = min(
        100,
        int((activity_done / 8) * 100)
    )

    # -----------------------------------------------------
    # STRESS CONTROL
    # -----------------------------------------------------

    stress_data = conn.execute("""
        SELECT COUNT(*) AS count
        FROM stress_logs
        WHERE user_id=?
        AND log_date=?
        AND minutes > 0
    """, (user_id, today)).fetchone()

    stress_done = stress_data["count"] if stress_data else 0

    stress_progress = 100 if stress_done > 0 else 0

    # -----------------------------------------------------
    # OVERALL WELLNESS
    # -----------------------------------------------------

    wellness_progress = int(
        (
            water_progress +
            step_progress +
            meal_progress +
            activity_progress +
            stress_progress
        ) / 5
    )

    wellness_plan = build_wellness_plan(
        profile,
        prediction,
        build_personalized_meal_plan(profile, prediction)
    )

    conn.close()

    # -----------------------------------------------------
    # RENDER DASHBOARD
    # -----------------------------------------------------

    return render_template(
        "dashboard.html",

        username=session["username"],

        # -------------------------------------------------
        # HEALTH RISKS
        # -------------------------------------------------

        diabetes_percentage=prediction["diabetes_percentage"],
        pcos_percentage=prediction["pcos_percentage"],
        anemia_percentage=prediction["anemia_percentage"],
        thyroid_percentage=prediction["thyroid_percentage"],

        diabetes_risk=risk_level(
            prediction["diabetes_percentage"]
        ),

        pcos_risk=risk_level(
            prediction["pcos_percentage"]
        ),

        anemia_risk=risk_level(
            prediction["anemia_percentage"]
        ),

        thyroid_risk=risk_level(
            prediction["thyroid_percentage"]
        ),

        # -------------------------------------------------
        # WATER
        # -------------------------------------------------

        water_glasses=water_glasses,
        water_progress=water_progress,
        water_goal=8,

        # -------------------------------------------------
        # STEPS
        # -------------------------------------------------

        steps=step_count,
        step_count=step_count,
        step_goal=8000,
        step_progress=step_progress,
        health_connect_synced=health_connect_synced,
        health_connect_distance_km=health_connect_distance_km,
        health_connect_calories=health_connect_calories,
        health_connect_exercise_minutes=health_connect_exercise_minutes,
        health_connect_sleep_minutes=health_connect_sleep_minutes,

        # -------------------------------------------------
        # DIET
        # -------------------------------------------------

        meals_done=meals_done,
        meal_total=meal_total,
        meal_progress=meal_progress,

        # -------------------------------------------------
        # ACTIVITY / WELLNESS
        # -------------------------------------------------

        activity_done=activity_done,
        activity_total=8,
        activity_progress=activity_progress,

        stress_done=stress_done,
        stress_progress=stress_progress,

        wellness_progress=wellness_progress,
        wellness_plan=wellness_plan,
        sattvic_enabled=int(profile["sattvic_enabled"] or 0)
    )


# =========================================================
# SATTVIC WELLNESS
# =========================================================

SATTVIC_WATER = [
    "Ajwain warm water", "Jeera warm water",
    "Fenugreek-infused warm water", "Coriander-seed warm water",
    "Lemon water", "Mint-infused warm water", "Plain warm water"
]
SATTVIC_BREAKFASTS = [
    "Chia seed pudding with fruit", "Overnight oats with banana",
    "Ragi porridge with fruit", "Moong dal chilla with mint chutney",
    "Vegetable poha bowl", "Millet breakfast bowl",
    "Oats and apple cinnamon bowl", "Fruit and chia yogurt bowl",
    "Vegetable upma with coconut", "Besan chilla with coriander",
    "Quinoa breakfast bowl", "Warm banana oat bowl"
]
SATTVIC_SNACKS = [
    "Seasonal fruit", "Soaked almonds and fruit", "Walnuts with fruit",
    "Roasted makhana", "Fresh coconut pieces", "Fruit bowl",
    "Soaked raisins and fruit", "Dates with a small portion of nuts"
]
SATTVIC_LUNCHES = [
    "Vegetable soup + salad + dal", "Mixed vegetable soup + sprouts salad",
    "Moong dal + vegetable soup + salad", "Millet bowl + vegetables + dal",
    "Lentil soup + cucumber-carrot salad", "Vegetable khichdi + salad",
    "Ragi roti + vegetable soup + dal"
]
SATTVIC_EVENINGS = ["Tulsi tea", "Ginger tea", "Mint tea", "Lemon tea", "Cinnamon tea", "Green tea"]
SATTVIC_DINNERS = [
    "2 multigrain chapatis + dal + vegetables",
    "2 ragi chapatis + vegetable soup + dal",
    "Moong dal khichdi + vegetables",
    "2 whole-wheat chapatis + mixed vegetables + dal",
    "Millet roti + lentil soup + vegetables",
    "2 ragi rotis + sprouts curry + vegetables"
]

def sattvic_plan_for(day):
    n = day.toordinal()
    return {
        "water": SATTVIC_WATER[day.weekday()],
        "breakfast": SATTVIC_BREAKFASTS[n % len(SATTVIC_BREAKFASTS)],
        "snack": SATTVIC_SNACKS[n % len(SATTVIC_SNACKS)],
        "lunch": SATTVIC_LUNCHES[n % len(SATTVIC_LUNCHES)],
        "evening": SATTVIC_EVENINGS[n % len(SATTVIC_EVENINGS)],
        "dinner": SATTVIC_DINNERS[n % len(SATTVIC_DINNERS)]
    }

def sattvic_completion(row):
    if not row:
        return 0
    fields = [
        "sunlight_completed", "morning_water_completed", "breakfast_completed",
        "snack_completed", "lunch_completed", "evening_completed",
        "dinner_completed", "movement_completed"
    ]
    return sum(int(row[field] or 0) for field in fields)

@app.route("/sattvic")
@login_required
def sattvic():
    user_id = session["user_id"]
    today = date.today()
    conn = get_db()
    profile = conn.execute("SELECT sattvic_enabled FROM health_profiles WHERE user_id=?", (user_id,)).fetchone()
    log = conn.execute("SELECT * FROM sattvic_daily_logs WHERE user_id=? AND log_date=?", (user_id, today.isoformat())).fetchone()
    history = conn.execute("SELECT * FROM sattvic_daily_logs WHERE user_id=? ORDER BY log_date DESC LIMIT 7", (user_id,)).fetchall()
    conn.close()

    done = sattvic_completion(log)
    history_data = [{
        "date": row["log_date"],
        "done": sattvic_completion(row),
        "percent": round(sattvic_completion(row) / 8 * 100),
        "photo": row["progress_photo"]
    } for row in history]

    return render_template(
        "sattvic.html",
        enabled=bool(profile and profile["sattvic_enabled"]),
        plan=sattvic_plan_for(today),
        log=log,
        progress=round(done / 8 * 100),
        completed=done,
        history=history_data
    )

@app.route("/sattvic/save", methods=["POST"])
@login_required
def save_sattvic():
    user_id = session["user_id"]
    today = date.today().isoformat()

    def checked(name):
        return 1 if request.form.get(name) == "1" else 0

    try:
        minutes = max(0, min(120, int(request.form.get("sunlight_minutes", "0") or 0)))
    except ValueError:
        minutes = 0

    photo_path = None
    photo = request.files.get("progress_photo")
    if photo and photo.filename:
        ext = photo.filename.rsplit(".", 1)[-1].lower() if "." in photo.filename else ""
        if ext in {"jpg", "jpeg", "png", "webp"}:
            filename = secure_filename(
                f"user_{user_id}_{today}_{datetime.now().strftime('%H%M%S')}.{ext}"
            )
            photo.save(os.path.join(app.config["SATTVIC_UPLOAD_FOLDER"], filename))
            photo_path = f"uploads/sattvic/{filename}"

    conn = get_db()
    old = conn.execute("SELECT progress_photo FROM sattvic_daily_logs WHERE user_id=? AND log_date=?", (user_id, today)).fetchone()
    if not photo_path and old:
        photo_path = old["progress_photo"]

    conn.execute("""
        INSERT INTO sattvic_daily_logs (
            user_id, log_date, sunlight_completed, sunlight_minutes,
            morning_water_completed, breakfast_completed, snack_completed,
            lunch_completed, evening_completed, dinner_completed,
            movement_completed, progress_photo, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, log_date) DO UPDATE SET
            sunlight_completed=excluded.sunlight_completed,
            sunlight_minutes=excluded.sunlight_minutes,
            morning_water_completed=excluded.morning_water_completed,
            breakfast_completed=excluded.breakfast_completed,
            snack_completed=excluded.snack_completed,
            lunch_completed=excluded.lunch_completed,
            evening_completed=excluded.evening_completed,
            dinner_completed=excluded.dinner_completed,
            movement_completed=excluded.movement_completed,
            progress_photo=excluded.progress_photo,
            notes=excluded.notes,
            updated_at=CURRENT_TIMESTAMP
    """, (
        user_id, today, checked("sunlight_completed"), minutes,
        checked("morning_water_completed"), checked("breakfast_completed"),
        checked("snack_completed"), checked("lunch_completed"),
        checked("evening_completed"), checked("dinner_completed"),
        checked("movement_completed"), photo_path,
        request.form.get("notes", "").strip()[:500]
    ))
    conn.commit()
    conn.close()
    flash("🌿 Today's Sattvic routine has been saved.")
    return redirect(url_for("sattvic"))

@app.route("/sattvic/start", methods=["POST"])
@login_required
def start_sattvic():
    conn = get_db()
    conn.execute("UPDATE health_profiles SET sattvic_enabled=1 WHERE user_id=?", (session["user_id"],))
    conn.commit()
    conn.close()
    flash("🌿 Sattvic Wellness has been activated.")
    return redirect(url_for("sattvic"))

@app.route("/sattvic/stop", methods=["POST"])
@login_required
def stop_sattvic():
    conn = get_db()
    conn.execute("UPDATE health_profiles SET sattvic_enabled=0 WHERE user_id=?", (session["user_id"],))
    conn.commit()
    conn.close()
    flash("Sattvic Wellness has been paused.")
    return redirect(url_for("sattvic"))

# =========================================================
# PERSONALIZED NUTRITION ENGINE
# =========================================================
# Recommendation logic lives in recommendation_engine.py.
# The app imports it above so the same engine is used by the dashboard and diet page.


# =========================================================
# DIET
# =========================================================

@app.route("/diet", methods=["GET", "POST"])
@login_required
def diet():

    user_id = session["user_id"]
    today = today_string()

    meal_names = ["breakfast", "snack", "lunch", "evening", "dinner"]
    conn = get_db()

    if request.method == "POST":
        for meal in meal_names:
            completed = 1 if request.form.get(f"meal_{meal}") == "1" else 0
            conn.execute("""
                INSERT INTO activity_logs
                (user_id, log_date, activity_name, completed)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, log_date, activity_name)
                DO UPDATE SET completed=excluded.completed
            """, (user_id, today, f"meal_{meal}", completed))

        conn.commit()
        flash("Today's personalized meal progress has been saved.")
        conn.close()
        return redirect(url_for("diet"))

    rows = conn.execute("""
        SELECT activity_name, completed
        FROM activity_logs
        WHERE user_id=? AND log_date=? AND activity_name LIKE 'meal_%'
    """, (user_id, today)).fetchall()

    profile = conn.execute("""
        SELECT * FROM health_profiles WHERE user_id=?
    """, (user_id,)).fetchone()

    predictions = conn.execute("""
        SELECT * FROM health_predictions WHERE user_id=?
    """, (user_id,)).fetchone()

    conn.close()

    meal_status = {row["activity_name"]: row["completed"] for row in rows}
    meal_plan = build_personalized_meal_plan(profile, predictions)

    meals_done = sum(
        1 for meal in meal_names
        if meal_status.get(f"meal_{meal}", 0) == 1
    )
    meal_progress = min(100, int((meals_done / len(meal_names)) * 100))

    return render_template(
        "diet.html",
        meal_status=meal_status,
        meals_done=meals_done,
        meal_total=len(meal_names),
        meal_progress=meal_progress,
        diet_preference=meal_plan["preference"],
        allergies=meal_plan["allergies"],
        food_dislikes=meal_plan["dislikes"],
        personalized_meals=meal_plan["meals"],
        nutrition_focus=meal_plan["focus"],
        risk_flags=meal_plan["risk_flags"],
        recipe_count=meal_plan["recipe_count"]
    )


# =========================================================
# RECIPE
# =========================================================

@app.route("/recipe/<dish_name>")
@login_required
def recipe(dish_name):

    recipe_data = RECIPE_BY_SLUG.get(dish_name)

    if recipe_data is None:
        return "Recipe not found", 404

    return render_template(
        "recipe.html",
        recipe_name=recipe_data["name"],
        ingredients=recipe_data["ingredients"],
        steps=recipe_data["steps"],
        calories=recipe_data["calories"],
        protein=recipe_data["protein"],
        fiber=recipe_data["fiber"],
        iron=recipe_data["iron"]
    )


# =========================================================
# ACTIVITY
# =========================================================

@app.route("/activity", methods=["GET", "POST"])
@login_required
def activity():

    user_id = session["user_id"]
    today = today_string()

    conn = get_db()

    if request.method == "POST":

        action = request.form.get("action")

        # -------------------------------------------------
        # WATER
        # -------------------------------------------------

        if action in ["add", "remove"]:

            water = conn.execute("""
                SELECT glasses, total_ml
                FROM water_logs
                WHERE user_id=? AND log_date=?
            """, (
                user_id,
                today
            )).fetchone()

            glasses = water["glasses"] if water else 0
            total_ml = water["total_ml"] if water else 0

            if action == "add" and glasses < 8:

                glasses += 1
                total_ml += 250

            elif action == "remove" and glasses > 0:

                glasses -= 1
                total_ml -= 250

            conn.execute("""
                INSERT INTO water_logs
                (
                    user_id,
                    log_date,
                    glasses,
                    total_ml
                )
                VALUES (?, ?, ?, ?)

                ON CONFLICT(user_id, log_date)
                DO UPDATE SET
                    glasses=excluded.glasses,
                    total_ml=excluded.total_ml
            """, (
                user_id,
                today,
                glasses,
                total_ml
            ))

        # -------------------------------------------------
        # STEPS
        # -------------------------------------------------

        elif action == "save_steps":

            try:
                steps_value = max(
                    0,
                    int(
                        request.form.get(
                            "steps",
                            "0"
                        )
                    )
                )

            except ValueError:
                steps_value = 0

            conn.execute("""
                INSERT INTO steps_logs
                (
                    user_id,
                    log_date,
                    steps
                )
                VALUES (?, ?, ?)

                ON CONFLICT(user_id, log_date)
                DO UPDATE SET
                    steps=excluded.steps
            """, (
                user_id,
                today,
                steps_value
            ))

        # -------------------------------------------------
        # ACTIVITY CHECKBOX
        # -------------------------------------------------

        elif action == "save_activity":

            activity_name = request.form.get(
                "activity_name"
            )

            completed = (
                1
                if request.form.get(
                    "completed"
                ) == "1"
                else 0
            )

            if activity_name:

                conn.execute("""
                    INSERT INTO activity_logs
                    (
                        user_id,
                        log_date,
                        activity_name,
                        completed
                    )
                    VALUES (?, ?, ?, ?)

                    ON CONFLICT(
                        user_id,
                        log_date,
                        activity_name
                    )
                    DO UPDATE SET
                        completed=excluded.completed
                """, (
                    user_id,
                    today,
                    activity_name,
                    completed
                ))

        conn.commit()

    # -----------------------------------------------------
    # LOAD WATER
    # -----------------------------------------------------

    water = conn.execute("""
        SELECT glasses, total_ml
        FROM water_logs
        WHERE user_id=? AND log_date=?
    """, (
        user_id,
        today
    )).fetchone()

    # -----------------------------------------------------
    # LOAD STEPS
    # -----------------------------------------------------

    step_data = conn.execute("""
        SELECT steps
        FROM steps_logs
        WHERE user_id=? AND log_date=?
    """, (
        user_id,
        today
    )).fetchone()

    # -----------------------------------------------------
    # LOAD ACTIVITIES
    # -----------------------------------------------------

    rows = conn.execute("""
        SELECT activity_name, completed
        FROM activity_logs
        WHERE user_id=? AND log_date=?
    """, (
        user_id,
        today
    )).fetchall()

    conn.close()

    activities = {
        row["activity_name"]: row["completed"]
        for row in rows
    }

    glasses = water["glasses"] if water else 0
    total_ml = water["total_ml"] if water else 0
    steps = step_data["steps"] if step_data else 0

    return render_template(
        "activity.html",

        glasses=glasses,
        total_ml=total_ml,

        progress=min(
            100,
            int(glasses / 8 * 100)
        ),

        steps=steps,
        step_goal=8000,

        step_progress=min(
            100,
            int(steps / 8000 * 100)
        ),

        activities=activities
    )


# =========================================================
# YOGA
# =========================================================

@app.route("/yoga", methods=["GET", "POST"])
@login_required
def yoga():

    user_id = session["user_id"]
    today = today_string()

    yoga_items = [

        (
            "yoga_surya",
            "Surya Namaskar",
            "5–10 rounds",
            "Full-body mobility and gentle activity."
        ),

        (
            "yoga_bhujang",
            "Bhujangasana",
            "30–60 seconds",
            "Gentle back and chest stretching."
        ),

        (
            "yoga_setu",
            "Setu Bandhasana",
            "30–60 seconds",
            "Gentle hip and back strengthening."
        ),

        (
            "yoga_malasana",
            "Malasana",
            "20–40 seconds",
            "Gentle lower-body mobility."
        ),

        (
            "yoga_bal",
            "Balasana",
            "30–60 seconds",
            "Relaxation and gentle stretching."
        )
    ]

    conn = get_db()

    if request.method == "POST":

        name = request.form.get(
            "activity_name"
        )

        completed = (
            1
            if request.form.get(
                "completed"
            ) == "1"
            else 0
        )

        if name:

            conn.execute("""
                INSERT INTO activity_logs
                (
                    user_id,
                    log_date,
                    activity_name,
                    completed
                )
                VALUES (?, ?, ?, ?)

                ON CONFLICT(
                    user_id,
                    log_date,
                    activity_name
                )
                DO UPDATE SET
                    completed=excluded.completed
            """, (
                user_id,
                today,
                name,
                completed
            ))

            conn.commit()

    rows = conn.execute("""
        SELECT activity_name, completed
        FROM activity_logs
        WHERE user_id=? AND log_date=?
    """, (
        user_id,
        today
    )).fetchall()

    conn.close()

    status = {
        row["activity_name"]: row["completed"]
        for row in rows
    }

    return render_template(
        "yoga.html",
        yoga_items=yoga_items,
        status=status
    )


# =========================================================
# STRESS CONTROL
# =========================================================

@app.route("/stress", methods=["GET", "POST"])
@login_required
def stress():

    user_id = session["user_id"]
    today = today_string()

    conn = get_db()

    if request.method == "POST":

        activity_type = request.form.get(
            "activity_type",
            "meditation"
        )

        try:

            minutes = max(
                0,
                int(
                    request.form.get(
                        "minutes",
                        "0"
                    )
                )
            )

        except ValueError:

            minutes = 0

        if minutes > 0:

            conn.execute("""
                INSERT INTO stress_logs
                (
                    user_id,
                    log_date,
                    activity_type,
                    minutes
                )
                VALUES (?, ?, ?, ?)

                ON CONFLICT(
                    user_id,
                    log_date,
                    activity_type
                )
                DO UPDATE SET
                    minutes=excluded.minutes
            """, (
                user_id,
                today,
                activity_type,
                minutes
            ))

            conn.commit()

    sessions_today = conn.execute("""
        SELECT activity_type, minutes
        FROM stress_logs
        WHERE user_id=? AND log_date=?
    """, (
        user_id,
        today
    )).fetchall()

    conn.close()

    stress_data = {
        row["activity_type"]: row["minutes"]
        for row in sessions_today
    }

    return render_template(
        "stress.html",
        stress_data=stress_data
    )


# =========================================================
# MENSTRUAL CYCLE
# =========================================================

@app.route("/menstrual", methods=["GET", "POST"])
@login_required
def menstrual():

    user_id = session["user_id"]

    conn = get_db()

    if request.method == "POST":

        start = request.form.get(
            "period_start"
        )

        end = request.form.get(
            "period_end"
        ) or None

        cycle_length = request.form.get(
            "cycle_length",
            "28"
        )

        flow = request.form.get(
            "flow",
            ""
        )

        mood = request.form.get(
            "mood",
            ""
        )

        symptoms = request.form.get(
            "symptoms",
            ""
        )

        notes = request.form.get(
            "notes",
            ""
        )

        try:

            cycle_length = max(
                20,
                min(
                    60,
                    int(cycle_length)
                )
            )

        except ValueError:

            cycle_length = 28

        if start:

            conn.execute("""
                INSERT INTO menstrual_logs
                (
                    user_id,
                    period_start,
                    period_end,
                    cycle_length,
                    flow,
                    mood,
                    symptoms,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                start,
                end,
                cycle_length,
                flow,
                mood,
                symptoms,
                notes
            ))

            conn.commit()

            flash(
                "Menstrual cycle entry saved."
            )

    latest = conn.execute("""
        SELECT *
        FROM menstrual_logs
        WHERE user_id=?
        ORDER BY period_start DESC, id DESC
        LIMIT 1
    """, (
        user_id,
    )).fetchone()

    history = conn.execute("""
        SELECT
            period_start,
            period_end,
            cycle_length,
            flow,
            mood
        FROM menstrual_logs
        WHERE user_id=?
        ORDER BY period_start DESC
        LIMIT 8
    """, (
        user_id,
    )).fetchall()

    conn.close()

    next_period = None
    cycle_day = None

    if latest:

        try:

            start_date = datetime.strptime(
                latest["period_start"],
                "%Y-%m-%d"
            ).date()

            cycle_length = (
                latest["cycle_length"]
                or 28
            )

            next_period = (
                start_date +
                timedelta(
                    days=cycle_length
                )
            )

            cycle_day = (
                date.today() -
                start_date
            ).days + 1

            if cycle_day < 1:
                cycle_day = None

        except ValueError:
            pass

    return render_template(
        "menstrual.html",
        latest=latest,
        history=history,
        next_period=next_period,
        cycle_day=cycle_day
    )


# =========================================================
# DOCTOR DIRECTORY
# =========================================================

@app.route("/doctors")
@login_required
def doctors():

    conn = get_db()

    doctors_list = conn.execute("""
        SELECT *
        FROM doctors
        ORDER BY name
    """).fetchall()

    conn.close()

    return render_template(
        "doctors.html",
        doctors=doctors_list
    )


# =========================================================
# APPOINTMENT BOOKING
# =========================================================

@app.route(
    "/appointment/<int:doctor_id>",
    methods=["GET", "POST"]
)
@login_required
def appointment(doctor_id):

    conn = get_db()

    doctor = conn.execute(
        """
        SELECT *
        FROM doctors
        WHERE id=?
        """,
        (doctor_id,)
    ).fetchone()

    if doctor is None:

        conn.close()

        return "Doctor not found", 404

    if request.method == "POST":

        appointment_date = request.form.get(
            "appointment_date"
        )

        appointment_time = request.form.get(
            "appointment_time"
        )

        reason = request.form.get(
            "reason",
            ""
        ).strip()

        if not appointment_date or not appointment_time:

            flash(
                "Please select an appointment date and time."
            )

        else:

            conn.execute("""
                INSERT INTO appointments
                (
                    user_id,
                    doctor_id,
                    appointment_date,
                    appointment_time,
                    reason
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                session["user_id"],
                doctor_id,
                appointment_date,
                appointment_time,
                reason
            ))

            conn.commit()
            conn.close()

            flash(
                "Appointment request submitted."
            )

            return redirect(
                url_for("doctors")
            )

    conn.close()

    return render_template(
        "appointment.html",
        doctor=doctor
    )

#appointments
@app.route("/appointments")
@login_required
def appointments():
    user_id = session["user_id"]

    conn = get_db()

    appointments = conn.execute("""
        SELECT
            appointments.id,
            appointments.appointment_date,
            appointments.appointment_time,
            appointments.reason,
            appointments.status,
            doctors.name,
            doctors.specialization,
            doctors.clinic
        FROM appointments
        JOIN doctors
            ON appointments.doctor_id = doctors.id
        WHERE appointments.user_id = ?
        ORDER BY
            appointments.appointment_date,
            appointments.appointment_time
    """, (user_id,)).fetchall()

    conn.close()

    return render_template(
        "appointments.html",
        appointments=appointments
    )


# =========================================================
# WEEKLY REPORT - CALENDAR BASED
# =========================================================

@app.route("/weekly-report")
@login_required
def weekly_report():
    user_id = session["user_id"]

    # -----------------------------------------------------
    # YEAR / MONTH / WEEK SELECTION
    # -----------------------------------------------------
    today = date.today()

    try:
        selected_year = int(request.args.get("year", today.year))
    except (TypeError, ValueError):
        selected_year = today.year

    try:
        selected_month = int(request.args.get("month", today.month))
    except (TypeError, ValueError):
        selected_month = today.month

    try:
        selected_week = int(request.args.get("week", 1))
    except (TypeError, ValueError):
        selected_week = 1

    # Keep selections valid.
    selected_year = max(2000, min(2100, selected_year))
    selected_month = max(1, min(12, selected_month))
    selected_week = max(1, min(5, selected_week))

    # -----------------------------------------------------
    # MONTH RANGE
    # -----------------------------------------------------
    import calendar

    days_in_month = calendar.monthrange(
        selected_year,
        selected_month
    )[1]

    # Requested week format:
    # Week 1 = 1-7
    # Week 2 = 8-14
    # Week 3 = 15-21
    # Week 4 = 22-28
    # Week 5 = 29-end of month
    week_start_day = ((selected_week - 1) * 7) + 1

    if week_start_day > days_in_month:
        selected_week = 1
        week_start_day = 1

    week_end_day = min(
        week_start_day + 6,
        days_in_month
    )

    selected_start = date(
        selected_year,
        selected_month,
        week_start_day
    )

    selected_end = date(
        selected_year,
        selected_month,
        week_end_day
    )

    days = [
        selected_start + timedelta(days=i)
        for i in range(
            (selected_end - selected_start).days + 1
        )
    ]

    # -----------------------------------------------------
    # FETCH DATA FOR EVERY DAY
    # -----------------------------------------------------
    conn = get_db()

    daily_rows = []

    water_total = 0
    steps_total = 0
    meals_total = 0
    yoga_total = 0
    exercise_total = 0
    stress_minutes_total = 0

    for current_day in days:

        day_string = current_day.isoformat()

        # WATER
        water_row = conn.execute("""
            SELECT glasses
            FROM water_logs
            WHERE user_id=?
            AND log_date=?
        """, (
            user_id,
            day_string
        )).fetchone()

        water = (
            water_row["glasses"]
            if water_row
            else 0
        )

        # STEPS
        synced_steps_row = conn.execute("""
            SELECT steps
            FROM health_sync_logs
            WHERE user_id=?
            AND log_date=?
        """, (
            user_id,
            day_string
        )).fetchone()

        steps_row = conn.execute("""
            SELECT steps
            FROM steps_logs
            WHERE user_id=?
            AND log_date=?
        """, (
            user_id,
            day_string
        )).fetchone()

        steps = (
            int(synced_steps_row["steps"])
            if synced_steps_row
            else (int(steps_row["steps"]) if steps_row else 0)
        )

        # MEALS
        meals_row = conn.execute("""
            SELECT COUNT(*) AS count
            FROM activity_logs
            WHERE user_id=?
            AND log_date=?
            AND activity_name LIKE 'meal_%'
            AND completed=1
        """, (
            user_id,
            day_string
        )).fetchone()

        meals = (
            meals_row["count"]
            if meals_row
            else 0
        )

        # YOGA
        yoga_row = conn.execute("""
            SELECT COUNT(*) AS count
            FROM activity_logs
            WHERE user_id=?
            AND log_date=?
            AND activity_name LIKE 'yoga_%'
            AND completed=1
        """, (
            user_id,
            day_string
        )).fetchone()

        yoga = (
            yoga_row["count"]
            if yoga_row
            else 0
        )

        # EXERCISE
        exercise_row = conn.execute("""
            SELECT COUNT(*) AS count
            FROM activity_logs
            WHERE user_id=?
            AND log_date=?
            AND activity_name LIKE 'exercise_%'
            AND completed=1
        """, (
            user_id,
            day_string
        )).fetchone()

        exercise = (
            exercise_row["count"]
            if exercise_row
            else 0
        )

        # STRESS / MEDITATION / BREATHING
        stress_row = conn.execute("""
            SELECT COALESCE(SUM(minutes), 0) AS minutes
            FROM stress_logs
            WHERE user_id=?
            AND log_date=?
        """, (
            user_id,
            day_string
        )).fetchone()

        stress_minutes = (
            stress_row["minutes"]
            if stress_row
            else 0
        )

        # SATTVIC DAILY LOG
        sattvic_row = conn.execute("""
            SELECT sunlight_completed, morning_water_completed,
                   breakfast_completed, snack_completed, lunch_completed,
                   evening_completed, dinner_completed, movement_completed
            FROM sattvic_daily_logs
            WHERE user_id=? AND log_date=?
        """, (user_id, day_string)).fetchone()

        sattvic_done = sattvic_completion(sattvic_row)
        sattvic_percent = round((sattvic_done / 8) * 100)

        # TOTALS
        water_total += water
        steps_total += steps
        meals_total += meals
        yoga_total += yoga
        exercise_total += exercise
        stress_minutes_total += stress_minutes

        # DAILY COMPLETION %
        water_score = min(
            100,
            (water / 8) * 100
        )

        step_score = min(
            100,
            (steps / 8000) * 100
        )

        meal_score = (
            (meals / 4) * 100
            if meals
            else 0
        )

        yoga_score = (
            (yoga / 5) * 100
            if yoga
            else 0
        )

        exercise_score = (
            (exercise / 3) * 100
            if exercise
            else 0
        )

        stress_score = (
            100
            if stress_minutes > 0
            else 0
        )

        daily_score = round(
            (
                water_score +
                step_score +
                meal_score +
                yoga_score +
                exercise_score +
                stress_score
            ) / 6
        )

        daily_rows.append({
            "date": current_day,
            "date_label": current_day.strftime("%b %d"),
            "day_name": current_day.strftime("%A"),
            "water": water,
            "steps": steps,
            "meals": meals,
            "yoga": yoga,
            "exercise": exercise,
            "stress_minutes": stress_minutes,
            "sattvic_done": sattvic_done,
            "sattvic_percent": sattvic_percent,
            "daily_score": daily_score
        })

    conn.close()

    # -----------------------------------------------------
    # SATTVIC WEEKLY SUMMARY
    # -----------------------------------------------------
    number_of_days = len(days)
    sattvic_total = sum(row["sattvic_done"] for row in daily_rows)
    sattvic_target = number_of_days * 8
    sattvic_score = round((sattvic_total / sattvic_target) * 100) if sattvic_target else 0
    sattvic_active_days = sum(1 for row in daily_rows if row["sattvic_done"] > 0)

    # Health Connect coverage for the selected period.
    health_connect_days = conn.execute("""
        SELECT COUNT(*)
        FROM health_sync_logs
        WHERE user_id=? AND log_date BETWEEN ? AND ?
    """, (user_id, selected_start.isoformat(), selected_end.isoformat())).fetchone()[0]

    # -----------------------------------------------------
    # WEEKLY SUMMARY
    # -----------------------------------------------------
    number_of_days = len(days)

    avg_water = round(
        water_total / number_of_days,
        1
    )

    avg_steps = round(
        steps_total / number_of_days
    )

    meal_target = number_of_days * 4
    yoga_target = number_of_days * 5
    exercise_target = number_of_days * 3

    hydration_score = min(
        100,
        (avg_water / 8) * 100
    )

    step_score = min(
        100,
        (avg_steps / 8000) * 100
    )

    meal_score = (
        (meals_total / meal_target) * 100
        if meal_target
        else 0
    )

    yoga_score = (
        (yoga_total / yoga_target) * 100
        if yoga_target
        else 0
    )

    exercise_score = (
        (exercise_total / exercise_target) * 100
        if exercise_target
        else 0
    )

    stress_days = sum(
        1
        for row in daily_rows
        if row["stress_minutes"] > 0
    )

    stress_score = (
        (stress_days / number_of_days) * 100
        if number_of_days
        else 0
    )

    wellness_score = round(
        (
            hydration_score +
            step_score +
            meal_score +
            yoga_score +
            exercise_score +
            stress_score
        ) / 6
    )

    # -----------------------------------------------------
    # INSIGHTS
    # -----------------------------------------------------
    insights = []

    if avg_water < 6:
        insights.append(
            "💧 Hydration was below the 8-glass daily target on average."
        )
    else:
        insights.append(
            "💧 Your hydration routine was fairly consistent."
        )

    if avg_steps < 5000:
        insights.append(
            "👣 Try gradually increasing daily movement."
        )
    else:
        insights.append(
            "👣 Your activity level showed good consistency."
        )

    if yoga_total >= 3:
        insights.append(
            "🧘 You completed yoga routines during this selected week."
        )
    else:
        insights.append(
            "🧘 Try adding a few short yoga sessions during the week."
        )

    if stress_days > 0:
        insights.append(
            "🧠 You used the stress-control tools during this selected week."
        )
    else:
        insights.append(
            "🧠 No stress-control session was recorded for this selected week."
        )

    # -----------------------------------------------------
    # AVAILABLE YEARS
    # -----------------------------------------------------
    conn = get_db()

    year_rows = conn.execute("""
        SELECT DISTINCT substr(log_date, 1, 4) AS year
        FROM (
            SELECT log_date FROM water_logs WHERE user_id=?
            UNION
            SELECT log_date FROM steps_logs WHERE user_id=?
            UNION
            SELECT log_date FROM activity_logs WHERE user_id=?
            UNION
            SELECT log_date FROM stress_logs WHERE user_id=?
            UNION
            SELECT log_date FROM health_sync_logs WHERE user_id=?
        )
        ORDER BY year
    """, (
        user_id,
        user_id,
        user_id,
        user_id,
        user_id
    )).fetchall()

    conn.close()

    available_years = sorted(
        {
            int(row["year"])
            for row in year_rows
            if row["year"]
        }
        | {today.year}
    )

    return render_template(
        "weekly_report.html",

        selected_year=selected_year,
        selected_month=selected_month,
        selected_week=selected_week,

        month_name=date(
            selected_year,
            selected_month,
            1
        ).strftime("%B"),

        days_in_month=days_in_month,

        week_start_day=week_start_day,
        week_end_day=week_end_day,

        days=daily_rows,

        available_years=available_years,

        water_total=water_total,
        steps_total=steps_total,
        meals_total=meals_total,
        yoga_total=yoga_total,
        exercise_total=exercise_total,
        stress_minutes_total=stress_minutes_total,
        sattvic_total=sattvic_total,
        sattvic_target=sattvic_target,
        sattvic_score=sattvic_score,
        sattvic_active_days=sattvic_active_days,
        health_connect_days=health_connect_days,

        avg_water=avg_water,
        avg_steps=avg_steps,

        wellness_score=wellness_score,

        hydration_score=round(hydration_score),
        step_score=round(step_score),
        meal_score=round(meal_score),
        yoga_score=round(yoga_score),
        exercise_score=round(exercise_score),
        stress_score=round(stress_score),

        insights=insights
    )


# =========================================================
# PROFILE
# =========================================================

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():

    user_id = session["user_id"]

    conn = get_db()

    if request.method == "POST":

        age = request.form.get("age")
        weight = request.form.get("weight")
        bmi = request.form.get("bmi")
        cycle_length = request.form.get(
            "cycle_length"
        )

        try:

            age = int(age)
            weight = int(weight)
            bmi = float(bmi)
            cycle_length = int(cycle_length)

        except (
            ValueError,
            TypeError
        ):

            flash(
                "Please enter valid profile values."
            )

        else:

            conn.execute("""
                UPDATE health_profiles
                SET
                    age=?,
                    weight=?,
                    bmi=?,
                    cycle_length=?
                WHERE user_id=?
            """, (
                age,
                weight,
                bmi,
                cycle_length,
                user_id
            ))

            conn.commit()

            flash(
                "Profile updated successfully."
            )

    profile_data = conn.execute("""
        SELECT *
        FROM health_profiles
        WHERE user_id=?
    """, (
        user_id,
    )).fetchone()

    predictions = conn.execute("""
        SELECT *
        FROM health_predictions
        WHERE user_id=?
    """, (
        user_id,
    )).fetchone()

    conn.close()

    return render_template(
        "profile.html",
        username=session["username"],
        profile=profile_data,
        predictions=predictions
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    init_db()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )