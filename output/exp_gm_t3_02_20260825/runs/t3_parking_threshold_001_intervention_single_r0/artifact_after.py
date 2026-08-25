PARKING_FREE_MINUTES = 90
SPEC_VERSION = "v1"

def fee_required(minutes):
    return minutes >= PARKING_FREE_MINUTES
