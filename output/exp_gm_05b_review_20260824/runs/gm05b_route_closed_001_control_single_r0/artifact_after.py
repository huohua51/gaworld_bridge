"""This module provides a function to route messages based on severity and center closure status."""

SPEC_VERSION = "v1"
HIGH_PRIORITY_THRESHOLD = 7

def route(severity, center_closed):
    if bool(center_closed):
        return None
    if int(severity) >= HIGH_PRIORITY_THRESHOLD:
        return "emergency"
    return "standard"

if __name__ == "__main__":
    # Example usage of the route function
    print(route(8, False))  # Should return "emergency"
    print(route(5, False))  # Should return "standard"
    print(route(8, True))   # Should return None
