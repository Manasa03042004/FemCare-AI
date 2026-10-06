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

    conn = get_db()

    profile = conn.execute(
        """
        SELECT profile_completed
        FROM health_profiles
        WHERE user_id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    conn.close()

    if profile and profile["profile_completed"] == 1:
        return redirect(url_for("dashboard"))

    return render_template("index.html")


# =========================================================
# PREDICT + SAVE HEALTH PROFILE
# =========================================================

@app.route("/predict", methods=["POST"])
@login_required
def predict():

    try:

        pregnancies = int(request.form["pregnancies"])
        glucose = int(request.form["glucose"])
        blood_pressure = int(request.form["blood_pressure"])
        skin_thickness = int(request.form["skin_thickness"])
        insulin = int(request.form["insulin"])
        bmi = float(request.form["bmi"])
        diabetes_pedigree = float(request.form["diabetes_pedigree"])
        age = int(request.form["age"])

        weight = int(request.form["weight"])
        cycle_length = int(request.form["cycle_length"])
        hair_growth = int(request.form["hair_growth"])
        skin_darkening = int(request.form["skin_darkening"])
        weight_gain = int(request.form["weight_gain"])

        hemoglobin = float(request.form["hemoglobin"])
        fatigue = int(request.form["fatigue"])
        dizziness = int(request.form["dizziness"])
        pale_skin = int(request.form["pale_skin"])

        thyroid_weight = int(request.form["thyroid_weight"])
        thyroid_fatigue = int(request.form["thyroid_fatigue"])
        hair_loss = int(request.form["hair_loss"])
        mood_swings = int(request.form["mood_swings"])

        diet_preference = request.form.get(
            "diet_preference",
            "Vegetarian"
        ).strip() or "Vegetarian"

        allergies = ", ".join(
            request.form.getlist("allergies")
        )

        food_dislikes = request.form.get(
            "food_dislikes",
            ""
        ).strip()

    except (KeyError, ValueError):

        flash("Please enter valid values in all health assessment fields.")

        return redirect(url_for("health_assessment"))

    # -----------------------------------------------------
    # DIABETES
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # PCOS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # ANEMIA
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # THYROID
    # -----------------------------------------------------

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
            diet_preference,
            allergies,
            food_dislikes,
            profile_completed
        )
        VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
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
# DIET
# =========================================================

@app.route("/diet", methods=["GET", "POST"])
@login_required
def diet():

    user_id = session["user_id"]
    today = today_string()

    # FOUR meals
    meal_names = [
        "breakfast",
        "lunch",
        "evening",
        "dinner"
    ]

    conn = get_db()

    # -----------------------------------------------------
    # SAVE
    # -----------------------------------------------------

    if request.method == "POST":

        for meal in meal_names:

            completed = (
                1
                if request.form.get(f"meal_{meal}") == "1"
                else 0
            )

            conn.execute("""
                INSERT INTO activity_logs
                (
                    user_id,
                    log_date,
                    activity_name,
                    completed
                )
                VALUES (?, ?, ?, ?)

                ON CONFLICT(user_id, log_date, activity_name)
                DO UPDATE SET
                    completed=excluded.completed
            """, (
                user_id,
                today,
                f"meal_{meal}",
                completed
            ))

        conn.commit()

        flash("Today's meal progress has been saved.")

        conn.close()

        return redirect(url_for("diet"))

    # -----------------------------------------------------
    # LOAD SAVED DATA
    # -----------------------------------------------------

    rows = conn.execute("""
        SELECT activity_name, completed
        FROM activity_logs
        WHERE user_id=?
        AND log_date=?
        AND activity_name LIKE 'meal_%'
    """, (user_id, today)).fetchall()

    profile = conn.execute("""
        SELECT diet_preference, allergies, food_dislikes
        FROM health_profiles
        WHERE user_id=?
    """, (user_id,)).fetchone()

    conn.close()

    meal_status = {
        row["activity_name"]: row["completed"]
        for row in rows
    }

    meals_done = sum(
        1
        for meal in meal_names
        if meal_status.get(
            f"meal_{meal}",
            0
        ) == 1
    )

    meal_progress = min(
        100,
        int(
            (meals_done / len(meal_names))
            * 100
        )
    )

    return render_template(
        "diet.html",
        meal_status=meal_status,
        meals_done=meals_done,
        meal_total=len(meal_names),
        meal_progress=meal_progress,
        diet_preference=(
            profile["diet_preference"]
            if profile and profile["diet_preference"]
            else "Vegetarian"
        ),
        allergies=(
            profile["allergies"]
            if profile and profile["allergies"]
            else ""
        ),
        food_dislikes=(
            profile["food_dislikes"]
            if profile and profile["food_dislikes"]
            else ""
        )
    )


# =========================================================
# RECIPE
# =========================================================

@app.route("/recipe/<dish_name>")
@login_required
def recipe(dish_name):

    recipes = {

        "paneer_salad": {
            "name": "Paneer Salad",
            "ingredients": [
                "Paneer cubes",
                "Tomato",
                "Cucumber",
                "Pepper"
            ],
            "steps": [
                "Cut vegetables",
                "Add paneer",
                "Mix well",
                "Serve fresh"
            ]
        },

        "oats_upma": {
            "name": "Oats Upma",
            "ingredients": [
                "Oats",
                "Vegetables",
                "Salt",
                "Oil"
            ],
            "steps": [
                "Roast oats",
                "Cook vegetables",
                "Add oats",
                "Cook 5 minutes"
            ]
        },

        "veg_soup": {
            "name": "Vegetable Soup",
            "ingredients": [
                "Carrot",
                "Beans",
                "Salt",
                "Pepper"
            ],
            "steps": [
                "Boil vegetables",
                "Add salt",
                "Simmer",
                "Serve hot"
            ]
        },

        "beetroot_salad": {
            "name": "Beetroot Salad",
            "ingredients": [
                "Beetroot",
                "Lemon",
                "Salt"
            ],
            "steps": [
                "Boil beetroot",
                "Cut pieces",
                "Add lemon",
                "Serve"
            ]
        },

        "dates_milk": {
            "name": "Dates Milk",
            "ingredients": [
                "Dates",
                "Milk"
            ],
            "steps": [
                "Blend dates",
                "Add milk",
                "Serve chilled"
            ]
        },

        "boiled_eggs": {
            "name": "Boiled Eggs",
            "ingredients": [
                "Eggs",
                "Salt"
            ],
            "steps": [
                "Boil eggs 10 minutes",
                "Peel shell",
                "Serve warm"
            ]
        },

        "brown_rice": {
            "name": "Brown Rice Meal",
            "ingredients": [
                "Brown rice",
                "Vegetables"
            ],
            "steps": [
                "Cook rice",
                "Add vegetables",
                "Serve hot"
            ]
        },

        "moong_chilla": {
            "name": "Moong Dal Chilla",
            "ingredients": [
                "Moong dal",
                "Salt",
                "Spices"
            ],
            "steps": [
                "Soak dal",
                "Grind batter",
                "Cook on pan"
            ]
        },

        "sprouts_salad": {
            "name": "Sprouts Salad",
            "ingredients": [
                "Sprouts",
                "Tomato",
                "Onion"
            ],
            "steps": [
                "Mix sprouts",
                "Add vegetables",
                "Serve"
            ]
        },

        "quinoa_bowl": {
            "name": "Quinoa Bowl",
            "ingredients": [
                "Quinoa",
                "Vegetables"
            ],
            "steps": [
                "Cook quinoa",
                "Add vegetables"
            ]
        },

        "spinach_curry": {
            "name": "Spinach Curry",
            "ingredients": [
                "Spinach",
                "Spices"
            ],
            "steps": [
                "Cook spinach",
                "Add spices"
            ]
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