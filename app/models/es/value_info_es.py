from typing import TypedDict

# 存储这些字段哪些值？存储结构是这样的，这是保证LLM工作的基础
class ValueInfoEs(TypedDict):
    id: str
    value: str
    type: str
    column_id: str
    column_name: str
    table_id: str
    table_name: str