"""
This script calculates whether to accept or reject a job offer based on the retained salary and the salary after deductions.
"""

def calculate_decision(retained_salary, salary_after_deductions):
    if retained_salary <= salary_after_deductions:
        return "accept"
    else:
        return "reject"

if __name__ == "__main__":
    retained_salary = int(input("Enter the retained salary: "))
    salary_after_deductions = int(input("Enter the salary after deductions: "))
    decision = calculate_decision(retained_salary, salary_after_deductions)
    print(decision)
