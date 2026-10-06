# Diabetes risk model for FemCare AI
# Retrained using simple binary risk indicators derived from diabetes.csv.

import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

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

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y
)

model = RandomForestClassifier(
    n_estimators=300,
    max_depth=6,
    random_state=42,
    class_weight="balanced"
)

model.fit(X_train, y_train)

y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print("Diabetes Risk Model Accuracy:", round(accuracy, 4))
print(classification_report(y_test, y_pred))

joblib.dump(model, "diabetes_model.pkl")
print("Saved: diabetes_model.pkl")
