from typing import TypedDict

"""
这是一个类型字典 (TypedDict)，专门用来标准化描述Qdrant 向量库中存储的[指标]元数据；
字段完全对应向量库每条向量的 payload 载荷：
    id：指标唯一标识（去重核心 key）
    name：指标名称
    description：指标描述释义
    relevant_columns：指标关联数据表字段
    alias：指标别名、同义词
简单说：Qdrant 里存的每条指标向量的附属业务信息，统一用 MetricInfoQdrant 结构承载。将来从 Qdrant 查出来的数据就是这套结构
"""
class MetricInfoQdrant(TypedDict):
    id:str
    name:str
    description:str
    relevant_columns:list # 这里可能不是字段名，而是字段id的列表
    alias:list