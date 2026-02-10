# Phase 01: Backend Session Tracking

## Priority: P1
## Status: Pending
## Effort: 1h

## Context Links
- `backend/app/services/session_aggregator.py` - Main service to modify
- `backend/app/models/domain.py` - SessionStats model
- `backend/app/services/trade_classifier.py` - ClassifiedTrade has timestamp
- `backend/app/models/ssi_messages.py` - SSITradeMessage has trading_session field

## Overview

Extend `SessionStats` model to track volumes per trading session phase (ATO/Continuous/ATC). Modify `SessionAggregator.add_trade()` to distribute volumes into correct session bucket based on `trading_session` field from SSI.

## Key Insights

- SSI provides `trading_session` field: "ATO", "ATC", or empty (continuous)
- VN sessions: ATO 9:00-9:15, Continuous 9:15-14:30, ATC 14:30-14:45
- Current `SessionStats` only tracks totals - need nested breakdown
- `ClassifiedTrade` already has trade_type and timestamp

## Requirements

**Functional:**
- Track buy/sell/neutral volumes separately for ATO/Continuous/ATC
- Maintain backward compatibility with existing total fields
- Reset behavior unchanged (15:00 daily reset)

**Non-functional:**
- Minimal overhead (3 session counters per symbol)
- Files under 200 LOC
- Type-safe Pydantic models

## Architecture

```
SSITradeMessage (trading_session field)
    ↓
TradeClassifier (classify() adds timestamp)
    ↓
SessionAggregator.add_trade()
    ↓ (detect session from trading_session field)
SessionStats (3 session breakdowns: ato/continuous/atc)
```

## Related Code Files

**To Modify:**
- `backend/app/models/domain.py` - Add SessionBreakdown model, extend SessionStats
- `backend/app/services/session_aggregator.py` - Implement session detection logic

**No New Files**

## Implementation Steps

1. **Add SessionBreakdown model** in `domain.py`:
   ```python
   class SessionBreakdown(BaseModel):
       mua_chu_dong_volume: int = 0
       ban_chu_dong_volume: int = 0
       neutral_volume: int = 0
       total_volume: int = 0
   ```

2. **Extend SessionStats** with session fields:
   ```python
   class SessionStats(BaseModel):
       # ... existing fields ...
       ato: SessionBreakdown = SessionBreakdown()
       continuous: SessionBreakdown = SessionBreakdown()
       atc: SessionBreakdown = SessionBreakdown()
   ```

3. **Update SessionAggregator.add_trade()** to:
   - Accept `trading_session` parameter (pass from ClassifiedTrade)
   - Detect session: "ATO" → ato, "ATC" → atc, else → continuous
   - Update both total counters AND session breakdown
   - Keep existing logic for trade_type classification

4. **Modify TradeClassifier** to pass trading_session:
   - Store `trading_session` from SSITradeMessage in ClassifiedTrade
   - Pass to SessionAggregator

5. **Update ClassifiedTrade model** to include trading_session:
   ```python
   class ClassifiedTrade(BaseModel):
       # ... existing fields ...
       trading_session: str = ""
   ```

## Todo List

- [ ] Add SessionBreakdown Pydantic model to domain.py
- [ ] Add ato/continuous/atc fields to SessionStats model
- [ ] Add trading_session field to ClassifiedTrade model
- [ ] Update TradeClassifier.classify() to capture trading_session
- [ ] Update SessionAggregator.add_trade() session detection logic
- [ ] Test reset() behavior (should clear session breakdowns)

## Success Criteria

- SessionStats includes 3 SessionBreakdown objects (ato/continuous/atc)
- ClassifiedTrade includes trading_session field
- SessionAggregator distributes volumes to correct session bucket
- Existing total fields still accurate (sum of sessions)
- reset() clears all session data
- Type hints pass mypy checks

## Risk Assessment

**Risks:**
- trading_session field missing/None from SSI → Default to "continuous"
- Backward compatibility broken for API consumers → Keep all existing fields

**Mitigation:**
- Fallback logic: if trading_session empty/unknown → "continuous"
- Don't remove existing total fields - session breakdowns are additive

## Security Considerations

- No security implications (read-only data aggregation)
- No user input validation needed (internal SSI data)

## Next Steps

After completion:
- Phase 02: Update /api/market/volume-stats to return session breakdown
- Write unit tests for SessionAggregator session logic
