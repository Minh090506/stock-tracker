"""Tests for CorrelationEngine — Pearson correlation, min samples, window, reset."""

from app.models.domain import CorrelationData
from app.services.correlation_engine import CorrelationEngine, _pearson


class TestPearsonFunction:
    def test_perfect_positive_correlation(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        assert abs(_pearson(x, y) - 1.0) < 0.001

    def test_perfect_negative_correlation(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 8.0, 6.0, 4.0, 2.0]
        assert abs(_pearson(x, y) - (-1.0)) < 0.001

    def test_zero_correlation(self):
        # Symmetric around mean → no linear relationship
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 1.0, 4.0, 2.0]
        r = _pearson(x, y)
        assert abs(r) < 0.5  # near zero, not exact

    def test_too_few_samples_returns_zero(self):
        assert _pearson([1.0, 2.0], [3.0, 4.0]) == 0.0
        assert _pearson([1.0], [2.0]) == 0.0
        assert _pearson([], []) == 0.0

    def test_constant_series_returns_zero(self):
        # Zero variance in y → denominator is 0
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [5.0, 5.0, 5.0, 5.0, 5.0]
        assert _pearson(x, y) == 0.0

    def test_known_correlation_value(self):
        # Known Pearson r ≈ 0.9919 for these data points
        x = [10.0, 20.0, 30.0, 40.0, 50.0]
        y = [12.0, 18.0, 31.0, 42.0, 48.0]
        r = _pearson(x, y)
        assert abs(r - 0.9919) < 0.01

    def test_large_near_constant_values_stay_real(self):
        # Large near-constant inputs (e.g. accumulated net velocity) can make a
        # variance term slightly negative via float cancellation; the sqrt must
        # not turn complex and the comparison must not raise.
        x = [
            266403927.40139613,
            266403927.40041828,
            266403927.4008487,
            266403927.40025848,
            266403927.40151292,
        ]
        y = [0.0, 0.5, 1.0, 0.0, 0.5]
        r = _pearson(x, y)
        assert isinstance(r, float)
        assert -1.0 <= r <= 1.0


class TestCorrelationEngine:
    def test_returns_correlation_data(self):
        engine = CorrelationEngine(window_minutes=10)
        result = engine.get_correlation()
        assert isinstance(result, CorrelationData)

    def test_min_samples_guard(self):
        engine = CorrelationEngine(window_minutes=10)
        # Feed 3 ticks (need 5 min for meaningful correlation)
        for price in [100.0, 101.0, 102.0]:
            engine.on_minute_tick(net_velocity=10.0, vn30f_price=price)
        result = engine.get_correlation()
        # First tick doesn't produce a point (no prev_price), so only 2 points
        assert result.sample_size < 5
        assert result.coefficient == 0.0

    def test_first_tick_stores_price_only(self):
        engine = CorrelationEngine(window_minutes=10)
        engine.on_minute_tick(net_velocity=10.0, vn30f_price=100.0)
        # No point stored yet (need prev_price for delta)
        assert len(engine._points) == 0

    def test_correlation_with_sufficient_data(self):
        engine = CorrelationEngine(window_minutes=20)
        # Positive correlation: higher velocity → larger price jump
        # Price deltas must VARY and correlate with velocity
        base_price = 1300.0
        velocities = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        price_steps = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        cumulative = base_price
        for vel, step in zip(velocities, price_steps):
            cumulative += step
            engine.on_minute_tick(float(vel), cumulative)
        result = engine.get_correlation()
        assert result.sample_size >= 5
        # Velocity and price_delta both increase → positive correlation
        assert result.coefficient > 0.5

    def test_negative_correlation(self):
        engine = CorrelationEngine(window_minutes=20)
        # Negative correlation: higher velocity → larger price DROP
        base_price = 1300.0
        velocities = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        price_steps = [-0.1, -0.2, -0.3, -0.4, -0.5, -0.6, -0.7, -0.8, -0.9, -1.0]
        cumulative = base_price
        for vel, step in zip(velocities, price_steps):
            cumulative += step
            engine.on_minute_tick(float(vel), cumulative)
        result = engine.get_correlation()
        assert result.sample_size >= 5
        assert result.coefficient < -0.5

    def test_window_minutes_in_result(self):
        engine = CorrelationEngine(window_minutes=30)
        result = engine.get_correlation()
        assert result.window_minutes == 30


class TestWindowExpiry:
    def test_old_points_expire(self):
        engine = CorrelationEngine(window_minutes=5)
        # Feed 8 ticks → deque maxlen=5, oldest 3 should be dropped
        for i in range(8):
            engine.on_minute_tick(float(i * 10), 1300.0 + i)
        # First tick produces no point, so 7 points created, 5 retained
        assert len(engine._points) == 5


class TestReset:
    def test_reset_clears_all(self):
        engine = CorrelationEngine()
        for i in range(10):
            engine.on_minute_tick(float(i * 10), 1300.0 + i)
        engine.reset()
        assert len(engine._points) == 0
        assert engine._prev_price is None

    def test_can_use_after_reset(self):
        engine = CorrelationEngine()
        engine.on_minute_tick(10.0, 1300.0)
        engine.reset()
        engine.on_minute_tick(20.0, 1301.0)
        # Should work fine after reset
        assert engine._prev_price == 1301.0


class TestLastUpdated:
    def test_last_updated_set(self):
        engine = CorrelationEngine()
        result = engine.get_correlation()
        assert result.last_updated is not None
