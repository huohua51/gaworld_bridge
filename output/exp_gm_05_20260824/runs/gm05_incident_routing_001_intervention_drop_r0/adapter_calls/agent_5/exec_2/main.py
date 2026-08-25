"""
事件路由模块
用途：根据事件严重程度和截止时间，将事件路由到合适的处理中心。
"""

HIGH_PRIORITY_THRESHOLD = 7

SPEC_VERSION = "1.0"

def is_high_priority(incident):
    """
    判断事件是否为高优先级。
    :param incident: 事件字典，包含 'severity' 和 'deadline' 键。
    :return: 布尔值，表示事件是否为高优先级。
    """
    return incident['severity'] >= HIGH_PRIORITY_THRESHOLD

def route(incident, centers):
    """
    根据事件路由到合适的处理中心。
    :param incident: 事件字典，包含 'severity' 和 'deadline' 键。
    :param centers: 处理中心列表，每个中心是一个字典，包含 'name', 'capacity', 'closed', 'coverage' 键。
    :return: 路由到的处理中心名称。
    """
    for center in centers:
        if center['closed'] or center['capacity'] == 0 or not center['coverage'].get(incident['region']):
            continue
        if is_high_priority(incident) and center['capacity'] > 0:
            center['capacity'] -= 1
            return center['name']
        elif not is_high_priority(incident) and center['capacity'] > 0:
            center['capacity'] -= 1
            return center['name']
    return None

if __name__ == "__main__":
    # 示例事件和中心数据
    incident_example = {'severity': 8, 'deadline': '2023-04-01 14:00', 'region': 'North'}
    centers_example = [
        {'name': 'Center A', 'capacity': 2, 'closed': False, 'coverage': {'North': True}},
        {'name': 'Center B', 'capacity': 0, 'closed': False, 'coverage': {'North': True}},
        {'name': 'Center C', 'capacity': 1, 'closed': True, 'coverage': {'North': True}},
        {'name': 'Center D', 'capacity': 1, 'closed': False, 'coverage': {'South': True}}
    ]

    # 路由事件
    center_selected = route(incident_example, centers_example)
    print(f"Event routed to: {center_selected}")
