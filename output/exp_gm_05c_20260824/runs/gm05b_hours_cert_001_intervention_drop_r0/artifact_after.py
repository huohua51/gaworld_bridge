"""
Check if an employee can work based on certification and hours worked.
"""

# Constants
SPEC_VERSION = "1.0"
MAX_HOURS = 40

def can_work(certified, hours):
    """
    Determine if an employee can work based on certification and hours worked.
    
    :param certified: bool - True if the employee is certified, False otherwise.
    :param hours: int - The number of hours the employee has worked this week.
    :return: bool - True if the employee can work, False otherwise.
    """
    return certified and hours <= MAX_HOURS

if __name__ == "__main__":
    # Example usage
    print(can_work(certified=True, hours=39))  # Should print True
    print(can_work(certified=False, hours=39)) # Should print False
    print(can_work(certified=True, hours=41))  # Should print False
