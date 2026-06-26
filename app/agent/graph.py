import asyncio

from langgraph.constants import START, END
from langgraph.graph import StateGraph

from app.agent.context import DataAgentContext
from app.agent.nodes.add_extra_context import add_extra_context
from app.agent.nodes.correct_sql import correct_sql
from app.agent.nodes.execute_sql import execute_sql
from app.agent.nodes.extract_keywords import extract_keywords
from app.agent.nodes.filter_metric import filter_metric
from app.agent.nodes.filter_table import filter_table
from app.agent.nodes.generate_sql import generate_sql
from app.agent.nodes.merge_retrieved_info import merge_retrieved_info
from app.agent.nodes.recall_column import recall_column
from app.agent.nodes.recall_metric import recall_metric
from app.agent.nodes.recall_value import recall_value
from app.agent.nodes.validate_sql import validate_sql

from app.agent.state import DataAgentState
from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.mysql.dw_mysql_repository import DwMysqlRepository
from app.repositories.es.values_es_repository import ValueEsRepository
from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_respository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

# 创建图
graph_builder = StateGraph(state_schema=DataAgentState, context_schema=DataAgentContext)

# 添加节点
graph_builder.add_node("extract_keywords", extract_keywords)
graph_builder.add_node("recall_column", recall_column)
graph_builder.add_node("recall_metric", recall_metric)
graph_builder.add_node("recall_value", recall_value)
graph_builder.add_node("merge_retrieved_info", merge_retrieved_info)
graph_builder.add_node("filter_metric", filter_metric)
graph_builder.add_node("filter_table", filter_table)
graph_builder.add_node("add_extra_context", add_extra_context)
graph_builder.add_node("generate_sql", generate_sql)
graph_builder.add_node("validate_sql", validate_sql)
graph_builder.add_node("correct_sql", correct_sql)
graph_builder.add_node("execute_sql", execute_sql)

# 设置边
graph_builder.add_edge(START, "extract_keywords")
graph_builder.add_edge("extract_keywords", "recall_column")
graph_builder.add_edge("extract_keywords", "recall_metric")
graph_builder.add_edge("extract_keywords", "recall_value")
graph_builder.add_edge("recall_column", "merge_retrieved_info")
graph_builder.add_edge("recall_value", "merge_retrieved_info")
graph_builder.add_edge("recall_metric", "merge_retrieved_info")
graph_builder.add_edge("merge_retrieved_info", "filter_metric")
graph_builder.add_edge("merge_retrieved_info", "filter_table")
graph_builder.add_edge("filter_metric", "add_extra_context")
graph_builder.add_edge("filter_table", "add_extra_context")
graph_builder.add_edge("add_extra_context", "generate_sql")
graph_builder.add_edge("generate_sql", "validate_sql")

# 设置条件边
graph_builder.add_conditional_edges("validate_sql",
                                    lambda state: "execute_sql" if state["error"] is None else "correct_sql",
                                    {"execute_sql":"execute_sql","correct_sql":"correct_sql"})

graph_builder.add_edge("correct_sql", "execute_sql")
graph_builder.add_edge("execute_sql", END)


# 编译图
graph = graph_builder.compile()

# 打印图的流程显示
# print(graph.get_graph().draw_mermaid())

if __name__ == '__main__':

    """
    整体极简串一遍这段代码在干嘛
    1. 先初始化向量库、ES、MySQL、向量模型 4 个客户端管理器；
    2. 创建 MySQL 会话，分别实例化向量模型、ES/Qdrant/MySQL 数据库操作仓储；
    3. 把所有模型、数据库仓储实例打包进 DataAgentContext 上下文（全局工具包）；
    4. 把用户查询装进 DataAgentState 状态，连同上下文一起丢给 LangGraph 智能体图运行；
    5. 图里每个节点（关键词提取、SQL 校验、执行 SQL 等）都能直接从 context 拿到数据库 / 向量工具，不用重复创建连接。
    """

    async def test():
        # 创建状态信息
        state = DataAgentState(query="统计华北地区的销售总额")
        # 创建依赖对象
        # 初始化客户端对象
        embedding_client_manager.init()
        qdrant_client_manager.init()
        es_client_manager.init()
        meta_mysql_client_manager.init()
        dw_mysql_client_manager.init()

        # 获取session必须有, 构建对象
        # session_factory() 是 mysql 会话工厂，执行后会生成一个数据库会话（数据库连接会话）,
        async with meta_mysql_client_manager.session_factory() as meta_session,dw_mysql_client_manager.session_factory() as dw_session:
            # 创建repository
            #  embeddings：直接取现成实例，不需要再包一层类
            embeddings = embedding_client_manager.embeddings
            # qdrant、es仓储：只需要传入底层client客户端
            column_qdrant_repository = ColumnQdrantRepository(qdrant_client_manager.client)
            metric_qdrant_repository = MetricQdrantRepository(qdrant_client_manager.client)
            value_es_repository = ValueEsRepository(es_client_manager.client)

            # mysql仓储特殊：MySQL 仓储依赖数据库会话session（事务、单次会话隔离），不能直接用裸 client
            # 把数据库会话传给仓储类，用来执行 SQL 读写。
            meta_mysql_repository=MetaMysqlRepository(meta_session)
            # 补充repository创建
            dw_mysql_repository=DwMysqlRepository(dw_session)

            # 创建上下文信息
            context = DataAgentContext(
                # DataAgentContext 定义的 key 名称 = 上面代码提前创建好的向量化模型实例变量
                embeddings=embeddings,
                column_qdrant_repository=column_qdrant_repository,
                metric_qdrant_repository=metric_qdrant_repository,
                value_es_repository=value_es_repository,
                meta_mysql_repository=meta_mysql_repository,
                dw_mysql_repository=dw_mysql_repository
            )
            async  for chunk in graph.astream(input=state, context=context, stream_mode="custom"):
                print(chunk)

        # 释放资源
        """
        原因：embedding_client_manager 是调用第三方 API（HuggingFace 接口），没有长连接本地资源，
        不存在数据库 / 向量库 TCP 连接需要手动关闭；
        而 qdrant、es、mysql 都是本地 / 远程长连接客户端，占用网络连接池，必须手动close()释放连接，
        """
        await qdrant_client_manager.close()
        await es_client_manager.close()
        await meta_mysql_client_manager.close()
        await dw_mysql_client_manager.close()
    asyncio.run(test())
