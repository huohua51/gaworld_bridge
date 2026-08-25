"""Check if a person is eligible based on age and income.

This module defines a function to determine if a person meets the eligibility criteria
based on their age and income. The criteria are that the age must be 18 or older and
the income must not exceed 45,000.

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
