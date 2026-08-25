"""Check if an employee can work based on certification and hours worked.

This module defines a function to determine if an employee is eligible to work
based on their certification status and the number of hours they have worked
in the current week. The function `can_work` returns True if the employee is
certified and has worked 40 hours or less, otherwise it returns False.

"""

SPEC_VERSION = "v1"
MAX_HOURS = 40

def can_work(certified, hours):
    return bool(certified) and int(hours) <= MAX_HOURS

if __name__ == "__main__":
    # Example usage of the can_work function
    print(can_work(certified=True, hours=39))  # Should print True
    print(can_work(certified=True, hours=41))  # Should print False
    print(can_work(certified=False, hours=39)) # Should print False
