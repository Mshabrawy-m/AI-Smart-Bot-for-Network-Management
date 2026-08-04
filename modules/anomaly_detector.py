"""ML-based anomaly detection using Isolation Forest."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


class AnomalyDetector:
    """ML-based anomaly detection using Isolation Forest."""

    def __init__(self, contamination: float = 0.1, random_state: int = 42):
        """
        Initialize the anomaly detector.
        
        Args:
            contamination: Expected proportion of outliers in the dataset
            random_state: Random seed for reproducibility
        """
        self.contamination = contamination
        self.random_state = random_state
        self.model: IsolationForest | None = None
        self.feature_columns: list[str] = []
        self.is_fitted = False

    def fit(self, history_df: pd.DataFrame) -> None:
        """
        Train the Isolation Forest model on historical data.
        
        Args:
            history_df: DataFrame with historical metrics. Should contain
                       columns like bandwidth_mbps, latency_ms, packet_loss_pct, etc.
        """
        # Select numerical features for anomaly detection
        numeric_cols = history_df.select_dtypes(include=[np.number]).columns.tolist()
        
        # Filter out timestamp and ID columns
        feature_cols = [col for col in numeric_cols 
                       if col not in ['timestamp', 'id', 'device_id']]
        
        if not feature_cols:
            raise ValueError("No numerical features found for anomaly detection")
        
        self.feature_columns = feature_cols
        
        # Prepare training data
        X = history_df[feature_cols].fillna(0).values
        
        # Train Isolation Forest
        self.model = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=100,
            max_samples='auto',
        )
        
        self.model.fit(X)
        self.is_fitted = True

    def predict(self, current_metrics: dict[str, float]) -> dict[str, Any]:
        """
        Predict if current metrics are anomalous.
        
        Args:
            current_metrics: Dictionary of current metric values
            
        Returns:
            Dictionary with:
                - is_anomaly: bool indicating if anomalous
                - anomaly_score: float anomaly score (lower = more anomalous)
                - feature_contributions: dict of which features contributed most
        """
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model must be fitted before prediction")
        
        # Prepare input vector
        feature_values = []
        for col in self.feature_columns:
            value = current_metrics.get(col, 0)
            feature_values.append(value)
        
        X = np.array([feature_values])
        
        # Get prediction and score
        prediction = self.model.predict(X)[0]  # 1 = normal, -1 = anomaly
        score = self.model.decision_function(X)[0]  # Lower = more anomalous
        
        # Calculate feature contributions (simplified)
        contributions = {}
        for i, col in enumerate(self.feature_columns):
            contributions[col] = abs(feature_values[i])
        
        return {
            'is_anomaly': prediction == -1,
            'anomaly_score': float(score),
            'feature_contributions': contributions,
        }

    def predict_batch(self, metrics_df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict anomalies for a batch of metrics.
        
        Args:
            metrics_df: DataFrame with metric values
            
        Returns:
            DataFrame with added columns: is_anomaly, anomaly_score
        """
        if not self.is_fitted or self.model is None:
            raise RuntimeError("Model must be fitted before prediction")
        
        # Ensure all feature columns exist
        for col in self.feature_columns:
            if col not in metrics_df.columns:
                metrics_df[col] = 0
        
        X = metrics_df[self.feature_columns].fillna(0).values
        
        predictions = self.model.predict(X)
        scores = self.model.decision_function(X)
        
        result_df = metrics_df.copy()
        result_df['is_anomaly'] = predictions == -1
        result_df['anomaly_score'] = scores
        
        return result_df

    def evaluate(self, test_df: pd.DataFrame, true_labels: list[int]) -> dict[str, float]:
        """
        Evaluate the detector against labeled test data.
        
        Args:
            test_df: Test data with features
            true_labels: True anomaly labels (1 = anomaly, 0 = normal)
            
        Returns:
            Dictionary with precision, recall, f1, false_positive_rate
        """
        predictions = self.predict_batch(test_df)
        pred_labels = (predictions['is_anomaly'].astype(int)).tolist()
        
        # Calculate metrics
        tp = sum(1 for p, t in zip(pred_labels, true_labels) if p == 1 and t == 1)
        fp = sum(1 for p, t in zip(pred_labels, true_labels) if p == 1 and t == 0)
        tn = sum(1 for p, t in zip(pred_labels, true_labels) if p == 0 and t == 0)
        fn = sum(1 for p, t in zip(pred_labels, true_labels) if p == 0 and t == 1)
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        
        return {
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'false_positive_rate': fpr,
            'true_positives': tp,
            'false_positives': fp,
            'true_negatives': tn,
            'false_negatives': fn,
        }


def inject_synthetic_anomalies(
    history_df: pd.DataFrame,
    anomaly_rate: float = 0.05,
    severity: float = 3.0
) -> tuple[pd.DataFrame, list[int]]:
    """
    Inject synthetic anomalies into historical data for evaluation.
    
    Args:
        history_df: Original historical data
        anomaly_rate: Proportion of data points to make anomalous
        severity: Multiplier for anomaly magnitude
        
    Returns:
        Tuple of (modified_df, anomaly_labels) where labels are 1 for anomaly, 0 for normal
    """
    df = history_df.copy()
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_cols = [col for col in numeric_cols if col not in ['timestamp', 'id', 'device_id']]
    
    n_samples = len(df)
    n_anomalies = int(n_samples * anomaly_rate)
    
    labels = [0] * n_samples
    anomaly_indices = np.random.choice(n_samples, n_anomalies, replace=False)
    
    for idx in anomaly_indices:
        # Randomly select which feature to make anomalous
        feature = np.random.choice(numeric_cols)
        
        # Apply anomaly (either spike or drop)
        if np.random.random() > 0.5:
            df.loc[idx, feature] *= severity  # Spike
        else:
            df.loc[idx, feature] /= severity  # Drop
        
        labels[idx] = 1
    
    return df, labels
