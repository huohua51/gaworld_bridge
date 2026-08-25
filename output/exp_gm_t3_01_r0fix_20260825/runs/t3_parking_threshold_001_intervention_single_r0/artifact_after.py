```python
required_value = 90
PARKING_FREE_MINUTES = required_value
SPEC_VERSION = "v1"

def fee_required(minutes):
    return minutes >= PARKING_FREE_MINUTES
```
