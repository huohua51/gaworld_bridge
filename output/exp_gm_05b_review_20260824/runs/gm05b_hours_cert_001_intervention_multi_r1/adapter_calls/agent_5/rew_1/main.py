"""
Check if an individual can work based on certification and hours worked.
"""

SPEC_VERSION = "v2"
MAX_HOURS = 35

def can_work(certified, hours):
    return bool(certified) and int(hours) <= MAX_HOURS

if __name__ == "__main__":
    # Example usage:
    print(can_work(certified=True, hours=30))  # Should return True
    print(can_work(certified=False, hours=30)) # Should return False
    print(can_work(certified=True, hours=45))  # Should return False
