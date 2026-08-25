MIN_BATTERY = 20
SPEC_VERSION = "v1"

def battery_ok(pct):
    return pct >= MIN_BATTERY
