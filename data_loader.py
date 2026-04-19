import os
import csv
import pandas as pd
from datetime import datetime

class SESIDataLoader:
    def __init__(self, base_dir="data"):
        self.base_dir = base_dir
        self.stats_dir = os.path.join(base_dir, "statistics")
        self.infra_dir = os.path.join(base_dir, "infrastructure")
        self.fees_dir = os.path.join(base_dir, "fees")
        
    def load_jp_fees(self, filename="jp_fees.csv"):
        """Loads Japanese fee data from CSV."""
        path = os.path.join(self.fees_dir, filename)
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
        """Loads the latest grade distribution weights."""
        target_file = ""
        for f in os.listdir(self.stats_dir):
            if "장기요양보험 인정현황" in f and f.endswith(".csv"):
                target_file = f
                break
        
        if not target_file:
            return {str(i): 1.0/5.0 for i in range(1, 6)}

        path = os.path.join(self.stats_dir, target_file)
        try:
            # Smart encoding check
            df = None
            for enc in ['cp949', 'utf-8', 'euc-kr']:
                try:
                    df = pd.read_csv(path, encoding=enc)
                    break
                except:
                    continue
            
            if df is None: return {str(i): 1.0/5.0 for i in range(1, 6)}

            ratio_df = df[df.iloc[:, 1] == '비율']
            latest_ratios = ratio_df.iloc[-1]
            weights = {
                "1": float(latest_ratios[4]) / 100.0,
                "2": float(latest_ratios[5]) / 100.0,
                "3": float(latest_ratios[6]) / 100.0,
                "4": float(latest_ratios[7]) / 100.0,
                "5": float(latest_ratios[8]) / 100.0
            }
            return weights
        except:
            return {str(i): 1.0/5.0 for i in range(1, 6)}

    def calculate_quality_index(self):
        """Calculates average quality score (A-E) from infrastructure data."""
        target_file = ""
        for f in os.listdir(self.infra_dir):
            if "평가 결과" in f and f.endswith(".csv"):
                target_file = f
                break
        
        if not target_file:
            return 80.0 # Default High-Quality assumption

        path = os.path.join(self.infra_dir, target_file)
        try:
            df = None
            for enc in ['cp949', 'utf-8']:
                try:
                    df = pd.read_csv(path, encoding=enc)
                    break
                except:
                    continue
            
            if df is None: return 80.0
            
            # Map A=100, B=80, C=60, D=40, E=20
            grade_map = {'A': 100, 'B': 80, 'C': 60, 'D': 40, 'E': 20}
            # Column 5 is '평가등급'
            grades = df.iloc[:, 5].dropna().map(grade_map).fillna(60)
            return round(grades.mean(), 2)
        except:
            return 80.0

if __name__ == "__main__":
    loader = SESIDataLoader()
    print("Quality Score:", loader.calculate_quality_index())
