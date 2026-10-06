import sys
from pathlib import Path
BASE_DIR = Path(r"D:\Personal Coding\Data Science and ML\NEW_X1")
sys.path.insert(0, str(BASE_DIR / "data_preprocessing"))

import cricketstats as cks
from Data_Extracter import data_extracter
import Data_Extracter
import os

zip_path = str(BASE_DIR / "data" / "raw" / "t20s_json.zip")
print(f"Zip exists: {os.path.exists(zip_path)}")
Data_Extracter.database = zip_path

print("Starting extraction...")
data_extracter(["T20", "IT20"], (2026, 9, 1), (2026, 9, 17))
print("Done!")
