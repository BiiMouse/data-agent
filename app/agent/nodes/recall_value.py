from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState
import asyncio

from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.prompt.prompt_loader import loader_prompt


async def recall_value(state:DataAgentState,runtime:Runtime[DataAgentContext]):

    writer = runtime.stream_writer
    writer({"stage": "召回字段取值"})
    try:
        # 前面指标 / 字段用 Qdrant 是向量相似度检索，必须把文本转向量才能向量匹配；
        # 当前字段取值存储在 ES，业务用的是全文关键词检索（倒排索引）：
        # ES 底层基于分词、关键词匹配，直接传原始文本给 ES 就能做文本模糊 / 全文匹配；不需要向量、不需要向量库
        # 因此无需加载 embeddings 向量化工具
        # embeddings = runtime.context["embeddings"]

        # 持久层查询对象（es客户端，全局链接)
        value_es_repository=runtime.context["value_es_repository"]
        # 获得问题
        query=state["query"]
        #获取关键词列表
        keywords=state["keywords"]

        ##扩展关键词
        #从文件加载扩展关键词的提示词文本字符串
        tml = await loader_prompt("extend_keywords_for_value_recall")

        # 将提示词文本字符串、入参变量封装成 LangChain 可执行的 PromptTemplate 提示模板对象
        # "query" 模板占位符的变量名，后续调用时要传入键为 query 的参数填充占位；
        # 后面 chain.ainvoke({"query": query})和这里 "query" 一一对应。
        prompt = PromptTemplate(template=tml, input_variables=["query"])

        # 强制LLM输出纯标准JSON，自动把JSON 文本解析成 Python list/dict；
        # 后续 chain.ainvoke() 拿到的直接是关键词列表
        output_parser = JsonOutputParser()

        #定义执行链
        chain=prompt|llm|output_parser
        #执行chain链
        result=await chain.ainvoke({"query":query})
        #合并关键词
        keywords = set(keywords+result)

        #定义字典结构接收召回结果
        retrieved_value_map: dict[str, ValueInfoEs] = {}
        #遍历关键词
        for keyword in keywords:
            #借用es持久化客户端，用关键词到es全文数据库查询匹配
            # 一次关键词检索会匹配多条字段取值数据，所以是列表；
            values:list[ValueInfoEs] = await value_es_repository.search(keyword)
            #遍历召回结果，去重
            if values:
                for value in values:
                    value_id=value["id"]
                    if value_id not in retrieved_value_map:
                        retrieved_value_map[value_id] = value
        #获得召回列表
        retrieved_values = list(retrieved_value_map.values())

        #打印信息
        logger.info(f"召回字段值成功，{list(retrieved_value_map.keys())}")

        #返回结果
        return {"retrieved_values": retrieved_values}

    except Exception as e:
        logger.error(f"召回字段值发生异常：{str(e)}")
        raise