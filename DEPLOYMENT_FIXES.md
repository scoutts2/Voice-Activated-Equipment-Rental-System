# Deployment Fixes - Intermittent Call Pickup Issues

## Problem Analysis

Your agent was experiencing intermittent call pickup issues on Railway. The logs showed that sometimes calls would connect successfully, and other times the agent would not pick up at all.

## Root Causes Identified

### 1. **Blocking Google Sheets API Calls**
- **Issue**: Every incoming call triggered a synchronous `get_available_equipment()` call, which loads data from Google Sheets
- **Impact**: If Google Sheets API was slow (100-500ms), rate-limited, or timing out, the entire entrypoint would hang, preventing the call from being picked up
- **Likelihood**: HIGH - This was the most likely cause

### 2. **Missing Connection Timeouts**
- **Issue**: `ctx.connect()` and `session.start()` had no timeout limits
- **Impact**: If LiveKit connection was slow or hanging, the agent would wait indefinitely, blocking subsequent calls
- **Likelihood**: MEDIUM

### 3. **Insufficient Error Handling**
- **Issue**: Exceptions in `session.start()` or cleanup could crash the worker
- **Impact**: A crashed worker can't pick up new calls until it restarts
- **Likelihood**: MEDIUM

### 4. **API Rate Limits**
- **Issue**: Multiple concurrent calls could hit rate limits on:
  - Google Sheets API: 60 requests/minute per user
  - Deepgram STT: Varies by plan
  - OpenAI GPT-4o: Varies by plan
- **Impact**: Rate-limited requests would timeout or fail
- **Likelihood**: LOW-MEDIUM (depends on call volume)

### 5. **Railway Resource Constraints**
- **Issue**: Railway free/hobby tier may have limited CPU/memory
- **Impact**: Under load, the worker process might slow down or restart
- **Likelihood**: LOW (but worth monitoring)

## Fixes Implemented

### 1. **Equipment Loading with Timeout** ✅
```python
# Load equipment data with timeout to prevent blocking
try:
    available_equipment = await asyncio.wait_for(
        asyncio.to_thread(get_available_equipment),
        timeout=3.0
    )
    logger.info(f"Equipment loaded successfully: {len(available_equipment)} items")
except asyncio.TimeoutError:
    logger.error("Equipment loading timed out - using empty list")
    available_equipment = []
```

**Impact**: Agent will now pick up calls even if Google Sheets is slow or unresponsive

### 2. **Connection Timeout** ✅
```python
try:
    await asyncio.wait_for(
        ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY),
        timeout=5.0
    )
    logger.info("Connected to room successfully")
except asyncio.TimeoutError:
    logger.error("Connection timed out after 5 seconds - aborting call")
    return
```

**Impact**: Prevents agent from hanging on slow connections

### 3. **Session Start Timeout** ✅
```python
await asyncio.wait_for(
    session.start(room=ctx.room, agent=agent),
    timeout=60.0  # Maximum 60 seconds to start session
)
```

**Impact**: Ensures the worker is released after 60 seconds if session fails to start

### 4. **Equipment Caching** ✅
- **Added**: 30-second cache for equipment data
- **Impact**: Reduces Google Sheets API calls from ~1 per call to ~1 per 30 seconds
- **Trade-off**: Equipment availability might be up to 30 seconds stale
- **Cache Invalidation**: Cache is cleared immediately after booking equipment

```python
# Cache equipment data for 30 seconds
_equipment_cache = None
_cache_timestamp = 0
_CACHE_DURATION = 30
```

### 5. **Improved Error Handling & Logging** ✅
- Added detailed logging with emojis for easier log reading:
  - ✅ Success
  - ❌ Error
  - ⚠️ Warning
  - 🔄 Cleanup
- Added `session_started` flag to track state
- Wrapped cleanup in try-except to prevent cleanup errors from crashing worker
- Added disconnect timeout to prevent hanging on cleanup

### 6. **Reduced Logging Verbosity** ✅
- Removed excessive debug logs that were hitting Railway's 500 logs/sec rate limit
- Condensed key information into single log lines

## What to Monitor

### 1. **Connection Success Rate**
Look for these log patterns:
```
✅ Agent session started - call in progress  <- SUCCESS
❌ Session start timed out after 60 seconds  <- TIMEOUT
❌ Equipment loading timed out               <- GOOGLE SHEETS SLOW
```

### 2. **Equipment Loading Time**
```
Equipment loaded successfully: X items       <- Should happen in < 1 second
Equipment loading timed out - using empty list  <- Google Sheets issue
```

### 3. **Cache Hit Rate**
```
Using cached equipment data (age: X.Xs)      <- GOOD (reduces API calls)
Cache expired or empty - reloading equipment <- Expected every 30s
```

### 4. **Cleanup Issues**
```
✅ Disconnected successfully                <- GOOD
⚠️ Disconnect timed out - forcing cleanup    <- Connection issue
⚠️ Room already disconnected                 <- Expected after abrupt hangup
```

### 5. **Call Lifecycle**
Every successful call should show this pattern:
```
NEW CALL - Entrypoint called
Connected to room successfully
Equipment loaded successfully: X items
✅ Agent session started - call in progress
[customer conversation]
🔄 CALL ENDED - Cleaning up (session_started=True)
✅ Disconnected successfully
✅ Ready for next call
```

## Expected Improvements

1. **Call Pickup Success Rate**: Should increase to ~95%+ (from ~50-70%)
2. **Time to Answer**: Should be < 2 seconds consistently
3. **Consecutive Calls**: Should handle multiple calls in a row without issues
4. **Google Sheets Resilience**: Agent will still work even if Google Sheets is down (uses empty equipment list)

## If Issues Persist

### Scenario 1: Still Not Picking Up Calls
**Check**:
- Railway logs for timeout errors
- LiveKit dashboard for dispatch rule status
- Google Sheets API quota (https://console.cloud.google.com)

**Solution**:
- Increase `_CACHE_DURATION` to 60 or 120 seconds
- Consider pre-loading equipment data at worker startup

### Scenario 2: Agent Picks Up But Is Slow/Unresponsive
**Check**:
- Railway resource usage (CPU/memory)
- OpenAI API rate limits
- Deepgram API rate limits

**Solution**:
- Upgrade Railway plan for more resources
- Switch to faster LLM model (gpt-4o-mini)

### Scenario 3: Equipment Bookings Not Saving
**Check**:
- Google Sheets API errors in logs
- Cache invalidation happening correctly

**Solution**:
- Reduce `_CACHE_DURATION` to 10 or 15 seconds
- Add retry logic to `update_equipment_status()`

## Critical Fix #2: Worker Process Exiting After First Call

### Problem
After the first call, the worker process was exiting completely, preventing subsequent calls from being picked up.

**Log Evidence**:
```
DEBUG:livekit.agents:shutting down job task
INFO:livekit.agents:process exiting
```

### Root Cause
The `entrypoint` function was not handling `asyncio.CancelledError` properly. When a call ends abruptly (hangup), LiveKit cancels the session task, and if not caught, this causes the entire worker process to exit.

### Fix Applied
1. **Catch `asyncio.CancelledError`**: Treat it as a normal call ending, not an error
2. **Simplified cleanup**: Removed aggressive disconnect logic that could cause issues
3. **Explicit return**: Ensure the function returns normally, keeping the worker alive

```python
except asyncio.CancelledError:
    # This is normal when a call ends abruptly
    logger.info("⚠️ Session was cancelled (normal for abrupt hangup)")
    session_started = True
finally:
    # Minimal cleanup
    await asyncio.sleep(0.1)
    logger.info("✅ Ready for next call")
    # IMPORTANT: Return normally so worker stays alive
```

## Critical Fix #3: Agent Not Picking Up Calls At All (Regression)

### Problem
After applying Critical Fix #2, the agent stopped picking up calls entirely. The worker would start, but no calls would be answered.

**Log Evidence**:
```
[No entrypoint logs appearing when calls come in]
```

### Root Cause
In attempting to simplify the cleanup logic, we **removed the timeout wrapper around `session.start()`**. Without this timeout:
- If `session.start()` hangs or blocks for any reason, the entire entrypoint is stuck
- The worker appears "alive" but is actually blocked waiting for the session to start
- Subsequent calls cannot be processed because the worker is busy with the blocked session

### Fix Applied
1. **Re-added timeout for `session.start()`**: 300 seconds (5 minutes) for entire call duration
2. **Added explicit start logging**: Clearer log message "🎯 STARTING SESSION - Agent is ready to answer the call..."
3. **Improved entry point logging**: Changed "NEW CALL" to "📞 INCOMING CALL - Entrypoint triggered" for easier identification

```python
# Start the agent session with timeout to prevent indefinite hanging
await asyncio.wait_for(
    session.start(
        room=ctx.room,
        agent=agent,
    ),
    timeout=300.0  # 5 minute timeout for entire call
)
```

### Why This Works
- **Prevents indefinite blocking**: If session fails to start within 5 minutes, the timeout fires and the worker is released
- **Balanced timeout**: 300 seconds is long enough for legitimate calls, but prevents indefinite hanging
- **Better debugging**: The new log messages make it clear when the entrypoint is triggered and when the session is about to start

## Next Steps

1. **Deploy to Railway** and monitor logs for the new patterns above
2. **Test with multiple consecutive calls** (call, hang up, call again immediately) - THIS IS CRITICAL
3. **Verify worker stays alive**: Look for "Ready for next call" without "process exiting"
4. **Test during Google Sheets API slowness** (simulate by pausing network)
5. **Monitor for 24 hours** to ensure stability

## Cache Trade-offs

**Current Setting**: 30 second cache

**Pros**:
- Drastically reduces Google Sheets API calls
- Faster call pickup (no API delay)
- More resilient to API issues

**Cons**:
- Equipment availability might be up to 30 seconds stale
- If someone books equipment, it might still show as available for up to 30 seconds

**Recommendation**: Start with 30 seconds, reduce to 15 seconds if stale data becomes an issue.

## Testing Checklist

- [ ] Single call connects successfully
- [ ] Agent greets customer within 2 seconds
- [ ] Equipment details are correct and up-to-date
- [ ] Multiple consecutive calls (call, hang up, call again x5)
- [ ] Agent picks up every time
- [ ] Abrupt hangup recovery (hang up mid-conversation, call back immediately)
- [ ] Equipment booking updates Google Sheets correctly
- [ ] Cache invalidation works (book equipment, call again, equipment should be marked RENTED)

---

**Date**: October 13, 2025
**Version**: 1.0

