"""
This module provides a function to calculate the remaining budget after a certain amount has been spent.
"""

SPEC_VERSION = "v1"
APPLIED_PATCH_IDS = ["patch-01"]

BUDGET_THRESHOLD = 100

def remaining(spent):
    """
    Calculate the remaining budget after a certain amount has been spent.

    Parameters:
    spent (int): The amount spent from the budget.

    Returns:
    int: The remaining budget, ensuring it is not negative.
    """
    return max(0, BUDGET_THRESHOLD - spent)

if __name__ == "__main__":
    # Example usage of the remaining function
    spent_amount = 50
    print(remaining(spent_amount))
