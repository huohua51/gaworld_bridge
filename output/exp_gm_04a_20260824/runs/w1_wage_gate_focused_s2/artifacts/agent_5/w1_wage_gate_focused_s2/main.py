"""
This script defines a function to decide whether to accept a job offer based on the reservation wage and take-home pay.
"""

def decide(reservation_wage, take_home):
    """
    Decide whether to accept a job offer.

    Parameters:
    reservation_wage (float): The wage at which the job is considered acceptable.
    take_home (float): The actual take-home pay from the job.

    Returns:
    str: 'accept' if the take-home pay is greater than or equal to the reservation wage, otherwise 'reject'.
    """
    return 'accept' if take_home >= reservation_wage else 'reject'

if __name__ == "__main__":
    # Example usage:
    reservation_wage = float(input("Enter the reservation wage: "))
    take_home = float(input("Enter the take-home pay: "))
    print(decide(reservation_wage, take_home))
