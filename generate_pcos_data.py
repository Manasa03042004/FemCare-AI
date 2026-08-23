import pandas as pd
import numpy as np

np.random.seed(42)

data_size = 500

Age = np.random.randint(18, 45, data_size)
Weight = np.random.randint(45, 90, data_size)
Cycle_Length = np.random.randint(21, 40, data_size)

Hair_Growth = np.random.randint(0, 2, data_size)
Skin_Darkening = np.random.randint(0, 2, data_size)
Weight_Gain = np.random.randint(0, 2, data_size)

# Create smarter PCOS rule
PCOS = (
    (Cycle_Length > 35) |
    (Hair_Growth == 1) |
    (Weight_Gain == 1)
).astype(int)

data = pd.DataFrame({
    "Age": Age,
    "Weight": Weight,
    "Cycle_Length": Cycle_Length,
    "Hair_Growth": Hair_Growth,
    "Skin_Darkening": Skin_Darkening,
    "Weight_Gain": Weight_Gain,
    "PCOS": PCOS
})

data.to_csv("pcos.csv", index=False)

print("Improved PCOS dataset created!")