from typing import TypedDict

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.repositories.es.values_es_repository import ValueEsRepository
from app.repositories.mysql.dw_mysql_repository import DwMysqlRepository
from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_respository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

"""
DataAgentContext 静态类型约束规则（给IDE/类型检查看）不生成任何实例，不存数据，没有内存对象
`DataAgentContext`只是规则模板，告诉 IDE 以后有个字典，必须包含embeddings、value_es_repository这些 key，每个 key 对应固定类型；
    它只做类型标注，不存真实数据，自然看不到{}。
字段含义对应
embeddings: HuggingFaceEndpointEmbeddings：规定字典里"embeddings"这个键，只能存向量化模型对象；
value_es_repository: ValueEsRepository：规定字典里"value_es_repository"键，只能存 ES 数据库操作仓库实例。

LangGraph 是多节点流水线（多个工具 / 函数依次执行），每个业务节点（检索 ES、查 Qdrant、查 MySQL、文本向量化）都需要共用同一批资源实例：
 - 向量化模型 embeddings
 - 3 个向量库 / ES 仓库、1 个元数据 MySQL 仓库
如果每个节点自己新建连接 / 模型：
 -1重复初始化，浪费内存、建立大量数据库连接；
 -2配置不统一（有的节点用 A 向量模型，有的用 B）；
 -3传参繁琐，每个函数要堆五六个入参。
于是用 DataAgentContext 这个统一字典容器，一次性装好所有全局依赖，整条链路所有节点只传这一个上下文对象即可


下面逐个拆解每个字段存在的必要性、什么时候会用到：
1. embeddings: HuggingFaceEndpointEmbeddings 向量模型实例
    作用：文本转向量的唯一工具
    业务中多处需要向量化：
    用户问题 → 转向量，去 Qdrant 做向量相似度检索（查指标、查字段）；
    ES 里文本值检索、语义匹配也需要向量；
    检索到的素材做语义打分、排序也要向量化。
2. column_qdrant_repository: ColumnQdrantRepository 字段向量库仓库
    存储业务数据表字段（列） 的向量元数据：字段名称、字段描述、业务含义、字段向量。
    使用场景
        用户提问涉及数据表字段时：流程节点会拿用户问题向量，通过这个 repository 去 Qdrant 检索相似字段，匹配候选数据表列。
    放入上下文是因为，Qdrant 有连接池、客户端实例，全局单例复用；所有字段检索节点统一调用该仓库，不用重复创建 Qdrant 连接。
3. metric_qdrant_repository: MetricQdrantRepository 指标向量库仓库
    存储业务指标（聚合指标、统计口径）向量数据：GMV、销售额、复购率、客单价等指标名称、口径描述、向量。
    使用场景：
        用户查询统计指标类问题例：“上个月总 GMV 是多少？” 节点通过该仓库检索相似指标，匹配对应统计口径。
    和 column_qdrant 分开的原因
    字段、指标是两类完全不同的向量数据，存在 Qdrant 不同 Collection，拆分成两个 Repository 做隔离，逻辑清晰，所以上下文需要两个独立实例。
4. value_es_repository: ValueEsRepository ES 文本值仓库
    存储业务表真实值、维度文本数据（地区、渠道、订单状态等文本明细），支持全文检索 + 语义向量检索。
    使用场景
        用户带筛选条件查询：例：“北京地区 2025 年销售额”
        节点需要从 ES 匹配「北京」这类维度枚举值，校验过滤条件合法性、补充筛选参数。
    放入上下文原因：ES 客户端连接全局复用，所有文本维度检索节点统一调用。
5. meta_mysql_repository: MetaMysqlRepository MySQL 元数据仓库
    存储底层基础结构化元数据：数据表基础信息、字段类型、指标 SQL 口径、表关联关系、权限信息等结构化配置（不适合存向量，适合 MySQL）。
    使用场景
        向量检索出候选字段 / 指标后，去 MySQL 拿真实 SQL、表关联关系；
        校验数据表访问权限、查询字段数据类型；
        拼接最终可执行查询 SQL。
    必要性: 向量库只存语义向量，拿不到完整 SQL、表结构、权限等结构化配置，必须依赖 MySQL 元数据仓库，是生成最终查询语句的核心依赖。

"""
class DataAgentContext(TypedDict):
    embeddings: HuggingFaceEndpointEmbeddings
    column_qdrant_repository: ColumnQdrantRepository
    metric_qdrant_repository: MetricQdrantRepository
    value_es_repository: ValueEsRepository
    meta_mysql_repository: MetaMysqlRepository
    dw_mysql_repository: DwMysqlRepository