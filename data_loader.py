import os
import csv
import pandas as pd
from datetime import datetime

class SESIDataLoader:
    def __init__(self, base_dir="data"):
        self.base_dir = base_dir
        self.stats_dir = os.path.join(base_dir, "statistics")
        self.fees_dir = os.path.join(base_dir, "fees") # Fallback or specific JP fees
        
    def load_jp_fees(self, filename="jp_fees.csv"):
        """Loads Japanese fee data from CSV."""
        path = os.path.join(self.base_dir, "fees", filename)
        if not os.path.exists(path):
            path = os.path.join(self.base_dir, filename)
            
        fees = []
        try:
            with open(path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    fees.append({
                        "name": row["name"],
                        "unit": float(row["unit"]),
                        "category": row["category"],
                        "grade": row["grade"]
                    })
        except Exception as e:
            print(f"ERROR: Failed to load JP fees: {e}")
        return fees

    def load_grade_weights(self):
        """
        Loads the latest grade distribution weights from NHIS statistics.
        Returns a dict: { "1": 0.1, "2": 0.2, ... }
        """
        # Looking for '국민건강보험공단_노인장기요양보험 인정현황'
        target_file = ""
        for f in os.listdir(self.stats_dir):
            if "장기요양보험 인정현황" in f and f.endswith(".csv"):
                target_file = f
                break
        
        if not target_file:
            print("WARNING: Recognition statistics file not found. Using equal weights.")
            return {str(i): 1.0/5.0 for i in range(1, 6)}

        path = os.path.join(self.stats_dir, target_file)
        try:
            # Try CP949 first (standard for KR govt CSVs)
            try:
                df = pd.read_csv(path, encoding='cp949')
            except:
                df = pd.read_csv(path, encoding='utf-8')

            # Filter for '비율' (Ratio) rows
            # Columns usually: 구분1 (Year), 구분2 (Inwon/Ratio), 전체계, 인정자소계, 1등급, 2등급...
            ratio_df = df[df.iloc[:, 1] == '비율']
            if ratio_df.empty:
                # Some files might use different column names
                ratio_df = df[df.apply(lambda r: '비율' in str(r.values), axis=1)]
            
            # Get the most recent year (last row of ratios)
            latest_ratios = ratio_df.iloc[-1]
            
            # Map grades 1-5
            # Headers are usually index 4 to 8 (1등급, 2등급, 3등급, 4등급, 5등급)
            # We normalize them to 0.0 - 1.0
            weights = {
                "1": float(latest_ratios[4]) / 100.0,
                "2": float(latest_ratios[5]) / 100.0,
                "3": float(latest_ratios[6]) / 100.0,
                "4": float(latest_ratios[7]) / 100.0,
                "5": float(latest_ratios[8]) / 100.0
            }
            return weights
            
        except Exception as e:
            print(f"ERROR: Failed to parse weights from {target_file}: {e}")
            return {str(i): 1.0/5.0 for i in range(1, 6)}

if __name__ == "__main__":
    # Test
    loader = SESIDataLoader()
    print("JP Fees:", loader.load_jp_fees())
    print("Weights:", loader.load_grade_weights())
