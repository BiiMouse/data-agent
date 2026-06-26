from typing import TypedDict

from app.models.es.value_info_es import ValueInfoEs
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant


"""
# 专门用来标准化描述Qdrant 向量库中存储的[字段]元数据
class ColumnInfoQdrant(TypedDict):
    id,name,type,role,examples,description,alias,table_id
"""
# 列信息封装实体
# 是智能体轻量流转状态，
# 生成 SQL、组装提示词用不到id,table_id, 流程流转不需要主键id 下游逻辑不需要表标识 table_id
# LLM 不方便解析列表，所以把多值 examples 拼接成字符串,。
# 用途：召回字段后，精简数据存入 graph 状态，给后续节点做 prompt 填充。
# 指标信息封装实体, examples/alias 是多段文本描述，LLM 直接读拼接字符串更友
class ColumnInfoState(TypedDict):
    name: str
    type: str
    role: str
    examples: str
    description: str
    alias: str

# 表信息封装实体
# 每条 ColumnInfoState 包含 name/type/ 描述 一整套完整字段信息，每条都是独立对象；
# LLM 需要区分「这张表里有哪些字段、每个字段各自是什么类型、什么含义」；
# 若把所有字段揉成一段大字符串，字段之间信息会混杂，LLM 分不清哪个描述对应哪个字段
class TableInfoState(TypedDict):
    name: str
    role: str
    description: str
    columns: list[ColumnInfoState]


# relevant_columns存储独立字段名，需逐条提取用于SQL拼接，用列表可清晰区分每个字段、避免字符串分割出错。
class MetricInfoState(TypedDict):
    name: str
    description: str
    relevant_columns: list[str]
    alias: str


class DataAgentState(TypedDict):
    query: str
    error: str
    keywords:list
    retrieved_columns: list[ColumnInfoQdrant]
    """
    class MetricInfoQdrant(TypedDict):
        id:str
        name:str
        description:str
        relevant_columns:list
        alias:list
    为什么召回结果要用这个类型？
        1.数据源匹配：从 Qdrant 查出来的数据就是这套结构
        2.State 状态统一约束：全局状态规定存储指标列表为此类型
        3.语义区分：带 Qdrant 标识，区分其他指标实体
    这是向量检索层的原始指标数据，不是数据库 ORM 对象、不是返回给前端的脱敏对象，专门用于召回阶段内部流转。
    """
    retrieved_metrics: list[MetricInfoQdrant]
    retrieved_values: list[ValueInfoEs]
    table_infos: list[TableInfoState]
    metric_infos: list[MetricInfoState]
