"""Check if a person is eligible based on age and income.

This module defines a function to determine if a person meets certain criteria
based on their age and income. The function is `eligible(age, income)` which
returns True if the age is 18 or older and the income is 50,000 or less.
"""

SPEC_VERSION = "v2"
MIN_AGE = 18
INCOME_CAP = 45000

def eligible(age, income):
    return int(age) >= MIN_AGE and int(income) <= INCOME_CAP

if __name__ == "__main__":
    # Example usage of the eligible function
    print(eligible(25, 40000))  # Should return True
    print(eligible(17, 50000))  # Should return False
