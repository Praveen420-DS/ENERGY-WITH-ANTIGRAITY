"""Process-local defense-in-depth limiter matching the Nginx prediction rate."""
from __future__ import annotations
import threading,time

class ElectricityCandidateRateLimiter:
    def __init__(self,rate:float=10.0,capacity:float=20.0): self.rate=rate; self.capacity=capacity; self._state={}; self._lock=threading.Lock()
    def allow(self,key:str,now:float|None=None)->bool:
        current=time.monotonic() if now is None else now
        with self._lock:
            tokens,last=self._state.get(key,(self.capacity,current)); tokens=min(self.capacity,tokens+max(0,current-last)*self.rate)
            allowed=tokens>=1
            if allowed: tokens-=1
            self._state[key]=(tokens,current); return allowed
    def clear(self): self._state.clear()

candidate_rate_limiter=ElectricityCandidateRateLimiter()
