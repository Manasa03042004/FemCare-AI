import pandas as pd
import numpy as np

np.random.seed(42)

data_size = 500

Age = np.random.randint(18, 50, data_size)
Weight = np.random.randint(45, 95, data_size)
Fatigue = np.random.randint(0, 2, data_size)
Hair_Loss = np.random.randint(0, 2, data_size)
Mood_Swings = np.random.randint(0, 2, data_size)

# Smart thyroid rule
Thyroid = (
    (Fatigue == 1) |
    (Hair_Loss == 1) |
    (Mood_Swings == 1)
).astype(int)

data = pd.DataFrame({
    "Age": Age,
    "Weight": Weight,
    "Fatigue": Fatigue,
    "Hair_Loss": Hair_Loss,
    "Mood_Swings": Mood_Swings,
    "Thyroid": Thyroid
})

data.to_csv("thyroid.csv", index=False)

print("Thyroid dataset created successfully!")