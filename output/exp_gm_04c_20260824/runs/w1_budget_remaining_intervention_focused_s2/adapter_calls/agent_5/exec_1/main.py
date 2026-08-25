"""
Calculate the remaining budget after a certain amount has been spent.

This module provides a function to calculate the remaining budget based on the total budget and the amount spent.
"""

SPEC_VERSION = "v2"

# Constants for the budget threshold
BUDGET_THRESHOLD = 80

def remaining(spent):
    """
    Calculate the remaining budget after a certain amount has been spent.

    Parameters:
    spent (int): The amount of money that has been spent.

    Returns:
    int: The remaining budget, ensuring it is not negative.
    """
    return max(0, BUDGET_THRESHOLD - spent)

if __name__ == "__main__":
    # Example usage of the remaining function
    spent_amount = 50
    print(remaining(spent_amount))
