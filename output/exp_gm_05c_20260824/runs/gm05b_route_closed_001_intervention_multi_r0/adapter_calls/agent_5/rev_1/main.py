"""
This module provides a function to route messages based on severity and center closure status.
"""

SPEC_VERSION = "v2"

HIGH_PRIORITY_THRESHOLD = 6

def route(severity, center_closed):
    """
    Routes messages based on severity and center closure status.

    :param severity: int, the severity level of the message
    :param center_closed: bool, indicates if the center is closed
    :return: str, 'emergency' if severity is >= HIGH_PRIORITY_THRESHOLD and center is not closed, otherwise 'standard'
    """
    if center_closed:
        return None
    return 'emergency' if severity >= HIGH_PRIORITY_THRESHOLD else 'standard'

if __name__ == "__main__":
    # Example usage
    print(route(8, False))  # Should print 'emergency'
    print(route(5, False))  # Should print 'standard'
    print(route(8, True))   # Should print None
