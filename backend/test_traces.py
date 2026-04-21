import asyncio
import os
from app.core.config import settings
from app.services.twilio.trace_store import _read_latest_trace_call_sid, _read_call_trace

async def main():
    call_sid = await _read_latest_trace_call_sid()
    if not call_sid:
        print("No recent call trace found in Redis.")
        return
    
    print(f"Traces for Call SID: {call_sid}")
    traces = await _read_call_trace(call_sid, since=0.0)
    for t in traces:
        print(t)

if __name__ == "__main__":
    asyncio.run(main())
