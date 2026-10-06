from flask import Flask, render_template, request, redirect, url_for, session, flash
import joblib
import numpy as np
import sqlite3
from functools import wraps
from datetime import date, datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "femcare_ai_secret_key"


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
        ("food_dislikes", "TEXT", "''")
    ]:
        if column_name not in existing_columns:
            cursor.execute(
                f"ALTER TABLE health_profiles "
                f"ADD COLUMN {column_name} {column_type} DEFAULT {default_value}"
            )

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

diabetes_model = joblib.load("diabetes_model.pkl")
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

        bmi = round(
            weight / ((height_cm / 100) ** 2),
            1
        )

        # Disease-specific fields are only required when
        # the user selected that health screening.
        pregnancies = int(request.form.get("pregnancies", 0))
        glucose = int(request.form.get("glucose", 0))
        blood_pressure = int(request.form.get("blood_pressure", 0))
        # Skin thickness is no longer collected from the user.
        # Keep the legacy model feature at 0 for compatibility with
        # the currently trained diabetes model.
        skin_thickness = 0
        insulin = int(request.form.get("insulin", 0))
        diabetes_pedigree = float(request.form.get("diabetes_pedigree", 0))

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

        # Server-side validation mirrors the progressive UI.
        # Only the selected screening needs its disease-specific data.
        if screening_diabetes:
            if (
                pregnancies < 0 or
                glucose <= 0 or
                blood_pressure <= 0 or
                insulin < 0 or
                diabetes_pedigree < 0
            ):
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
            pregnancies,
            glucose,
            blood_pressure,
            skin_thickness,
            insulin,
            bmi,
            diabetes_pedigree,
            age
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
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1
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
        SELECT
            diabetes_percentage,
            pcos_percentage,
            anemia_percentage,
            thyroid_percentage
        FROM health_predictions
        WHERE user_id=?
    """, (user_id,)).fetchone()

    if prediction is None:

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

    steps_data = conn.execute("""
        SELECT steps
        FROM steps_logs
        WHERE user_id=? AND log_date=?
    """, (user_id, today)).fetchone()

    step_count = steps_data["steps"] if steps_data else 0

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

        wellness_progress=wellness_progress
    )


# =========================================================
# PERSONALIZED NUTRITION ENGINE
# =========================================================

def _food_is_blocked(ingredients, preference, allergies, dislikes):
    ingredient_text = " ".join(ingredients).lower()
    allergy_text = str(allergies or "").lower()
    dislike_items = [x.strip().lower() for x in str(dislikes or "").split(",") if x.strip()]

    allergy_groups = {
        "nuts": ["almond", "walnut", "cashew", "pistachio", "nut"],
        "peanuts": ["peanut", "groundnut"],
        "dairy": ["milk", "paneer", "curd", "yogurt", "cheese", "ghee", "butter"],
        "gluten": ["wheat", "bread", "atta", "maida", "barley", "rye"],
        "soy": ["soy", "tofu", "soya"],
        "sesame": ["sesame", "til"],
        "seeds": ["seed", "chia", "flax", "sunflower", "pumpkin"]
    }

    for allergy, words in allergy_groups.items():
        if allergy in allergy_text and any(word in ingredient_text for word in words):
            return True

    pref = str(preference or "").lower()
    if "vegan" in pref and any(word in ingredient_text for word in [
        "milk", "paneer", "curd", "yogurt", "cheese", "ghee", "butter", "egg"
    ]):
        return True

    if pref in ["vegetarian", "vegan", "eggetarian"] and any(
        word in ingredient_text for word in ["chicken", "fish", "meat", "mutton"]
    ):
        return True

    if pref == "vegetarian" and "egg" in ingredient_text:
        return True

    if pref == "eggetarian" and any(
        word in ingredient_text for word in ["chicken", "fish", "meat", "mutton"]
    ):
        return True

    for item in dislike_items:
        if item in ingredient_text:
            return True

    for part in allergy_text.split(","):
        part = part.strip()
        if part.startswith("other:"):
            custom = part.replace("other:", "", 1).strip()
            if custom and custom in ingredient_text:
                return True

    return False


def build_personalized_meal_plan(profile, predictions):
    preference = profile["diet_preference"] if profile and profile["diet_preference"] else "Vegetarian"
    allergies = profile["allergies"] if profile else ""
    dislikes = profile["food_dislikes"] if profile else ""

    risk_flags = {
        "diabetes": bool(predictions and ((predictions["diabetes_prediction"] or 0) == 1 or (predictions["diabetes_percentage"] or 0) >= 50)),
        "pcos": bool(predictions and ((predictions["pcos_prediction"] or 0) == 1 or (predictions["pcos_percentage"] or 0) >= 50)),
        "anemia": bool(predictions and ((predictions["anemia_prediction"] or 0) == 1 or (predictions["anemia_percentage"] or 0) >= 50)),
        "thyroid": bool(predictions and ((predictions["thyroid_prediction"] or 0) == 1 or (predictions["thyroid_percentage"] or 0) >= 50))
    }

    focus = []
    if risk_flags["anemia"]:
        focus.append(("🩸", "Iron Support", "Iron-rich foods such as spinach, lentils and beetroot."))
    if risk_flags["pcos"]:
        focus.append(("🌸", "PCOS-Friendly Balance", "Protein, vegetables and high-fibre carbohydrates."))
    if risk_flags["diabetes"]:
        focus.append(("🩺", "Blood-Sugar Friendly", "Fibre-rich meals with limited added sugar."))
    if risk_flags["thyroid"]:
        focus.append(("🦋", "Balanced Thyroid Support", "Balanced meals with protein, vegetables and whole foods."))
    if not focus:
        focus.append(("🥗", "Balanced Wellness", "Vegetables, protein, whole grains and regular hydration."))

    plans = {
        "breakfast": [
            {"diseases":["anemia"],"name":"Spinach Moong Chilla","recipe":"spinach_moong_chilla","ingredients":["spinach","moong dal","lemon","spices"]},
            {"diseases":["pcos","diabetes"],"name":"Moong Dal Chilla","recipe":"moong_chilla","ingredients":["moong dal","vegetables","spices"]},
            {"diseases":["thyroid"],"name":"Vegetable Moong Chilla","recipe":"moong_chilla","ingredients":["moong dal","vegetables","spices"]},
            {"diseases":[],"name":"Vegetable Oats Upma","recipe":"oats_upma","ingredients":["oats","mixed vegetables","spices"]}
        ],
        "snack": [
            {"diseases":["anemia"],"name":"Beetroot Fruit Bowl","recipe":"beetroot_salad","ingredients":["beetroot","apple","lemon"]},
            {"diseases":["pcos","diabetes"],"name":"Apple & Roasted Chickpeas","recipe":"fruit_chickpea_bowl","ingredients":["apple","roasted chickpeas","cinnamon"]},
            {"diseases":["thyroid"],"name":"Fresh Fruit Bowl","recipe":"fruit_bowl","ingredients":["apple","papaya","banana"]},
            {"diseases":[],"name":"Seasonal Fruit Bowl","recipe":"fruit_bowl","ingredients":["seasonal fruit","water"]}
        ],
        "lunch": [
            {"diseases":["anemia"],"name":"Spinach Dal Brown Rice","recipe":"spinach_dal_rice","ingredients":["spinach","dal","brown rice","lemon"]},
            {"diseases":["pcos","diabetes"],"name":"Protein Vegetable Brown Rice Bowl","recipe":"protein_rice_bowl","ingredients":["brown rice","dal","vegetables","beans"]},
            {"diseases":["thyroid"],"name":"Balanced Brown Rice Vegetable Meal","recipe":"brown_rice","ingredients":["brown rice","vegetables","dal"]},
            {"diseases":[],"name":"Brown Rice Vegetable Meal","recipe":"brown_rice","ingredients":["brown rice","vegetables","dal"]}
        ],
        "evening": [
            {"diseases":["anemia"],"name":"Spinach Sprouts Salad","recipe":"spinach_sprouts_salad","ingredients":["spinach","sprouts","tomato","lemon"]},
            {"diseases":["pcos","diabetes"],"name":"Chickpea Sprouts Salad","recipe":"chickpea_sprouts_salad","ingredients":["chickpeas","sprouts","tomato","cucumber"]},
            {"diseases":["thyroid"],"name":"Vegetable Sprouts Salad","recipe":"sprouts_salad","ingredients":["sprouts","tomato","onion"]},
            {"diseases":[],"name":"Sprouts Salad","recipe":"sprouts_salad","ingredients":["sprouts","tomato","onion"]}
        ],
        "dinner": [
            {"diseases":["anemia"],"name":"Lentil Vegetable Bowl","recipe":"lentil_vegetable_bowl","ingredients":["lentils","spinach","carrot","lemon"]},
            {"diseases":["pcos","diabetes"],"name":"Chickpea Vegetable Salad","recipe":"chickpea_salad","ingredients":["chickpeas","cucumber","tomato","leafy greens"]},
            {"diseases":["thyroid"],"name":"Vegetable Moong Bowl","recipe":"moong_vegetable_bowl","ingredients":["moong dal","vegetables","brown rice"]},
            {"diseases":[],"name":"Paneer Vegetable Salad","recipe":"paneer_salad","ingredients":["paneer","cucumber","tomato","spices"]}
        ]
    }

    labels = {
        "breakfast":("Breakfast","MORNING","🍳"),
        "snack":("Mid-Morning","MID-MORNING","🍎"),
        "lunch":("Lunch","AFTERNOON","🍚"),
        "evening":("Evening Snack","EVENING","🥗"),
        "dinner":("Dinner","NIGHT","🥘")
    }

    selected = []
    for slot, candidates in plans.items():
        candidates = sorted(
            candidates,
            key=lambda item: 0 if any(d in item["diseases"] and risk_flags[d] for d in item["diseases"]) else 1
        )
        chosen = next(
            (item for item in candidates if not _food_is_blocked(item["ingredients"], preference, allergies, dislikes)),
            None
        )
        if chosen is None:
            chosen = {
                "diseases":[],"name":"Vegetable Wellness Bowl",
                "recipe":"vegetable_wellness_bowl",
                "ingredients":["mixed vegetables","lentils","brown rice"]
            }
        label,time,icon=labels[slot]
        selected.append({**chosen,"slot":slot,"label":label,"time":time,"icon":icon})

    return {
        "meals":selected,
        "focus":focus,
        "preference":preference,
        "allergies":allergies,
        "dislikes":dislikes,
        "risk_flags":risk_flags
    }


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
        risk_flags=meal_plan["risk_flags"]
    )


# =========================================================
# RECIPE
# =========================================================

@app.route("/recipe/<dish_name>")
@login_required
def recipe(dish_name):

    recipes = {
        "oats_upma": {
            "name": "Vegetable Oats Upma",
            "ingredients": ["Oats", "Mixed vegetables", "Salt", "Healthy spices"],
            "steps": ["Roast oats lightly.", "Cook mixed vegetables.", "Add oats, water and spices.", "Cook until soft and serve warm."]
        },
        "moong_chilla": {
            "name": "Moong Dal Chilla",
            "ingredients": ["Moong dal", "Vegetables", "Salt", "Spices"],
            "steps": ["Soak moong dal and blend into batter.", "Mix vegetables and spices.", "Cook on a lightly oiled pan.", "Serve warm with lemon."]
        },
        "spinach_moong_chilla": {
            "name": "Spinach Moong Chilla",
            "ingredients": ["Moong dal", "Spinach", "Lemon", "Spices"],
            "steps": ["Blend soaked moong dal with spinach.", "Add spices.", "Cook on a hot pan until both sides are done.", "Serve with lemon."]
        },
        "fruit_bowl": {
            "name": "Fresh Fruit Bowl",
            "ingredients": ["Apple", "Papaya", "Banana"],
            "steps": ["Wash and cut the fruits.", "Combine in a bowl.", "Serve fresh without added sugar."]
        },
        "beetroot_salad": {
            "name": "Beetroot Fruit Bowl",
            "ingredients": ["Beetroot", "Apple", "Lemon"],
            "steps": ["Cook and dice beetroot.", "Add chopped apple.", "Finish with lemon.", "Serve fresh."]
        },
        "fruit_chickpea_bowl": {
            "name": "Apple & Roasted Chickpeas",
            "ingredients": ["Apple", "Roasted chickpeas", "Cinnamon"],
            "steps": ["Wash and slice the apple.", "Prepare roasted chickpeas.", "Add a small amount of cinnamon.", "Serve as a snack."]
        },
        "brown_rice": {
            "name": "Brown Rice Vegetable Meal",
            "ingredients": ["Brown rice", "Vegetables", "Dal"],
            "steps": ["Cook brown rice.", "Prepare vegetables and dal.", "Combine and serve warm."]
        },
        "spinach_dal_rice": {
            "name": "Spinach Dal Brown Rice",
            "ingredients": ["Spinach", "Dal", "Brown rice", "Lemon"],
            "steps": ["Cook brown rice.", "Prepare dal with spinach.", "Serve together.", "Finish with lemon."]
        },
        "protein_rice_bowl": {
            "name": "Protein Vegetable Brown Rice Bowl",
            "ingredients": ["Brown rice", "Dal", "Vegetables", "Beans"],
            "steps": ["Cook brown rice.", "Prepare dal and beans.", "Add mixed vegetables.", "Serve as a balanced bowl."]
        },
        "sprouts_salad": {
            "name": "Sprouts Salad",
            "ingredients": ["Sprouts", "Tomato", "Onion", "Lemon"],
            "steps": ["Combine sprouts and chopped vegetables.", "Add lemon and mild spices.", "Mix well and serve fresh."]
        },
        "spinach_sprouts_salad": {
            "name": "Spinach Sprouts Salad",
            "ingredients": ["Spinach", "Sprouts", "Tomato", "Lemon"],
            "steps": ["Wash the vegetables.", "Combine spinach, sprouts and tomato.", "Add lemon.", "Serve fresh."]
        },
        "chickpea_sprouts_salad": {
            "name": "Chickpea Sprouts Salad",
            "ingredients": ["Chickpeas", "Sprouts", "Tomato", "Cucumber"],
            "steps": ["Combine cooked chickpeas and sprouts.", "Add chopped tomato and cucumber.", "Mix with mild spices.", "Serve fresh."]
        },
        "paneer_salad": {
            "name": "Paneer Vegetable Salad",
            "ingredients": ["Paneer", "Cucumber", "Tomato", "Pepper"],
            "steps": ["Cut paneer and vegetables.", "Combine in a bowl.", "Season with pepper.", "Serve fresh."]
        },
        "chickpea_salad": {
            "name": "Chickpea Vegetable Salad",
            "ingredients": ["Chickpeas", "Cucumber", "Tomato", "Leafy greens"],
            "steps": ["Combine cooked chickpeas and vegetables.", "Add leafy greens.", "Season lightly.", "Serve fresh."]
        },
        "lentil_vegetable_bowl": {
            "name": "Lentil Vegetable Bowl",
            "ingredients": ["Lentils", "Spinach", "Carrot", "Lemon"],
            "steps": ["Cook lentils.", "Add spinach and carrot.", "Simmer until vegetables are tender.", "Finish with lemon."]
        },
        "moong_vegetable_bowl": {
            "name": "Vegetable Moong Bowl",
            "ingredients": ["Moong dal", "Vegetables", "Brown rice"],
            "steps": ["Cook moong dal.", "Prepare mixed vegetables.", "Serve with brown rice."]
        },
        "vegetable_wellness_bowl": {
            "name": "Vegetable Wellness Bowl",
            "ingredients": ["Mixed vegetables", "Lentils", "Brown rice"],
            "steps": ["Cook brown rice.", "Prepare lentils.", "Add mixed vegetables.", "Serve warm."]
        }
    }

    recipe_data = recipes.get(dish_name)

    if recipe_data is None:
        return "Recipe not found", 404

    return render_template(
        "recipe.html",
        recipe_name=recipe_data["name"],
        ingredients=recipe_data["ingredients"],
        steps=recipe_data["steps"]
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
            steps_row["steps"]
            if steps_row
            else 0
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
            "daily_score": daily_score
        })

    conn.close()

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
        )
        ORDER BY year
    """, (
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
        debug=True
    )