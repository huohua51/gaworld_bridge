"""
This module provides a function to decide whether to accept a job offer based on the take-home salary.
"""

SPEC_VERSION = "v2"

def decide(take_home):
    """
    Decide whether to accept a job offer based on the take-home salary.

    Parameters:
    take_home (float): The take-home salary of the job offer.

    Returns:
    str: 'accept' if the take-home salary is greater than or equal to the reservation wage, otherwise 'reject'.
    """
    reservation_wage = 70000
    if take_home >= reservation_wage:
        return 'accept'
    else:
        return 'reject'

if __name__ == "__main__":
    # Example usage:
    take_home_salary = float(input("Enter the take-home salary: "))
    print(decide(take_home_salary))
