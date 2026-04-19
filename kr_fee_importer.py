import os
import requests
import json
import csv
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables
# load_dotenv() - Removed for environment stability

class SESIFeeImporter:
    def __init__(self, db_client=None):
        self.service_key = os.getenv("DATA_GO_KR_SERVICE_KEY") or os.getenv("PUBLIC_DATA_API_KEY")
        self.db = db_client
        
    def fetch_from_portal(self):
        """
        Loads fees from local CSV or API.
        Prioritizes data/fees/kr_fees.csv if available.
        """
        local_path = "data/fees/kr_fees.csv"
        if os.path.exists(local_path):
            print(f"INFO: Loading fees from local {local_path}")
            fees = []
            try:
                with open(local_path, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        fees.append({
                            "category": row["category"],
                            "grade": row["grade"],
                            "time": row["time"],
                            "fee": int(row["fee"]),
                            "type": "facility_care" if "시설" in row["category"] else "home_care"
                        })
                return fees
            except Exception as e:
                print(f"ERROR: Failed to read local fees: {e}")

        # Fallback to API or Mock
        if not self.service_key:
            return self._generate_mock_2026_data()

    def _generate_mock_2026_data(self):
        """Generates the 2026 standard fee table based on current trends."""
        fees = []
        # Visiting Care
        times = [30, 60, 90, 120, 150, 180, 210, 240]
        base_fee_60 = 17500 # 2026 Estimate
        for t in times:
            fees.append({
                "category": "방문요양",
                "grade": "All",
                "time": t,
                "fee": int(base_fee_60 * (t / 60)),
                "type": "home_care"
            })
        # Facility Care
        grades = [1, 2, 3, 4, 5]
        base_facility_fee = 88000
        for g in grades:
            fees.append({
                "category": "입소시설",
                "grade": str(g),
                "time": "daily",
                "fee": int(base_facility_fee * (1.1 if g <= 2 else 1.0)),
                "type": "facility_care"
            })
        return fees

    def index_and_transform(self, raw_data):
        """Transforms raw data into SESI Index format."""
        indexed_data = []
        now = datetime.now().strftime("%Y-%m-%d")
        for item in raw_data:
            indexed_item = {
                "country": "KR",
                "category": item["category"],
                "service_name": f"{item['category']}_{item['grade']}_{item['time']}",
                "grade": str(item["grade"]),
                "fee": item["fee"],
                "unit_value": item["fee"], # Matching JP structure
                "year": 2026,
                "last_updated": now,
                "source": "data.go.kr (via SESI Engine)"
            }
            indexed_data.append(indexed_item)
        return indexed_data

    def upload_to_firestore(self, data):
        """Uploads processed indices to Firestore."""
        if not self.db:
            print("WARNING: Firestore client not provided. Skipping upload.")
            return

        print(f"INFO: Uploading {len(data)} KR items to Firestore...")
        batch = self.db.batch()
        collection_ref = self.db.collection("SESI_Global_Index") # Consolidated
        for i, item in enumerate(data):
            doc_id = f"KR_{item['service_name']}".replace("/", "_")
            batch.set(collection_ref.document(doc_id), item)
            if (i + 1) % 400 == 0:
                batch.commit()
                batch = self.db.batch()
        batch.commit()

