import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib

# Load dataset
data = pd.read_csv("anemia.csv")

# Features & target
X = data.drop("Anemia", axis=1)
y = data["Anemia"]

# Split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Train
model = RandomForestClassifier()
model.fit(X_train, y_train)

# Predict
y_pred = model.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)

print("Anemia Model Accuracy:", accuracy)

# Save model
joblib.dump(model, "anemia_model.pkl")

print("Anemia model saved successfully!")