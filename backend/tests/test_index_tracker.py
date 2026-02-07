"""Tests for IndexTracker — breadth ratio, intraday sparkline, multi-index."""

from app.models.domain import IndexData, IntradayPoint
from app.models.ssi_messages import SSIIndexMessage
from app.services.index_tracker import IndexTracker


def _make_msg(
    index_id="VN30",
    index_value=1250.5,
    prior_index_value=1245.0,
    change=5.5,
    ratio_change=0.44,
    total_qtty=500_000_000,
    advances=20,
    declines=8,
    no_changes=2,
):
    return SSIIndexMessage(
        index_id=index_id,
        index_value=index_value,
        prior_index_value=prior_index_value,
        change=change,
        ratio_change=ratio_change,
        total_qtty=total_qtty,
        advances=advances,
        declines=declines,
        no_changes=no_changes,
    )


class TestBasicUpdate:
    def test_stores_index_values(self):
        tracker = IndexTracker()
        result = tracker.update(_make_msg(index_value=1250.5, change=5.5))
        assert result.value == 1250.5
        assert result.change == 5.5

    def test_prior_value_stored(self):
        tracker = IndexTracker()
        result = tracker.update(_make_msg(prior_index_value=1245.0))
        assert result.prior_value == 1245.0

    def test_volume_and_breadth_counts(self):
        tracker = IndexTracker()
        result = tracker.update(_make_msg(
            total_qtty=500_000_000, advances=20, declines=8, no_changes=2
        ))
        assert result.total_volume == 500_000_000
        assert result.advances == 20
        assert result.declines == 8
        assert result.no_changes == 2

    def test_ratio_change_stored(self):
        tracker = IndexTracker()
        result = tracker.update(_make_msg(ratio_change=0.44))
        assert result.ratio_change == 0.44

    def test_last_updated_set(self):
        tracker = IndexTracker()
        result = tracker.update(_make_msg())
        assert result.last_updated is not None

    def test_returns_index_data(self):
        tracker = IndexTracker()
        result = tracker.update(_make_msg())
        assert isinstance(result, IndexData)


class TestBreadthRatio:
    def test_advance_ratio_computed(self):
        tracker = IndexTracker()
        result = tracker.update(_make_msg(advances=20, declines=10))
        # 20 / (20 + 10) = 0.6667
        assert abs(result.advance_ratio - 20 / 30) < 0.001

    def test_advance_ratio_all_advancing(self):
        tracker = IndexTracker()
        result = tracker.update(_make_msg(advances=30, declines=0))
        assert result.advance_ratio == 1.0

    def test_advance_ratio_all_declining(self):
        tracker = IndexTracker()
        result = tracker.update(_make_msg(advances=0, declines=30))
        assert result.advance_ratio == 0.0

    def test_advance_ratio_zero_when_no_data(self):
        tracker = IndexTracker()
        result = tracker.update(_make_msg(advances=0, declines=0))
        assert result.advance_ratio == 0.0

    def test_advance_ratio_equal_split(self):
        tracker = IndexTracker()
        result = tracker.update(_make_msg(advances=15, declines=15))
        assert result.advance_ratio == 0.5


class TestIntradaySparkline:
    def test_intraday_points_accumulated(self):
        tracker = IndexTracker()
        tracker.update(_make_msg(index_value=1250.0))
        tracker.update(_make_msg(index_value=1251.0))
        tracker.update(_make_msg(index_value=1252.0))
        data = tracker.get("VN30")
        assert len(data.intraday) == 3
        assert data.intraday[0].value == 1250.0
        assert data.intraday[2].value == 1252.0

    def test_intraday_points_are_intraday_point_type(self):
        tracker = IndexTracker()
        tracker.update(_make_msg(index_value=1250.0))
        data = tracker.get("VN30")
        assert isinstance(data.intraday[0], IntradayPoint)

    def test_intraday_skips_zero_values(self):
        tracker = IndexTracker()
        tracker.update(_make_msg(index_value=0.0))
        points = tracker.get_intraday("VN30")
        assert len(points) == 0

    def test_get_intraday_returns_list(self):
        tracker = IndexTracker()
        tracker.update(_make_msg(index_value=1250.0))
        points = tracker.get_intraday("VN30")
        assert isinstance(points, list)
        assert len(points) == 1

    def test_get_intraday_unknown_index(self):
        tracker = IndexTracker()
        points = tracker.get_intraday("UNKNOWN")
        assert points == []


class TestMultipleIndices:
    def test_separate_tracking(self):
        tracker = IndexTracker()
        tracker.update(_make_msg(index_id="VN30", index_value=1250.0))
        tracker.update(_make_msg(index_id="VNINDEX", index_value=1300.0))
        assert tracker.get("VN30").value == 1250.0
        assert tracker.get("VNINDEX").value == 1300.0

    def test_get_all(self):
        tracker = IndexTracker()
        tracker.update(_make_msg(index_id="VN30"))
        tracker.update(_make_msg(index_id="VNINDEX"))
        tracker.update(_make_msg(index_id="HNX"))
        all_data = tracker.get_all()
        assert len(all_data) == 3
        assert "VN30" in all_data
        assert "VNINDEX" in all_data
        assert "HNX" in all_data

    def test_get_all_returns_copy(self):
        tracker = IndexTracker()
        tracker.update(_make_msg(index_id="VN30"))
        result = tracker.get_all()
        result["FAKE"] = IndexData(index_id="FAKE")
        assert "FAKE" not in tracker.get_all()

    def test_intraday_separate_per_index(self):
        tracker = IndexTracker()
        tracker.update(_make_msg(index_id="VN30", index_value=1250.0))
        tracker.update(_make_msg(index_id="VN30", index_value=1251.0))
        tracker.update(_make_msg(index_id="VNINDEX", index_value=1300.0))
        assert len(tracker.get_intraday("VN30")) == 2
        assert len(tracker.get_intraday("VNINDEX")) == 1


class TestGetVn30Value:
    def test_returns_value(self):
        tracker = IndexTracker()
        tracker.update(_make_msg(index_id="VN30", index_value=1250.5))
        assert tracker.get_vn30_value() == 1250.5

    def test_returns_zero_when_not_tracked(self):
        tracker = IndexTracker()
        assert tracker.get_vn30_value() == 0.0

    def test_updates_on_new_message(self):
        tracker = IndexTracker()
        tracker.update(_make_msg(index_id="VN30", index_value=1250.0))
        tracker.update(_make_msg(index_id="VN30", index_value=1260.0))
        assert tracker.get_vn30_value() == 1260.0


class TestGetUnknown:
    def test_get_unknown_returns_none(self):
        tracker = IndexTracker()
        assert tracker.get("UNKNOWN") is None


class TestReset:
    def test_reset_clears_all(self):
        tracker = IndexTracker()
        tracker.update(_make_msg(index_id="VN30"))
        tracker.update(_make_msg(index_id="VNINDEX"))
        tracker.reset()
        assert tracker.get_all() == {}
        assert tracker.get("VN30") is None
        assert tracker.get_vn30_value() == 0.0

    def test_reset_clears_intraday(self):
        tracker = IndexTracker()
        tracker.update(_make_msg(index_value=1250.0))
        tracker.reset()
        assert tracker.get_intraday("VN30") == []

    def test_can_update_after_reset(self):
        tracker = IndexTracker()
        tracker.update(_make_msg(index_value=1250.0))
        tracker.reset()
        tracker.update(_make_msg(index_value=1260.0))
        assert tracker.get("VN30").value == 1260.0
        assert len(tracker.get_intraday("VN30")) == 1
