"""
Calculate the remaining budget after a certain amount has been spent.

This module provides a function to calculate the remaining budget based on the total budget and the amount spent. The total budget is fixed at 100, and the function does not accept the total budget as a parameter. The function checks against a fixed threshold of 80 for the total budget.

Usage:
    remaining(spent) -> int
"""

SPEC_VERSION = "v2"

THRESHOLD = 80

def remaining(spent):
    """
    Calculate the remaining budget after a certain amount has been spent.

    Parameters:
    spent (int): The amount of money that has been spent.

    Returns:
    int: The remaining budget after the spent amount has been deducted from the total budget.
    """
    return max(0, THRESHOLD - spent)

if __name__ == "__main__":
    # Example usage:
    print(remaining(50))  # Output: 30
    print(remaining(80))  # Output: 0
    print(remaining(100)) # Output: 0
