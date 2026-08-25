"""Check if an employee can work based on certification and hours worked.

This module provides a function to determine if an employee is eligible to work
based on their certification status and the number of hours they have worked in
a week. The function `can_work` checks if the employee is certified and has worked
a maximum of 40 hours in the week.

Usage:
    from can_work_module import can_work

    certified = True
    hours = 35
    can_work_result = can_work(certified, hours)
    print(can_work_result)  # Output: True
"""

SPEC_VERSION = "v1"
MAX_HOURS = 40

def can_work(certified, hours):
    return bool(certified) and int(hours) <= MAX_HOURS

if __name__ == "__main__":
    # Example usage of the can_work function
    certified = True
    hours = 35
    print(can_work(certified, hours))  # Output: True
