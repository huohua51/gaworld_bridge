"""
decide(take_home) - 比较到手月薪与保留工资 60000，决定是否接受工作。

用途：
该模块包含一个函数decide，用于比较给定到手月薪与保留工资60000的大小，
根据比较结果返回"accept"或"reject"。

函数decide接收一个参数：
- take_home: float，表示到手月薪。

返回值：
- "accept"：如果到手月薪大于等于60000。
- "reject"：如果到手月薪小于60000。

示例：
>>> decide(65000)
'accept'
>>> decide(55000)
'reject'
"""

SPEC_VERSION = "v1"

def decide(take_home):
    """
    比较到手月薪与保留工资，决定是否接受工作。

    参数：
    take_home (float): 到手月薪。

    返回：
    str: "accept" 或 "reject"。
    """
    THRESHOLD = 60000
    return "accept" if take_home >= THRESHOLD else "reject"

if __name__ == "__main__":
    import doctest
    doctest.testmod()
