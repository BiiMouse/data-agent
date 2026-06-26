from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
import asyncio

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
from app.core.log import logger
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant
from app.prompt.prompt_loader import loader_prompt


async def recall_metric(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "召回指标信息"})
    """
    关键词向量化 → Qdrant 搜索 → 返回 payload: dict（字段匹配 MetricInfoQdrant）
    通过 metric_id 字典去重，得到一批符合 MetricInfoQdrant 结构的字典
    转列表 list(retrieved_metric_map.values())，类型为 list[MetricInfoQdrant]
    返回写入 DataAgentState["retrieved_metrics"]，供后续节点读取使用
    """
    try:
        # 向量转换器对象
        embeddings = runtime.context["embeddings"]
        # 获得持久层查询对象
        metric_qdrant_repository=runtime.context["metric_qdrant_repository"]
        # 获取问题
        query = state["query"]
        #获取关键字列表
        keywords=state["keywords"]

        #扩展关键词
        tml = await loader_prompt("extend_keywords_for_metric_recall.prompt")
        #1.1定义提示词模板
        prompt = PromptTemplate(template=tml, input_variables=["query"])
        #1.2构造结果转化器 强制LLM输出纯标准JSON，自动把JSON 文本解析成 Python list/dict；
        # 后续 chain.ainvoke() 拿到的直接是关键词列表
        output_parser=JsonOutputParser()
        #1.3定义langchain执行链
        chain = prompt | llm | output_parser
        #1.4执行链
        result = await chain.ainvoke({"query": query})
        #1.5合并关键字
        keywords = set(keywords+result)
        logger.info(f"指标扩展后关键字列表keywords: {keywords}")

        #召回指标--qdrant
        # 定义字典结构去除召回的重复字段, 数据源匹配：从 Qdrant 查出来的数据就是MetricInfoQdrant结构
        retrieved_metric_map: dict[str, MetricInfoQdrant] = {}
        # 遍历关键字集合，按关键字逐个召回
        for keyword in keywords:
            # 关键字转换为向量
            embedding = await embeddings.aembed_query(keyword)
            # 然后到向量仓库里做相似度匹配-召回
            payloads:list[MetricInfoQdrant] = await metric_qdrant_repository.search(embedding)
            # 遍历召回结果
            for payload in payloads:
                # 获取召回指标信息的id
                metric_id = payload["id"]
                # 判断当前字段是否已经被召回
                if metric_id not in retrieved_metric_map:
                    retrieved_metric_map[metric_id]=payload

        # 获取召回指标列表
        retrieved_metrics = list(retrieved_metric_map.values())

        logger.info(f"指标召回学习成功，{list(retrieved_metric_map.keys())}")

        return {"retrieved_metrics": retrieved_metrics}
    except Exception as e:
        logger.error(f"指标召回信息异常，{str(e)}")
        raise