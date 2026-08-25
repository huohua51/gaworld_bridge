SPEC_VERSION = "v1"
HIGH_PRIORITY_THRESHOLD = 7


def route(severity, center_closed):
    if bool(center_closed):
        return None
    if int(severity) >= HIGH_PRIORITY_THRESHOLD:
        return "emergency"
    return "standard"
