"""Calculate the remaining budget after a certain amount has been spent.

This module provides a function to calculate the remaining budget after a
specified amount has been spent. The total budget is fixed at 100, and the
function does not accept the budget as a parameter.

Usage:
    remaining_spent = remaining(spent)
    print(remaining_spent)
"""

SPEC_VERSION = "v2"
BUDGET = 80

def remaining(spent):
    return max(0, BUDGET - spent)

if __name__ == "__main__":
    # Example usage:
    spent_amount = 50
    print(remaining(spent_amount))
