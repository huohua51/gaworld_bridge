"""
This module provides a function to calculate the remaining budget after a certain amount has been spent.
"""

SPEC_VERSION = "v2"
APPLIED_PATCH_IDS = ["patch-01"]

BUDGET_THRESHOLD = 80

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
    print(remaining(20))  # Output should be 60
