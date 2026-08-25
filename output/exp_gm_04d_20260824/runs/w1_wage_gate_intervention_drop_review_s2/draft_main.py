"""
decide(take_home) - 比较到手月薪与保留工资 60000，决定是否接受工作。

用途：
该模块包含一个函数decide，用于比较给定到手月薪与保留工资60000的大小，
并根据比较结果返回接受或拒绝工作。

函数decide接收一个参数take_home，表示到手月薪，并返回字符串'accept'或'reject'。
"""

SPEC_VERSION = "v1"

def decide(take_home):
    """
    决定是否接受工作。

    参数:
    take_home (int): 到手月薪。

    返回:
    str: 'accept' 如果到手月薪大于等于60000，否则返回'reject'。
    """
    return 'accept' if take_home >= 60000 else 'reject'

if __name__ == "__main__":
    # 示例使用
    take_home_salary = 65000
    print(decide(take_home_salary))
