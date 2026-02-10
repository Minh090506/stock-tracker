# Phase 02: Backend API Extension

## Priority: P1
## Status: Pending
## Effort: 30m

## Context Links
- `backend/app/routers/market_router.py` - Existing /api/market/volume-stats endpoint
- `backend/app/models/domain.py` - SessionStats with session breakdown
- Phase 01 output: Extended SessionStats model

## Overview

Update `/api/market/volume-stats` endpoint to return enhanced SessionStats with session breakdown data. No new endpoint needed - enhance existing one.

## Key Insights

- `/api/market/volume-stats` already exists but unused by frontend
- Returns `{"stats": [SessionStats, ...]}` - just need to include new fields
- Pydantic auto-serializes SessionBreakdown objects
- Frontend will use this instead of polling snapshot quotes

## Requirements

**Functional:**
- Return SessionStats with ato/continuous/atc breakdown
- Maintain existing response format `{"stats": [...]}`
- No breaking changes to existing response structure

**Non-functional:**
- Response time under 50ms (in-memory data)
- JSON schema compatible with frontend types

## Architecture

```
GET /api/market/volume-stats
    ↓
MarketDataProcessor.aggregator.get_all_stats()
    ↓
List[SessionStats] (with session breakdown)
    ↓
Pydantic JSON serialization
    ↓
Frontend: VolumeStatsResponse type
```

## Related Code Files

**To Modify:**
- `backend/app/routers/market_router.py` - No changes needed (Pydantic auto-serializes)

**To Create:**
- None - Phase 01 changes sufficient

**To Test:**
- Manual: `curl http://localhost:8000/api/market/volume-stats`
- Frontend type alignment in Phase 03

## Implementation Steps

1. **Verify /api/market/volume-stats endpoint** still works:
   - Endpoint at line 31-37 in market_router.py
   - Returns aggregator.get_all_stats().values()
   - Pydantic will auto-serialize new SessionBreakdown fields

2. **Test response format** matches expected schema:
   ```json
   {
     "stats": [{
       "symbol": "VNM",
       "mua_chu_dong_volume": 1000,
       "ato": {"mua_chu_dong_volume": 100, ...},
       "continuous": {"mua_chu_dong_volume": 800, ...},
       "atc": {"mua_chu_dong_volume": 100, ...}
     }]
   }
   ```

3. **Optional: Add query params** for session filtering (YAGNI - skip for now)

## Todo List

- [ ] Start backend dev server
- [ ] Trigger some trades to populate session data
- [ ] Test GET /api/market/volume-stats with curl
- [ ] Verify JSON includes ato/continuous/atc fields
- [ ] Check response structure matches VolumeStatsResponse type

## Success Criteria

- GET /api/market/volume-stats returns 200
- Response includes session breakdown (ato/continuous/atc) for each symbol
- Existing fields unchanged (backward compatible)
- Response time under 50ms
- JSON validates against frontend types

## Risk Assessment

**Risks:**
- Pydantic serialization error with nested models → Low (BaseModel standard behavior)
- Response too large with session data → Very low (30 symbols × 3 sessions = minimal overhead)

**Mitigation:**
- Test with dev tools before frontend integration
- Monitor response size (expect <10KB for 30 VN30 symbols)

## Security Considerations

- No authentication required (public market data)
- No rate limiting needed (read-only, in-memory)

## Next Steps

After completion:
- Phase 03: Create frontend types for session breakdown
- Phase 03: Add pressure bars to volume detail table
