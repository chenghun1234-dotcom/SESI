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
            except:
                pass
        return firestore.client() if firebase_admin._apps else None

    def get_exchange_rate(self):
        try:
            url = "https://open.er-api.com/v6/latest/JPY"
            res = requests.get(url, timeout=10).json()
            return res['rates']['KRW'] if res.get('result') == 'success' else 9.0
        except:
            return 9.0

    def run(self):
        print("SESI Multi-Factor Engine Starting...")
        
        xr = self.get_exchange_rate()
        weights = self.loader.load_grade_weights()
        quality_score = self.loader.calculate_quality_index()
        jp_fees = self.loader.load_jp_fees()
        
        print(f"XR: 1 JPY = {xr:.2f} KRW")
        print(f"Quality Score (KR): {quality_score}")

        # Process Japan
        processed_jp = []
        region_multiplier = 11.40
        for jp in jp_fees:
            jpy_val = jp['unit'] * region_multiplier
            krw_val = jpy_val * xr
            processed_jp.append({
                "country": "JP",
                "category": jp['category'],
                "service_name": jp['name'],
                "grade": str(jp['grade']),
                "krw_value": int(krw_val),
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

        # Process Korea
        raw_kr = self.kr_importer.fetch_from_portal()
        processed_kr = self.kr_importer.index_and_transform(raw_kr)

        # Multi-Factor Indexing
        results = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "exchange_rate": xr,
                "weights": weights,
                "kr_quality_score": quality_score
            },
            "countries": {"JP": processed_jp, "KR": processed_kr},
            "scores": self._calculate_complex_scores(processed_jp, processed_kr, weights, quality_score)
        }

        self._output_results(results)
        if self.db:
            self._upload_to_firestore(processed_jp + processed_kr)
            
        print("SESI Engine Enhancement Completed!")

    def _calculate_complex_scores(self, jp, kr, weights, quality):
        jp_sum = 0
        kr_sum = 0
        for g in ["1", "2", "3", "4", "5"]:
            w = weights.get(g, 0.2)
            jp_f = next((x for x in jp if x['grade'] == g or x['grade'] == 'all'), jp[0])
            kr_f = next((x for x in kr if x['grade'] == g), kr[0])
            jp_sum += jp_f['krw_value'] * w
            kr_sum += kr_f['fee'] * w
            
        # Quality-Adjusted Ratio
        # Lower index means better value (cost per quality unit)
        raw_ratio = kr_sum / jp_sum if jp_sum > 0 else 0
        quality_factor = quality / 100.0
        adjusted_score = raw_ratio / quality_factor if quality_factor > 0 else raw_ratio
        
        return {
            "jp_weighted_avg_krw": int(jp_sum),
            "kr_weighted_avg_krw": int(kr_sum),
            "raw_ratio": round(raw_ratio, 4),
            "quality_adjusted_sesi_score": round(adjusted_score, 4)
        }

    def _output_results(self, results):
        os.makedirs("public/api", exist_ok=True)
        with open("public/api/sesi_index.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print("Static API saved to public/api/sesi_index.json")

    def _upload_to_firestore(self, all_data):
        print(f"Uploading {len(all_data)} items to Firestore...")
        if not self.db: return
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
