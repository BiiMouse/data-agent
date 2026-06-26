from typing import TypedDict

"""
专门用来标准化描述Qdrant 向量库中存储的[字段]元数据,
这是向量库持久化载体：存在 Qdrant 的 payload 里，是原始完整业务元数据，用于向量检索召回
"""
class ColumnInfoQdrant(TypedDict):
    id: str
    name: str
    type: str
    role: str
    examples: list
    description: str
    alias: list
    table_id: str