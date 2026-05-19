---
phase: 3
title: "News RSS scraping + Gemini sentiment scoring"
status: pending
priority: P2
effort: "1.5w"
dependencies: [2]
risk: HIGH — may drop entirely if Vietstock blocks or Gemini cost overruns
---

# Phase 3: News + Sentiment Scoring

## Overview
Tin tức công ty + sentiment scoring. **Highest risk slice** — có drop policy nếu RSS bị block hoặc Gemini cost vượt budget.

**Source changes vs V1:** CafeF DROPPED (verified blocked). Vietstock RSS only. FireAnt API optional fallback.

## Requirements

### Functional
- Vietstock RSS scraper: parse XML, extract symbol mentions
- Gemini 2.5 Flash importance scoring (0-10) với brief summary
- Cron 6h pipeline run
- Dedup news by normalized URL
- News markers trên chart (color khác corp/earnings/macro)
- Default UI: hide news <7/10 importance; toggle để show all
- Importance threshold slider

### Non-functional
- Gemini cost hard cap: $5/month
- Symbol extraction false positive rate <5%
- Pipeline fault-tolerant (Gemini fail → fallback rule-based)

## Architecture

```
Backend:
  app/services/events/
    vietstock_rss_scraper.py    (parse XML feed, extract symbols)
    fireant_api_source.py       (OPTIONAL fallback)
    importance_scorer.py        (Gemini API + cache + rule-based fallback)
  
Cron job (scheduler.py):
  every 6h → fetch_news → score → store (extends events_pipeline)
  
Frontend:
  Enable news filter checkbox (Phase 2 placeholder)
  Add importance threshold slider
  Update event-aggregator to handle news color
```

## Related Code Files

### Modify
- `backend/app/services/events/events_pipeline.py` — add news integration
- `backend/app/scheduler.py` — add news refresh job (every 6h)
- `frontend/src/components/charts/event-filters.tsx` — enable news checkbox
- `frontend/src/components/charts/event-importance-slider.tsx` — new component

### Create
- `backend/app/services/events/vietstock_rss_scraper.py`
- `backend/app/services/events/fireant_api_source.py` (optional)
- `backend/app/services/events/importance_scorer.py`
- `backend/app/services/events/symbol_extractor.py`
- `backend/data/vn30-tickers.txt` (whitelist for regex filter)
- `backend/tests/test_vietstock_rss_scraper.py`
- `backend/tests/test_importance_scorer.py`
- `backend/tests/test_symbol_extractor.py`
- `frontend/src/components/charts/event-importance-slider.tsx`

## Implementation Steps

### Step 0: Risk gate (BEFORE coding)
1. Re-verify Vietstock RSS still works: `curl -I https://vietstock.vn/830/chung-khoan/co-phieu.rss` → expect 200
2. Verify `GEMINI_API_KEY` working: small test call
3. Compute cost estimate based on actual feed item count × 6h frequency
4. **Decision:** if any check fails → revisit options:
   - Drop Phase 3, ship Phase 4 sớm
   - Use rule-based scoring only (skip Gemini)
   - Manual news ingestion (skip pipeline)

### Step 1: Vietstock RSS scraper
```python
# app/services/events/vietstock_rss_scraper.py
import logging
import asyncio
from datetime import datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

FEEDS = [
    "https://vietstock.vn/830/chung-khoan/co-phieu.rss",      # stocks
    # Add more as discovered
]


class VietstockRSSScraper:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "VN-Stock-Tracker/1.0"},
        )

    async def fetch_all(self) -> list[dict]:
        items: list[dict] = []
        for feed_url in FEEDS:
            items.extend(await self._fetch_feed(feed_url))
        return items

    async def _fetch_feed(self, url: str) -> list[dict]:
        try:
            r = await self._client.get(url)
            r.raise_for_status()
            return self._parse(r.text)
        except Exception as exc:
            logger.warning(f"Vietstock RSS fetch failed {url}: {exc}")
            return []

    def _parse(self, xml_text: str) -> list[dict]:
        root = ET.fromstring(xml_text)
        items = []
        for item in root.iter("item"):
            link = item.findtext("link", "")
            title = item.findtext("title", "")
            description = item.findtext("description", "")
            pub_date_str = item.findtext("pubDate", "")
            try:
                ts = parsedate_to_datetime(pub_date_str)
            except Exception:
                ts = datetime.now()
            items.append({
                "url": link,
                "title": title.strip(),
                "description": description.strip(),
                "ts": ts,
                "source": "vietstock",
            })
        return items
```

### Step 2: Symbol extractor
```python
# app/services/events/symbol_extractor.py
import re
from pathlib import Path

WHITELIST_FILE = Path(__file__).parent.parent.parent.parent / "data" / "vn30-tickers.txt"
TICKER_RE = re.compile(r"\b[A-Z]{3,4}\b")


def load_whitelist() -> set[str]:
    if not WHITELIST_FILE.exists():
        return set()
    return {line.strip() for line in WHITELIST_FILE.read_text().splitlines() if line.strip()}


def extract_symbols(text: str, whitelist: set[str]) -> list[str]:
    """Return VN30 tickers mentioned in text. Filtered against whitelist to avoid false positives."""
    candidates = set(TICKER_RE.findall(text))
    return sorted(candidates & whitelist)
```

`backend/data/vn30-tickers.txt` (one ticker per line):
```
ACB
BCM
BID
BVH
CTG
FPT
GAS
GVR
HDB
HPG
LPB
MBB
MSN
MWG
PLX
SAB
SHB
SSB
SSI
STB
TCB
TPB
VCB
VHM
VIB
VIC
VJC
VNM
VPB
VRE
```

### Step 3: Importance scorer (Gemini Flash + cache + fallback)
```python
# app/services/events/importance_scorer.py
import asyncio
import hashlib
import json
import logging
from pathlib import Path

import google.generativeai as genai

from app.config import settings

logger = logging.getLogger(__name__)

CACHE_DIR = Path("/tmp/event-scorer-cache")
CACHE_DIR.mkdir(exist_ok=True)


class ImportanceScorer:
    MAX_MONTHLY_CALLS = 1000

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            logger.warning("GEMINI_API_KEY not set; using rule-based fallback only")
            self._model = None
        else:
            genai.configure(api_key=settings.gemini_api_key)
            self._model = genai.GenerativeModel("gemini-2.5-flash")
        self._monthly_calls = self._load_monthly_count()

    async def score(self, item: dict) -> tuple[int, str]:
        """Returns (importance 0-10, summary 1-line)."""
        cache_key = self._cache_key(item)
        cached = self._read_cache(cache_key)
        if cached:
            return cached["importance"], cached["summary"]

        if self._model is None or self._monthly_calls >= self.MAX_MONTHLY_CALLS:
            return self._fallback_score(item), self._fallback_summary(item)

        try:
            result = await self._gemini_call(item)
            self._write_cache(cache_key, result)
            self._monthly_calls += 1
            return result["importance"], result["summary"]
        except Exception as exc:
            logger.warning(f"Gemini scoring failed: {exc}")
            return self._fallback_score(item), self._fallback_summary(item)

    async def _gemini_call(self, item: dict) -> dict:
        prompt = f"""Bạn là analyst chứng khoán Việt Nam. Chấm điểm importance (0-10) cho tin tức sau:
Title: {item['title']}
Description: {item.get('description', '')[:500]}

Trả về JSON: {{"importance": int 0-10, "summary": "1 câu tóm tắt impact"}}.
0-3 = noise (giá hợp tác mua hàng, sự kiện routine). 4-6 = moderate (M&A nhỏ, top management thay đổi).
7-10 = high impact (earnings beat/miss, dividend special, regulatory, M&A lớn, exec resignation).
"""
        resp = await asyncio.to_thread(
            self._model.generate_content, prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        return json.loads(resp.text)

    def _fallback_score(self, item: dict) -> int:
        """Rule-based: keyword presence in title."""
        title = item.get("title", "").lower()
        HIGH = ["earnings", "cổ tức", "lợi nhuận", "kết quả kinh doanh", "phát hành", "chia tách"]
        MED = ["bổ nhiệm", "miễn nhiệm", "đại hội cổ đông", "hợp tác"]
        if any(k in title for k in HIGH):
            return 7
        if any(k in title for k in MED):
            return 5
        return 3

    def _fallback_summary(self, item: dict) -> str:
        return item.get("title", "")[:200]

    def _cache_key(self, item: dict) -> str:
        raw = item.get("url") or item["title"]
        return hashlib.sha256(raw.encode()).hexdigest()

    def _read_cache(self, key: str) -> dict | None:
        f = CACHE_DIR / f"{key}.json"
        if f.exists():
            return json.loads(f.read_text())
        return None

    def _write_cache(self, key: str, data: dict) -> None:
        (CACHE_DIR / f"{key}.json").write_text(json.dumps(data))

    def _load_monthly_count(self) -> int:
        # Track monthly Gemini call count for budget cap
        counter = CACHE_DIR / "monthly_count.txt"
        if not counter.exists():
            return 0
        from datetime import datetime
        try:
            month, count = counter.read_text().strip().split(":")
            if month == datetime.now().strftime("%Y-%m"):
                return int(count)
        except Exception:
            pass
        return 0
```

### Step 4: Integrate into events_pipeline.py
```python
# events_pipeline.py — add method
async def run_news_refresh(self) -> int:
    scraper = VietstockRSSScraper()
    extractor_whitelist = load_whitelist()
    scorer = ImportanceScorer()

    items = await scraper.fetch_all()
    stored = 0
    for raw in items:
        symbols = extract_symbols(raw["title"] + " " + raw["description"], extractor_whitelist)
        importance, summary = await scorer.score(raw)
        # 1 event per mentioned symbol (or 1 with symbol=NULL if no symbols)
        targets = symbols or [None]
        for sym in targets:
            event = {
                "ts": raw["ts"],
                "symbol": sym,
                "event_type": "news",
                "title": raw["title"],
                "summary": summary,
                "url": raw["url"],
                "source": raw["source"],
                "importance": importance,
            }
            stored += await self._store([event])
    return stored
```

### Step 5: Cron job
```python
# scheduler.py — add
async def _news_refresh():
    pipeline = EventsPipeline()
    count = await pipeline.run_news_refresh()
    logger.info(f"News refresh stored {count} items")

scheduler.add_job(
    _news_refresh,
    CronTrigger(hour="*/6", timezone="Asia/Saigon"),
    id="news_refresh_6h",
    replace_existing=True,
)
```

### Step 6: Frontend importance slider
```tsx
// src/components/charts/event-importance-slider.tsx
export function EventImportanceSlider({
  value, onChange,
}: { value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-xs text-gray-400">Min importance: {value}</label>
      <input
        type="range" min="0" max="10" step="1"
        value={value} onChange={(e) => onChange(Number(e.target.value))}
        className="w-32"
      />
    </div>
  );
}
```

### Step 7: Enable news filter checkbox
Update Phase 2 `event-filters.tsx`: remove `disabled` on news item.

### Step 8: Wire min_importance to API call
```ts
// use-events.ts — extend
export function useEvents(
  symbol: string, start: string, end: string,
  types: string[], minImportance = 7,
) {
  // ... include min_importance in fetch URL
}
```

### Step 9: Cost monitoring + alert
Add Prometheus counter for Gemini calls; alert if monthly count >800 (warning before hard limit at 1000).

### Step 10: Docs sync
- Append `docs/api-reference.md` events endpoint với new params
- Update `docs/system-architecture.md` news pipeline section
- Document cost/budget tracking in `docs/monitoring.md`

## Tests (TDD order)

1. **Unit (backend)**: `test_vietstock_rss_scraper.py`
   - Parse fixed XML fixture → list of items với correct fields
   - Failed fetch returns `[]` (not raise)
2. **Unit**: `test_symbol_extractor.py`
   - "BID, VCB tăng" với whitelist VN30 → ["BID", "VCB"]
   - "API, URL, JSON" với whitelist → [] (false positives filtered)
3. **Unit**: `test_importance_scorer.py`
   - Cache hit returns cached value, no Gemini call
   - Monthly limit exceeded → rule-based fallback
   - Gemini failure → rule-based fallback
   - Rule-based "earnings" keyword → score ≥7
4. **Integration**: pipeline E2E with mocked scraper + scorer
5. **Manual E2E**: chạy `_news_refresh()` manually, verify DB rows

## Success Criteria

- [ ] Risk gate passed (Vietstock + Gemini available)
- [ ] Vietstock scraper parses real feed (>5 items)
- [ ] Symbol extractor < 5% false positive on 100 sample items
- [ ] Gemini scorer cache works (2nd call same URL → no API hit)
- [ ] Cron 6h registered
- [ ] DB has news rows after 1 manual run
- [ ] Chart shows news markers with gray color
- [ ] Importance slider hides/shows markers correctly
- [ ] Backend tests ≥10 new
- [ ] Docs updated

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Vietstock blocks our scraper | UA rotation, respect robots.txt, reasonable rate. Fallback FireAnt API |
| Gemini key not provided | Fallback rule-based scoring only (functional but lower quality) |
| Gemini cost overrun | Hard cap MAX_MONTHLY_CALLS=1000. Counter persisted. Alert at 80%. |
| Symbol extraction noise | Whitelist filter + manual review of first 100 events |
| News too noisy on chart | Default min_importance=7 hides low-impact items |
| Pipeline fails silently | Prometheus counters: `news_fetch_total`, `news_fetch_errors`, `news_scored_total` |

## Drop Policy

Phase 3 can be **safely abandoned** without affecting Phase 4-5:
- Phase 2 already provides corp/earnings/macro events
- Phase 4 indicators work independently
- Decision: if risk gate fails OR 1 week in we're stuck on RSS/Gemini → skip phase, mark as deferred, move to Phase 4
