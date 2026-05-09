"""
tools/anomaly.py
Isolation Forest anomaly detection for transaction data.
Detects: statistical outliers, velocity fraud, structuring patterns.
"""

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Transactions just below ₹1,00,000 (₹99,500–₹99,999) = structuring signal
STRUCTURING_LOW = 99_500
STRUCTURING_HIGH = 99_999


def _engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create numeric features from raw transaction DataFrame for IsolationForest.
    Expected columns: date, txn_id, amount, merchant, city, type
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    df["hour"] = df["date"].dt.hour.fillna(12)
    df["day_of_week"] = df["date"].dt.dayofweek.fillna(0)
    df["is_debit"] = (df.get("type", "debit").str.lower() == "debit").astype(int)

    # Rolling 24-hour count per city (velocity signal)
    df = df.sort_values("date")
    df["city_velocity"] = (
        df.groupby("city")["date"]
        .transform(lambda s: s.expanding().count())
        .fillna(1)
    )

    # Number of distinct cities in 24h window
    df["unique_cities_day"] = df.groupby(df["date"].dt.date)["city"].transform("nunique").fillna(1)

    return df


def run_isolation_forest(
    transactions: list[dict[str, Any]],
    contamination: float = 0.1,
) -> dict[str, Any]:
    """
    Run Isolation Forest on a list of transaction dicts.

    Returns:
        {
          "anomaly_score": float (0-100),
          "flagged_transactions": list[dict],
          "structuring_flags": list[dict],
          "velocity_flags": list[dict],
          "total_transactions": int,
          "flagged_count": int,
        }
    """
    if not transactions:
        return {
            "anomaly_score": 0.0,
            "flagged_transactions": [],
            "structuring_flags": [],
            "velocity_flags": [],
            "total_transactions": 0,
            "flagged_count": 0,
        }

    df = pd.DataFrame(transactions)
    required = {"date", "amount"}
    missing = required - set(df.columns)
    if missing:
        logger.warning("Transactions missing columns: %s", missing)
        for col in missing:
            df[col] = None

    df = _engineer_features(df)

    feature_cols = ["amount", "hour", "day_of_week", "is_debit", "city_velocity", "unique_cities_day"]
    X = df[feature_cols].fillna(0).values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        n_jobs=-1,
    )
    preds = model.fit_predict(X_scaled)          # -1 = anomaly, 1 = normal
    scores = model.score_samples(X_scaled)       # more negative = more anomalous

    df["is_anomaly"] = preds == -1
    df["anomaly_raw_score"] = scores

    # Normalize anomaly score to 0–100 (higher = more anomalous overall)
    flagged_ratio = df["is_anomaly"].mean()
    anomaly_score = round(flagged_ratio * 100, 2)

    flagged_df = df[df["is_anomaly"]].copy()

    # Structuring detection: amounts just below 1 lakh
    structuring_mask = df["amount"].between(STRUCTURING_LOW, STRUCTURING_HIGH)
    structuring_df = df[structuring_mask]

    # Velocity fraud: multiple distinct cities on the same day
    velocity_mask = df["unique_cities_day"] >= 3
    velocity_df = df[velocity_mask]

    def _to_records(subset: pd.DataFrame) -> list[dict]:
        cols = [c for c in ["txn_id", "date", "amount", "merchant", "city", "type", "anomaly_raw_score"] if c in subset.columns]
        records = subset[cols].copy()
        records["date"] = records["date"].astype(str)
        return records.to_dict(orient="records")

    return {
        "anomaly_score": anomaly_score,
        "flagged_transactions": _to_records(flagged_df),
        "structuring_flags": _to_records(structuring_df),
        "velocity_flags": _to_records(velocity_df),
        "total_transactions": len(df),
        "flagged_count": int(df["is_anomaly"].sum()),
    }
