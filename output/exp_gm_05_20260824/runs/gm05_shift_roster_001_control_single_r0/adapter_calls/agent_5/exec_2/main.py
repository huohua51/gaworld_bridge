"""Roster Management Module

This module provides functionality to validate and assign shifts to workers
based on given assignments and shift requirements.
"""

# Module Constants
NIGHT_SHIFT_MINIMUM = 1
SPEC_VERSION = "v1"

def valid_roster(assignments, workers, shifts):
    """
    Validates the roster to ensure that each shift is covered and the
    conditions for workers are met.
    
    :param assignments: List of tuples (worker_id, shift_id)
    :param workers: Dictionary with worker_id as key and a tuple (name, is_medic, certification) as value
    :param shifts: Dictionary with shift_id as key and a tuple (start_time, end_time, kind) as value
    :return: Boolean indicating if the roster is valid
    """
    for worker_id, shift_id in assignments:
        worker = workers.get(worker_id)
        shift = shifts.get(shift_id)
        if not worker or not shift:
            return False
        
        if worker[1] and not worker[2]:
            return False
        
        if (shift[2] == 'night' and worker_id not in assignments) or \
           (shift[2] == 'day' and worker_id in assignments):
            return False
        
        if (shift[1] - shift[0]) > 12:
            return False
        
        for other_shift_id in assignments:
            if other_shift_id[0] == worker_id and other_shift_id[1] != shift_id:
                return False
    
    return True

def assign(workers, shifts):
    """
    Assigns shifts to workers based on the given workers and shifts.
    
    :param workers: Dictionary with worker_id as key and a tuple (name, is_medic, certification) as value
    :param shifts: Dictionary with shift_id as key and a tuple (start_time, end_time, kind) as value
    :return: List of tuples (worker_id, shift_id) representing the assignments
    """
    assignments = []
    for shift_id, shift in shifts.items():
        if shift[2] == 'night' and len(assignments) < NIGHT_SHIFT_MINIMUM:
            continue
        for worker_id, worker in workers.items():
            if worker[1] and not worker[2]:
                continue
            if (shift[1] - shift[0]) > 12:
                continue
            if worker_id not in [assignment[0] for assignment in assignments]:
                assignments.append((worker_id, shift_id))
                break
    return assignments

if __name__ == "__main__":
    # Example usage
    workers = {
        1: ("Alice", False, True),
        2: ("Bob", True, True),
        3: ("Charlie", False, False)
    }
    shifts = {
        1: (9, 17, "day"),
        2: (17, 1, "night"),
        3: (1, 9, "night")
    }
    assignments = assign(workers, shifts)
    print("Valid Roster:", valid_roster(assignments, workers, shifts))
    print("Assignments:", assignments)
