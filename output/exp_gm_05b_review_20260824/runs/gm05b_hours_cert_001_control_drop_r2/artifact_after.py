"""Check if an employee can work based on certification and hours worked.

This module provides a function to determine if an employee is eligible to work
based on their certification status and the number of hours they have worked in
a week. The function `can_work` returns True if the employee is certified and has
worked 40 hours or less in the week, otherwise it returns False.

Usage:
    from can_work_module import can_work

    certified = True
    hours = 35
    can_work_employee = can_work(certified, hours)
    print(can_work_employee)  # Output: True
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
