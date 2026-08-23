import pandas as pd
import numpy as np

np.random.seed(42)

data_size = 500

Age = np.random.randint(18, 45, data_size)
Hemoglobin = np.random.uniform(8, 15, data_size)
Fatigue = np.random.randint(0, 2, data_size)
Dizziness = np.random.randint(0, 2, data_size)
Pale_Skin = np.random.randint(0, 2, data_size)

# Smart rule for anemia
Anemia = (
    (Hemoglobin < 11) |
    (Fatigue == 1) |
    (Dizziness == 1)
).astype(int)

data = pd.DataFrame({
    "Age": Age,
    "Hemoglobin": Hemoglobin,
    "Fatigue": Fatigue,
    "Dizziness": Dizziness,
    "Pale_Skin": Pale_Skin,
    "Anemia": Anemia
})

data.to_csv("anemia.csv", index=False)

print("Anemia dataset created successfully!")