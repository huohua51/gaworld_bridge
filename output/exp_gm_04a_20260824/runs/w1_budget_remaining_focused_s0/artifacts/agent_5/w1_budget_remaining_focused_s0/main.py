"""
This script defines a function to calculate the remaining budget after some amount has been spent.
"""

def remaining(budget, spent):
    """
    Calculate the remaining budget after spending a certain amount.

    Parameters:
    budget (float): The total budget available.
    spent (float): The amount already spent.

    Returns:
    float: The remaining budget, or 0 if spent exceeds budget.
    """
    return max(0, budget - spent)

if __name__ == "__main__":
    budget = float(input("Enter the total budget: "))
    spent = float(input("Enter the amount spent: "))
    print("Remaining budget:", remaining(budget, spent))
