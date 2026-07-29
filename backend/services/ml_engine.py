import logging
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from services.nasa_client import get_solar_flares, get_cme_events
from services.noaa_client import get_kp_index_1hour
from services.cache import save_prediction

logger = logging.getLogger(__name__)

CLASS_LABELS = ["Quiet", "C-class", "M-class", "X-class"]

FLARE_CLASS_MAP = {
    "A": 0, "B": 0, "C": 1, "M": 2, "X": 3
}


def _encode_class(class_str: str) -> int:
    """Encode flare class string to numeric label."""
    if not class_str:
        return 0
    prefix = class_str[0].upper()
    return FLARE_CLASS_MAP.get(prefix, 0)


def _parse_location(loc: str):
    """Parse heliographic location like 'N25E30' into lat/lon."""
    if not loc or len(loc) < 5:
        return 0.0, 0.0
    try:
        import re
        m = re.match(r'([NS])(\d+)([EW])(\d+)', loc)
        if m:
            lat = float(m.group(2)) * (1 if m.group(1) == 'N' else -1)
            lon = float(m.group(4)) * (1 if m.group(3) == 'E' else -1)
            return lat, lon
    except Exception:
        pass
    return 0.0, 0.0


class MLEngine:
    def __init__(self):
        self.model: Pipeline | None = None
        self.trained_at: datetime | None = None
        self.feature_names = [
            "flare_class_encoded",
            "flare_lat",
            "flare_lon",
            "flares_last_7d",
            "x_class_last_7d",
            "m_class_last_7d",
            "c_class_last_7d",
            "cme_count_last_7d",
            "avg_kp_last_24h",
            "max_kp_last_24h",
            "active_region_num",
        ]

    async def _build_training_data(self):
        """Build feature matrix from NASA/NOAA data."""
        flares = await get_solar_flares(days=90)
        cmes = await get_cme_events(days=90)
        kp_data = await get_kp_index_1hour()

        if not flares:
            return self._synthetic_training_data()

        X, y = [], []

        for i, flare in enumerate(flares):
            try:
                # Parse flare time
                begin_str = flare.get("beginTime", "")
                flare_dt = datetime.strptime(begin_str[:16], "%Y-%m-%dT%H:%M") if begin_str else datetime.utcnow()

                # Class encoding
                class_str = flare.get("classType", "C1.0")
                class_encoded = _encode_class(class_str)

                # Location
                loc = flare.get("sourceLocation", "N00E00")
                lat, lon = _parse_location(loc)

                # Active region
                ar_num = flare.get("activeRegionNum") or 0
                ar_num = float(ar_num) if ar_num else 13000.0

                # Count flares in prior 7 days
                prior_flares = [
                    f for f in flares
                    if f.get("beginTime") and
                    abs((datetime.strptime(f["beginTime"][:16], "%Y-%m-%dT%H:%M") - flare_dt).days) <= 7
                ]
                flares_last_7d = len(prior_flares)
                x_class_last_7d = sum(1 for f in prior_flares if f.get("classType", "").startswith("X"))
                m_class_last_7d = sum(1 for f in prior_flares if f.get("classType", "").startswith("M"))
                c_class_last_7d = sum(1 for f in prior_flares if f.get("classType", "").startswith("C"))

                # CME count near this flare
                cme_count = sum(
                    1 for c in cmes
                    if c.get("startTime") and
                    abs((datetime.strptime(c["startTime"][:16], "%Y-%m-%dT%H:%M") - flare_dt).days) <= 7
                )

                # Kp statistics
                kp_values = []
                for k in kp_data:
                    kp_val = k.get("kp") or k.get("Kp") or 0
                    try:
                        kp_values.append(float(str(kp_val).replace("+", "").replace("-", "")))
                    except Exception:
                        pass

                avg_kp = float(np.mean(kp_values)) if kp_values else 2.0
                max_kp = float(np.max(kp_values)) if kp_values else 3.0

                features = [
                    class_encoded,
                    lat,
                    lon,
                    flares_last_7d,
                    x_class_last_7d,
                    m_class_last_7d,
                    c_class_last_7d,
                    cme_count,
                    avg_kp,
                    max_kp,
                    ar_num,
                ]

                # Label: predict class of NEXT flare (shift by 1)
                if i + 1 < len(flares):
                    next_class = _encode_class(flares[i + 1].get("classType", "C1.0"))
                else:
                    next_class = class_encoded

                X.append(features)
                y.append(next_class)

            except Exception as ex:
                logger.debug(f"Skipping flare due to parse error: {ex}")
                continue

        if len(X) < 5:
            return self._synthetic_training_data()

        return np.array(X, dtype=float), np.array(y, dtype=int)

    def _synthetic_training_data(self):
        """Generate realistic synthetic training data as fallback."""
        np.random.seed(42)
        n = 500
        X = np.column_stack([
            np.random.randint(0, 4, n),            # flare class
            np.random.uniform(-60, 60, n),          # lat
            np.random.uniform(-90, 90, n),          # lon
            np.random.randint(1, 20, n),            # flares 7d
            np.random.randint(0, 3, n),             # X-class 7d
            np.random.randint(0, 8, n),             # M-class 7d
            np.random.randint(1, 15, n),            # C-class 7d
            np.random.randint(0, 5, n),             # CME count
            np.random.uniform(0, 5, n),             # avg Kp
            np.random.uniform(1, 9, n),             # max Kp
            np.random.randint(12800, 13200, n),     # AR num
        ])
        # Labels: weighted towards quiet/c-class (realistic distribution)
        y = np.random.choice([0, 1, 2, 3], n, p=[0.45, 0.35, 0.15, 0.05])
        return X.astype(float), y.astype(int)

    async def train(self):
        """Train the Random Forest model."""
        logger.info("🤖 Training ML model...")
        try:
            X, y = await self._build_training_data()

            pipeline = Pipeline([
                ("scaler", StandardScaler()),
                ("clf", RandomForestClassifier(
                    n_estimators=150,
                    class_weight="balanced",
                    max_depth=10,
                    random_state=42,
                    n_jobs=-1,
                )),
            ])
            pipeline.fit(X, y)
            self.model = pipeline
            self.trained_at = datetime.utcnow()
            logger.info(f"✅ Model trained on {len(X)} samples. Classes: {np.unique(y).tolist()}")
        except Exception as e:
            logger.error(f"Training failed: {e}")
            self._train_fallback()

    def _train_fallback(self):
        """Train on synthetic data as last resort."""
        X, y = self._synthetic_training_data()
        pipeline = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", RandomForestClassifier(n_estimators=100, class_weight="balanced", random_state=42)),
        ])
        pipeline.fit(X, y)
        self.model = pipeline
        self.trained_at = datetime.utcnow()
        logger.info("✅ Fallback model trained on synthetic data.")

    async def predict(self, flares: list, cmes: list, kp_data: list) -> dict:
        """Generate a prediction using the latest space weather data."""
        if not self.model:
            await self.train()

        try:
            # Build current feature vector from latest data
            now = datetime.utcnow()
            recent_flares = flares[:20] if flares else []
            latest_class = _encode_class(recent_flares[0].get("classType", "C1.0") if recent_flares else "C1.0")
            lat, lon = _parse_location(recent_flares[0].get("sourceLocation", "N00E00") if recent_flares else "N00E00")
            ar_num = float(recent_flares[0].get("activeRegionNum") or 13000) if recent_flares else 13000.0

            flares_7d = len([f for f in recent_flares if f.get("beginTime")])
            x_7d = sum(1 for f in recent_flares if f.get("classType", "").startswith("X"))
            m_7d = sum(1 for f in recent_flares if f.get("classType", "").startswith("M"))
            c_7d = sum(1 for f in recent_flares if f.get("classType", "").startswith("C"))
            cme_count = len(cmes[:10]) if cmes else 0

            kp_values = []
            for k in kp_data:
                try:
                    v = float(str(k.get("kp") or k.get("Kp", 0)).replace("+", "").replace("-", ""))
                    kp_values.append(v)
                except Exception:
                    pass

            avg_kp = float(np.mean(kp_values)) if kp_values else 2.0
            max_kp = float(np.max(kp_values)) if kp_values else 3.0

            features = np.array([[
                latest_class, lat, lon, flares_7d, x_7d, m_7d, c_7d,
                cme_count, avg_kp, max_kp, ar_num,
            ]], dtype=float)

            probs = self.model.predict_proba(features)[0]
            classes = self.model.classes_

            # Map probabilities to labels
            prob_map = {int(c): float(p) for c, p in zip(classes, probs)}
            quiet_p = prob_map.get(0, 0.0)
            c_p = prob_map.get(1, 0.0)
            m_p = prob_map.get(2, 0.0)
            x_p = prob_map.get(3, 0.0)

            # Ensure they sum to 1
            total = quiet_p + c_p + m_p + x_p
            if total > 0:
                quiet_p /= total
                c_p /= total
                m_p /= total
                x_p /= total

            predicted_idx = int(np.argmax([quiet_p, c_p, m_p, x_p]))
            predicted_class = CLASS_LABELS[predicted_idx]
            confidence = max(quiet_p, c_p, m_p, x_p)

            # Feature importances
            rf = self.model.named_steps["clf"]
            importances = rf.feature_importances_.tolist()
            feat_imp = dict(zip(self.feature_names, importances))

            result = {
                "predicted_class": predicted_class,
                "confidence": round(confidence * 100, 1),
                "probabilities": {
                    "quiet": round(quiet_p * 100, 1),
                    "c_class": round(c_p * 100, 1),
                    "m_class": round(m_p * 100, 1),
                    "x_class": round(x_p * 100, 1),
                },
                "feature_importances": {k: round(v * 100, 1) for k, v in feat_imp.items()},
                "model_trained_at": self.trained_at.isoformat() if self.trained_at else None,
                "input_summary": {
                    "recent_flares_7d": flares_7d,
                    "recent_cmes_7d": cme_count,
                    "avg_kp": round(avg_kp, 2),
                    "max_kp": round(max_kp, 2),
                    "latest_flare_class": recent_flares[0].get("classType", "N/A") if recent_flares else "N/A",
                },
                "generated_at": now.isoformat(),
            }

            await save_prediction({
                "quiet": quiet_p,
                "c_class": c_p,
                "m_class": m_p,
                "x_class": x_p,
                "predicted_class": predicted_class,
                "confidence": confidence,
            })

            return result

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return self._default_prediction()

    def _default_prediction(self) -> dict:
        return {
            "predicted_class": "C-class",
            "confidence": 55.0,
            "probabilities": {"quiet": 30.0, "c_class": 40.0, "m_class": 20.0, "x_class": 10.0},
            "feature_importances": {},
            "model_trained_at": None,
            "input_summary": {},
            "generated_at": datetime.utcnow().isoformat(),
        }
