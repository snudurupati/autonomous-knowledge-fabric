from datetime import datetime, timezone
from typing import List, Dict, Any

# Risk Score Weights (Sprint 15)
SIGNAL_WEIGHTS = {
    "TAKEOVER_BID": 40,
    "EXECUTIVE_DEPARTURE": 30,
    "DELISTING_RISK": 25,
    "EARNINGS_MISS": 20,
    "CRITICAL_SUPPORT": 15,
    "CONTRACT_RENEWAL_AT_RISK": 10,
}

def calculate_risk_score(signals: List[Dict[str, Any]]) -> int:
    """
    Calculates a risk score clamped to [0, 100] based on weighted signals.
    Each signal dict should have 'name' and optionally 'timestamp' (ISO format).
    
    Recency Decay:
    - 0-7 days: 100% weight
    - 8-30 days: linear decay to 50% weight
    - 31-90 days: linear decay to 20% weight
    - >90 days: 20% floor
    """
    if not signals:
        return 0
    
    total_score = 0.0
    now = datetime.now(timezone.utc)
    
    # Track unique signals to avoid double-counting the same type if it repeats
    # (Though in our graph, HAS_SIGNAL is usually merged per signal type)
    processed_signals = set()

    for signal in signals:
        name = signal.get("name")
        if not name or name in processed_signals:
            continue
            
        weight = SIGNAL_WEIGHTS.get(name, 5)  # Default weight for unknown signals
        
        ts_str = signal.get("timestamp")
        decay = 1.0
        
        if ts_str:
            try:
                # Handle both 'Z' and '+00:00' offsets
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                age_days = (now - ts).total_seconds() / (24 * 3600)
                
                if age_days <= 7:
                    decay = 1.0
                elif age_days <= 30:
                    # Linear decay from 1.0 to 0.5
                    decay = 1.0 - (age_days - 7) * (0.5 / 23)
                elif age_days <= 90:
                    # Linear decay from 0.5 to 0.2
                    decay = 0.5 - (age_days - 30) * (0.3 / 60)
                else:
                    decay = 0.2
            except ValueError:
                decay = 1.0
        
        total_score += weight * decay
        processed_signals.add(name)
        
    return min(100, max(0, int(total_score)))

def get_risk_level(score: int) -> str:
    """Return a human-readable risk level based on the score."""
    if score >= 70:
        return "CRITICAL"
    elif score >= 40:
        return "HIGH"
    elif score >= 20:
        return "ELEVATED"
    elif score > 0:
        return "STABLE"
    else:
        return "LOW"
