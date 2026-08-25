SPEC_VERSION = "v1"
ALERT_C = 36

def should_alert(temp):
    return temp >= ALERT_C
