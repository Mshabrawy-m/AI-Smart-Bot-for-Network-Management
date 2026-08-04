"""Lightweight time-series forecasting for network metrics."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False


class NetworkForecaster:
    """Lightweight forecaster for network metrics."""

    def __init__(self, method: str = "auto"):
        """
        Initialize the forecaster.
        
        Args:
            method: Forecasting method ('auto', 'linear', 'exponential', 'rolling')
        """
        self.method = method
        self.last_model = None

    def forecast_metric(
        self,
        history_df: pd.DataFrame,
        metric: str = "bandwidth_mbps",
        horizon_minutes: int = 30,
        confidence_level: float = 0.95,
    ) -> dict[str, Any]:
        """
        Forecast a metric into the future.
        
        Args:
            history_df: Historical data with timestamp and metric columns
            metric: Name of the metric column to forecast
            horizon_minutes: How many minutes ahead to forecast
            confidence_level: Confidence level for prediction bounds
            
        Returns:
            Dictionary with predicted value, confidence bounds, and metadata
        """
        if metric not in history_df.columns:
            return {
                "predicted_value": None,
                "lower_bound": None,
                "upper_bound": None,
                "error": f"Metric {metric} not found in data",
            }
        
        # Prepare time series
        ts = self._prepare_timeseries(history_df, metric)
        
        if len(ts) < 10:
            return {
                "predicted_value": None,
                "lower_bound": None,
                "upper_bound": None,
                "error": "Insufficient data points (need at least 10)",
            }
        
        # Choose forecasting method
        if self.method == "auto":
            method = self._select_best_method(ts)
        else:
            method = self.method
        
        # Perform forecast
        if method == "exponential" and STATSMODELS_AVAILABLE:
            result = self._forecast_exponential(ts, horizon_minutes, confidence_level)
        elif method == "linear":
            result = self._forecast_linear(ts, horizon_minutes, confidence_level)
        else:  # rolling average
            result = self._forecast_rolling(ts, horizon_minutes, confidence_level)
        
        result["method_used"] = method
        result["data_points_used"] = len(ts)
        
        return result

    def _prepare_timeseries(self, df: pd.DataFrame, metric: str) -> pd.Series:
        """Prepare time series from DataFrame."""
        # Ensure timestamp is datetime
        if 'timestamp' in df.columns:
            df = df.copy()
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            ts = df[metric].dropna()
        else:
            ts = df[metric].dropna()
        
        return ts

    def _select_best_method(self, ts: pd.Series) -> str:
        """Select the best forecasting method based on data characteristics."""
        # Simple heuristic based on trend and seasonality
        if len(ts) < 20:
            return "rolling"  # Not enough data for complex models
        
        # Check for trend
        first_half = ts[:len(ts)//2].mean()
        second_half = ts[len(ts)//2:].mean()
        trend_strength = abs(second_half - first_half) / (first_half + 1e-6)
        
        # Check for seasonality (simple variance check)
        variance = ts.var()
        mean = ts.mean()
        cv = variance / (mean + 1e-6) if mean > 0 else float('inf')
        
        if trend_strength > 0.2 and STATSMODELS_AVAILABLE:
            return "exponential"
        elif cv > 0.5:
            return "rolling"
        else:
            return "linear"

    def _forecast_exponential(
        self,
        ts: pd.Series,
        horizon_minutes: int,
        confidence_level: float,
    ) -> dict[str, Any]:
        """Forecast using exponential smoothing."""
        try:
            # Fit exponential smoothing model
            model = ExponentialSmoothing(
                ts,
                trend='add',
                seasonal=None,
                damped_trend=True,
            ).fit()
            
            # Forecast
            steps = max(1, horizon_minutes // 5)  # Assume 5-minute intervals
            forecast = model.forecast(steps=steps)
            
            predicted = forecast.iloc[-1]
            
            # Simple confidence bounds based on residual std
            residuals = model.resid
            std_error = residuals.std()
            z_score = 1.96  # For 95% confidence
            
            lower_bound = predicted - z_score * std_error
            upper_bound = predicted + z_score * std_error
            
            return {
                "predicted_value": float(predicted),
                "lower_bound": float(lower_bound),
                "upper_bound": float(upper_bound),
                "forecast_horizon_minutes": horizon_minutes,
            }
        
        except Exception as e:
            # Fallback to linear if exponential fails
            return self._forecast_linear(ts, horizon_minutes, confidence_level)

    def _forecast_linear(
        self,
        ts: pd.Series,
        horizon_minutes: int,
        confidence_level: float,
    ) -> dict[str, Any]:
        """Forecast using linear regression on recent trend."""
        # Use last N points for trend
        n_points = min(20, len(ts))
        recent_ts = ts[-n_points:]
        
        x = np.arange(len(recent_ts))
        y = recent_ts.values
        
        # Linear regression
        coeffs = np.polyfit(x, y, 1)
        slope, intercept = coeffs
        
        # Predict future point
        steps = max(1, horizon_minutes // 5)
        predicted = slope * (len(recent_ts) + steps) + intercept
        
        # Confidence bounds based on residual std
        y_pred = slope * x + intercept
        residuals = y - y_pred
        std_error = residuals.std()
        z_score = 1.96  # For 95% confidence
        
        lower_bound = predicted - z_score * std_error
        upper_bound = predicted + z_score * std_error
        
        return {
            "predicted_value": float(predicted),
            "lower_bound": float(lower_bound),
            "upper_bound": float(upper_bound),
            "forecast_horizon_minutes": horizon_minutes,
        }

    def _forecast_rolling(
        self,
        ts: pd.Series,
        horizon_minutes: int,
        confidence_level: float,
    ) -> dict[str, Any]:
        """Forecast using rolling average (baseline method)."""
        # Use rolling mean of recent data
        window = min(10, len(ts))
        recent_mean = ts[-window:].mean()
        recent_std = ts[-window:].std()
        
        # Predict future as recent mean (no trend assumption)
        predicted = recent_mean
        
        # Confidence bounds based on recent std
        z_score = 1.96  # For 95% confidence
        lower_bound = predicted - z_score * recent_std
        upper_bound = predicted + z_score * recent_std
        
        return {
            "predicted_value": float(predicted),
            "lower_bound": float(lower_bound),
            "upper_bound": float(upper_bound),
            "forecast_horizon_minutes": horizon_minutes,
        }

    def check_capacity_threshold(
        self,
        history_df: pd.DataFrame,
        metric: str = "bandwidth_mbps",
        capacity_threshold: float = 100.0,
        horizon_minutes: int = 30,
    ) -> dict[str, Any]:
        """
        Check if forecasted value will exceed capacity threshold.
        
        Args:
            history_df: Historical data
            metric: Metric to forecast
            capacity_threshold: Threshold value to check against
            horizon_minutes: Forecast horizon
            
        Returns:
            Dictionary with prediction and threshold breach warning
        """
        forecast = self.forecast_metric(history_df, metric, horizon_minutes)
        
        if forecast.get("predicted_value") is None:
            return {
                **forecast,
                "will_exceed_threshold": False,
                "threshold": capacity_threshold,
            }
        
        predicted = forecast["predicted_value"]
        will_exceed = predicted > capacity_threshold
        
        if will_exceed:
            forecast["warning"] = f"Forecasted {metric} ({predicted:.1f}) will exceed capacity threshold ({capacity_threshold}) within {horizon_minutes} minutes"
        else:
            forecast["info"] = f"Forecasted {metric} ({predicted:.1f}) is within capacity threshold ({capacity_threshold})"
        
        forecast["will_exceed_threshold"] = will_exceed
        forecast["threshold"] = capacity_threshold
        
        return forecast
