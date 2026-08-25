"""
Calculate the minimum return based on the principal amount.
"""

SPEC_VERSION = "v1"

MIN_RETURN_THRESHOLD = 0.3

def min_return(principal):
    """
    Calculate the minimum return for an investment.

    :param principal: The principal amount of the investment.
    :return: The minimum return as an integer.
    """
    return int(principal * MIN_RETURN_THRESHOLD)

if __name__ == "__main__":
    # Example usage
    principal_input = float(input("Enter the principal amount: "))
    print("Minimum return:", min_return(principal_input))
