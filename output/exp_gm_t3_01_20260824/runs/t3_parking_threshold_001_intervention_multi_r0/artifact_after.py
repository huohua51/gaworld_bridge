```python
PARKING_FREE_MINUTES = 120
SPEC_VERSION = "v2"

def fee_required(minutes):
    return minutes >= PARKING_FREE_MINUTES
```
