from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
import asyncio

from app.agent.llm import llm
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState

from app.core.log import logger
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.prompt.prompt_loader import loader_prompt


async def recall_column(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "召回字段信息"})
    try:
        # 获取向量转换对象
        embeddings = runtime.context["embeddings"]
        # 获取持久层查询对象
        column_qdrant_repository = runtime.context["column_qdrant_repository"]
        # 获取问题
        query = state["query"]
        # 获取关键字列表
        keywords = state["keywords"]

        # 1.扩展关键字--llm
        tml = await loader_prompt("extend_keywords_for_column_recall")
        #1.1定义提示词模板
        prompt = PromptTemplate(template=tml, input_variables=["query"])
        #1.2构造结果转化器 强制LLM输出纯标准JSON，自动把JSON 文本解析成 Python list/dict；
        # 后续 chain.ainvoke() 拿到的直接是关键词列表
        output_parser=JsonOutputParser()
        #1.3定义执行连接
        chain = prompt | llm | output_parser
        #1.4执行lian
        result=await chain.ainvoke({"query": query})
        #1.5合并关键字
        keywords = set(keywords+result)
        logger.info(f"字段扩展后关键字列表：{keywords}")

        # 2.字段召回--qdrant
        #定义字典结构去除召回的重复字段信息
        retrieved_column_map: dict[str, ColumnInfoQdrant]

        # 这段代码正在从 Qdrant 做向量召回,ColumnInfoQdrant 是专门适配 Qdrant 向量库存储结构的数据模型
        # 这段不是精确匹配，是向量相似度模糊召回，先把文字转数字向量，Qdrant 内部计算向量余弦相似度，返回「语义相近」的数据，属于模糊语义召回。
        """
        截图里 4 个类分工完全分开：
        ColumnInfoMySQL：MySQL 数据库表实体，存原始业务字段全量信息（结构化表字段）
        ColumnMetricMySQL：MySQL 里字段关联的指标数据
        ColumnInfoQdrant：存入 Qdrant 向量库时，精简后的字段向量载体（只存向量检索需要的字段 id、名称、描述等轻量化信息）
        ColumnQdrantRepository：操作 Qdrant 的仓库类，读取 / 写入时只产出、接收ColumnInfoQdrant对象
        """

        # 遍历关键字
        for keyword in keywords:
            #转换成向量
            embedding = await embeddings.aembed_query(keyword)
            # 用关键字向量到字段向量仓中查询
            payloads:list[ColumnInfoQdrant] = await column_qdrant_repository.search(embedding)
            # 遍历召回的结果，目标是去重
            for payload in payloads:
                # 获取召回字段信息的id
                column_id = payload["id"]
                # 判断当前字段是否已经被召回
                if column_id not in retrieved_column_map:
                    retrieved_column_map[column_id] = payload
        # 获得召回字段列表
        retrieved_columns = list(retrieved_column_map.values())

        logger.info(f"召回字段信息成功，{list(retrieved_column_map.keys())}")

        return {"retrieved_columns": retrieved_columns}
    except Exception as e:
        logger.error(f"召回字段信息异常，{str(e)}")
        raise