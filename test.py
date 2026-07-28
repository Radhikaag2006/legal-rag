import pandas as pd

df = pd.read_csv("data/csv/judgements.csv")   # Replace with your CSV filename if different
print(df.columns.tolist())