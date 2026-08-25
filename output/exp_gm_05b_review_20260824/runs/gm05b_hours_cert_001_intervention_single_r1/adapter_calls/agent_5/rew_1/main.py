"""Check if an employee can work based on certification and hours worked.

This module defines a function to determine if an employee is eligible to work
for the week based on their certification status and the number of hours they
have worked. The function checks if the employee is certified and if the number
of hours worked is within the allowed maximum.

Usage:
    from can_work_module import can_work

    certified = True
    hours = 30
    can_work_employee = can_work(certified, hours)
    print(can_work_employee)  # Output: True
"""

SPEC_VERSION = "v2"
MAX_HOURS = 35

def can_work(certified, hours):
    return bool(certified) and int(hours) <= MAX_HOURS

if __name__ == "__main__":
    # Example usage of the can_work function
    certified = True
    hours = 30
    print(can_work(certified, hours))  # Output: True
