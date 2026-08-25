"""
Calculate the minimum return amount based on principal and minimum rate.
"""

def min_return(principal, min_rate):
    if min_rate < 0:
        raise ValueError("Minimum rate must be non-negative.")
    return int(principal * min_rate)

if __name__ == "__main__":
    principal = float(input("Enter the principal amount: "))
    min_rate = float(input("Enter the minimum rate: "))
    print("Minimum return amount:", min_return(principal, min_rate))
