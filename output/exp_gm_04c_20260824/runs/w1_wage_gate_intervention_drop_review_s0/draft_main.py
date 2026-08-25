"""
decide(take_home) - 比较到手月薪与保留工资 60000，决定是否接受工作。

用途：
该模块包含一个函数decide，用于比较给定到手月薪与保留工资60000的大小，
并根据比较结果返回接受或拒绝工作。

函数decide接收一个参数take_home，表示到手月薪。
如果take_home大于等于60000，则返回'accept'；否则返回'reject'。

模块顶层定义了SPEC_VERSION常量，表示模块版本。
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
    if take_home >= 60000:
        return 'accept'
    else:
        return 'reject'

if __name__ == "__main__":
    # 示例使用decide函数
    take_home_salary = 65000
    print(decide(take_home_salary))
