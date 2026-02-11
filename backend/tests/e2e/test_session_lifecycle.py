"""E2E: Session lifecycle — ATO → Continuous → ATC state transitions.

Validates SessionAggregator phase breakdown, reset behavior,
and volume invariants across trading session phases.
"""

import pytest


@pytest.mark.asyncio
async def test_ato_trades_classified_separately(wired_system, f):
    """ATO trades accumulate in ato breakdown, not continuous."""
    proc = wired_system["processor"]

    await proc.handle_quote(f.quote("VNM", bid=80.0, ask=80.5))
    await proc.handle_trade(f.trade("VNM", price=80.5, volume=100, session="ATO"))

    stats = proc.aggregator.get_stats("VNM")
    assert stats.ato.total_volume == 100
    assert stats.continuous.total_volume == 0
    assert stats.atc.total_volume == 0


@pytest.mark.asyncio
async def test_continuous_and_atc_phases_separate(wired_system, f):
    """Continuous (LO) and ATC trades accumulate independently."""
    proc = wired_system["processor"]

    await proc.handle_quote(f.quote("VNM", bid=80.0, ask=80.5))

    # Continuous trades (LO session)
    await proc.handle_trade(f.trade("VNM", price=80.5, volume=50, session="LO"))
    await proc.handle_trade(f.trade("VNM", price=80.5, volume=50, session="LO"))

    # ATC trade
    await proc.handle_trade(f.trade("VNM", price=80.0, volume=200, session="ATC"))

    stats = proc.aggregator.get_stats("VNM")
    assert stats.continuous.total_volume == 100
    assert stats.atc.total_volume == 200
    assert stats.total_volume == 300


@pytest.mark.asyncio
async def test_session_reset_clears_aggregates_preserves_quotes(wired_system, f):
    """Reset clears aggregator stats but quote cache persists."""
    proc = wired_system["processor"]

    await proc.handle_quote(f.quote("VNM", bid=80.0, ask=80.5))
    await proc.handle_trade(f.trade("VNM", price=80.5, volume=100))

    assert proc.aggregator.get_stats("VNM").total_volume == 100
    assert proc.quote_cache.get_bid_ask("VNM") == (80.0, 80.5)

    proc.reset_session()

    # Aggregator cleared
    assert proc.aggregator.get_stats("VNM").total_volume == 0
    # Quote cache preserved — trade classification still works
    assert proc.quote_cache.get_bid_ask("VNM") == (80.0, 80.5)


@pytest.mark.asyncio
async def test_phase_volume_invariant(wired_system, f):
    """Sum of ATO + Continuous + ATC volumes equals total_volume."""
    proc = wired_system["processor"]

    await proc.handle_quote(f.quote("VNM", bid=80.0, ask=80.5))

    await proc.handle_trade(f.trade("VNM", price=80.5, volume=100, session="ATO"))
    await proc.handle_trade(f.trade("VNM", price=80.5, volume=200, session="LO"))
    await proc.handle_trade(f.trade("VNM", price=80.5, volume=50, session="ATC"))

    stats = proc.aggregator.get_stats("VNM")
    phase_sum = (
        stats.ato.total_volume
        + stats.continuous.total_volume
        + stats.atc.total_volume
    )
    assert phase_sum == stats.total_volume
    assert stats.total_volume == 350


@pytest.mark.asyncio
async def test_classification_works_after_reset(wired_system, f):
    """After reset, new trades still classify correctly (quote cache persists)."""
    proc = wired_system["processor"]

    await proc.handle_quote(f.quote("VNM", bid=80.0, ask=80.5))
    await proc.handle_trade(f.trade("VNM", price=80.5, volume=100))
    proc.reset_session()

    # New trade at bid price → ban_chu_dong
    await proc.handle_trade(f.trade("VNM", price=80.0, volume=50))
    stats = proc.aggregator.get_stats("VNM")
    assert stats.ban_chu_dong_volume == 50
    assert stats.total_volume == 50
