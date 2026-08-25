"""
Calculate the minimum return rate for an investment.
"""

SPEC_VERSION = "v2"

MIN_RETURN_RATE = 0.5

def min_return(principal):
    """
    Calculate the minimum return for an investment.

    :param principal: The principal amount of the investment.
    :return: The minimum return as an integer.
    """
    return int(principal * MIN_RETURN_RATE)

if __name__ == "__main__":
    # Example usage
    principal = 1000
    print(min_return(principal))
