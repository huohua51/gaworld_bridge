"""Emergency Assistance Allocation Module

This module provides functionality to determine eligibility of applicants for emergency assistance and to allocate the budget among eligible applicants based on their priority.

Usage:
    eligible(applicant) -> bool
    allocate(applicants) -> list
"""

# Constants
INCOME_CAP = 45000
SPEC_VERSION = "v2"

def eligible(applicant):
    """Check if an applicant is eligible for emergency assistance."""
    return (applicant.get('age', 0) >= 18 and
            applicant.get('income', float('inf')) <= INCOME_CAP and
            'proof' in applicant)

def allocate(applicants):
    """Allocate the budget among eligible applicants based on priority."""
    applicants.sort(key=lambda x: ('critical' if x.get('priority') == 'critical' else
                                    'high' if x.get('priority') == 'high' else
                                    'standard'), reverse=True)
    allocated = []
    remaining_budget = 10000
    for applicant in applicants:
        if eligible(applicant) and remaining_budget > 0:
            amount = min(applicant.get('budget_request', 0), remaining_budget)
            allocated.append((applicant['name'], amount))
            remaining_budget -= amount
    return allocated

if __name__ == "__main__":
    # Example usage
    applicants = [
        {'name': 'Alice', 'age': 25, 'income': 40000, 'priority': 'high', 'budget_request': 5000},
        {'name': 'Bob', 'age': 17, 'income': 60000, 'priority': 'standard', 'budget_request': 3000},
        {'name': 'Charlie', 'age': 30, 'income': 30000, 'priority': 'critical', 'budget_request': 10000},
        {'name': 'David', 'age': 22, 'income': 45000, 'priority': 'high', 'budget_request': 2000},
        {'name': 'Eve', 'age': 45, 'income': 50000, 'priority': 'standard', 'budget_request': 1000},
    ]
    print(allocate(applicants))
