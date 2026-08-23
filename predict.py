import joblib
import numpy as np

# Load Saved Model
model = joblib.load("diabetes_model.pkl")

print("Enter Patient Details:")

# Take Inputs
pregnancies = int(input("Pregnancies: "))
glucose = int(input("Glucose Level: "))
blood_pressure = int(input("Blood Pressure: "))
skin_thickness = int(input("Skin Thickness: "))
insulin = int(input("Insulin Level: "))
bmi = float(input("BMI: "))
diabetes_pedigree = float(input("Diabetes Pedigree Function: "))
age = int(input("Age: "))

# Create Input Array
input_data = np.array([[pregnancies,
                        glucose,
                        blood_pressure,
                        skin_thickness,
                        insulin,
                        bmi,
                        diabetes_pedigree,
                        age]])

# Predict
prediction = model.predict(input_data)

# Output Result
if prediction[0] == 1:
    print("\n⚠ High Diabetes Risk Detected")
else:
    print("\n✅ Low Diabetes Risk")