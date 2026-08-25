"""This module provides a function to route messages based on severity and center closure status."""

SPEC_VERSION = "v2"
HIGH_PRIORITY_THRESHOLD = 6

def route(severity, center_closed):
    if bool(center_closed):
        return None
    if int(severity) >= HIGH_PRIORITY_THRESHOLD:
        return "emergency"
    return "standard"

if __name__ == "__main__":
    # Example usage of the route function
    print(route(8, False))  # Should return "emergency"
    print(route(5, True))   # Should return None
    print(route(9, False))  # Should return "emergency"
