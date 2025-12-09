import pandas as pd
import os

# Paths
base_dir = r"c:\Users\ADMINS\Documents\projects\machine_learning\ml_predictions"
x_train_path = os.path.join(base_dir, "X_train.csv")
y_train_path = os.path.join(base_dir, "y_train.csv")
output_path = r"c:\Users\ADMINS\Documents\projects\machine_learning\data\training.parquet"

print("Reading CSVs...")
X = pd.read_csv(x_train_path)
y = pd.read_csv(y_train_path)

print(f"X shape: {X.shape}")
print(f"y shape: {y.shape}")

# Merge
df = pd.concat([X, y], axis=1)
print(f"Merged shape: {df.shape}")

# Save to parquet
print(f"Saving to {output_path}...")
df.to_parquet(output_path)
print("Done.")
