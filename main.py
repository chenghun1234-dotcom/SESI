import os
import requests
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from data_loader import SESIDataLoader
from kr_fee_importer import SESIFeeImporter

class SESIEngine:
    def __init__(self):
        self.db = self._init_firebase()
        self.loader = SESIDataLoader()
        self.kr_importer = SESIFeeImporter(db_client=self.db)
        
    def _init_firebase(self):
        """Initializes Firebase from Environment Variables."""
        if not firebase_admin._apps:
            try:
                firebase_key_raw = os.environ.get('FIREBASE_KEY')
                if firebase_key_raw:
                    try:
                        cred_json = json.loads(firebase_key_raw)
                        cred = credentials.Certificate(cred_json)
                    except json.JSONDecodeError:
                        cred = credentials.Certificate(firebase_key_raw)
                    firebase_admin.initialize_app(cred)
                else:
                    print("[WARNING] FIREBASE_KEY not set. Local dry-run mode.")
            except Exception as e:
                print(f"[ERROR] Firebase init failed: {e}")
        return firestore.client() if firebase_admin._apps else None

    def get_exchange_rate(self):
        """Fetches JPY/KRW rate."""
        try:
            url = "https://open.er-api.com/v6/latest/JPY"
            res = requests.get(url, timeout=10).json()
            return res['rates']['KRW'] if res.get('result') == 'success' else 9.0
        except:
            return 9.0

    def run(self):
        print("SESI Engine Starting...")
        
        # 1. Basic Data
        xr = self.get_exchange_rate()
        weights = self.loader.load_grade_weights()
        jp_fees = self.loader.load_jp_fees()
        
        print(f"XR: 1 JPY = {xr:.2f} KRW")
        print(f"Weights Loaded: {weights}")

        # 2. Process Japan (JP)
        processed_jp = []
        region_multiplier = 11.40 # Tokyo Standard
        for jp in jp_fees:
            jpy_val = jp['unit'] * region_multiplier
            krw_val = jpy_val * xr
            processed_jp.append({
                "country": "JP",
                "category": jp['category'],
                "service_name": jp['name'],
                "grade": str(jp['grade']),
                "unit_value": jp['unit'],
                "multiplier": region_multiplier,
                "jpy_value": round(jpy_val, 2),
                "krw_value": int(krw_val),
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        # 3. Process Korea (KR)
        raw_kr = self.kr_importer.fetch_from_portal()
        processed_kr = self.kr_importer.index_and_transform(raw_kr)

        # 4. Calculate Aggregate SESI Index
        # Simple Logic: Average KRW value for Grade 1-5 Visiting Care
        sesi_results = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "exchange_rate": xr,
                "weights": weights
            },
            "countries": {
                "JP": processed_jp,
                "KR": processed_kr
            },
            "scores": self._calculate_scores(processed_jp, processed_kr, weights)
        }

        # 5. Output & Persistence
        self._output_results(sesi_results)
        
        if self.db:
            self._upload_to_firestore(processed_jp + processed_kr)
            
        print("SESI Pipeline Completed Successfully!")

    def _calculate_scores(self, jp, kr, weights):
        """Calculates weighted average scores for comparison."""
        # This is a simplified SESI Score logic
        jp_score = 0
        kr_score = 0
        
        # Calculate Weighted Average daily/per-service costs
        # (This matches Grade 1-5 weights to the fees)
        for g in ["1", "2", "3", "4", "5"]:
            w = weights.get(g, 0.2)
            # Find matching JP facility fee
            jp_f = next((x for x in jp if x['grade'] == g or x['grade'] == 'all'), jp[0])
            kr_f = next((x for x in kr if x['grade'] == g), kr[0])
            
            jp_score += jp_f['krw_value'] * w
            kr_score += kr_f['fee'] * w
            
        return {
            "jp_weighted_avg_krw": int(jp_score),
            "kr_weighted_avg_krw": int(kr_score),
            "ratio": round(kr_score / jp_score, 4) if jp_score > 0 else 0
        }

    def _output_results(self, results):
        """Saves to public/api for static distribution."""
        os.makedirs("public/api", exist_ok=True)
        with open("public/api/sesi_index.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print("Static API saved to public/api/sesi_index.json")

    def _upload_to_firestore(self, all_data):
        print(f"Uploading {len(all_data)} items to Firestore...")
        batch = self.db.batch()
        coll = self.db.collection("SESI_Global_Index")
        for i, item in enumerate(all_data):
            doc_id = f"{item['country']}_{item['service_name']}".replace("/", "_")
            batch.set(coll.document(doc_id), item)
            if (i+1) % 400 == 0:
                batch.commit()
                batch = self.db.batch()
        batch.commit()

if __name__ == "__main__":
    engine = SESIEngine()
    engine.run()
