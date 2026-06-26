import asyncio

import yaml
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, TableInfoState
from app.core.log import logger
from app.prompt.prompt_loader import loader_prompt


async def filter_table(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "过滤表信息"})

    try:
        # 获取用户问题
        query = state["query"]
        # 获取合并的表信息
        table_infos:list[TableInfoState] = state["table_infos"]
        # 加载提示词
        tml = await loader_prompt("filter_table_info")
        prompt = PromptTemplate(template=tml, input_variables=["query", "table_infos"])
        # 构造结果转化器 强制LLM输出纯标准JSON，自动把JSON 文本解析成 Python list/dict；
        # 后续 chain.ainvoke() 拿到的直接是关键词列表
        output_parser=JsonOutputParser()
        # 定义执行链chain
        chain = prompt | llm | output_parser
        # 执行chain链
        """ 
        yaml.dump 核心目的：
        把内存中 TableInfoState 对象列表(无法直接序列化给大模型读)，转换成人 + 大模型都易读懂、中文正常显示、原有顺序不变的分层文本，填入提示词，让 LLM 准确理解每张表和下属字段，完成筛选逻辑。
        - YAML 缩进分层展示表、字段、描述，LLM 更容易识别每张表包含哪些字段，降低识别出错概率。
        - allow_unicode=True：保留中文不转义
        - sort_keys=False：不自动排序字典 key，原始召回、合并的表顺序有业务意义，强制排序会打乱原有数据顺序
        result：
           {
               "表名1":["字段1", "字段2", "..."],
               "表名2":["字段1", "字段2", "..."]
           }
        """
        result = await chain.ainvoke(
            {"query": query, "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False)})

        ### 大模型根据提示词，返回给我过滤器“必要的信息”，那些不必要的从表信息中砍掉

        # 遍历合并的表信息，过滤合并的表
        for table_info in table_infos[:]:
            # 获取表名
            table_name = table_info["name"]
            # 判断，表名是否在大模型给出的过滤器（必要信息）
            if table_name not in result:
                # 从合并的表信息过滤掉当前表
                table_infos.remove(table_info)
            else:
                # 获取当前表合并后对应的字段列表
                for column in table_info["columns"][:]:
                    # 获取字段名称
                    column_name = column["name"]
                    # 判断
                    if column_name not in result[table_name]:
                        table_info["columns"].remove(column)

        logger.info(f"过滤后的表信息{[table_info['name'] for table_info in table_infos]}")

        return {"table_infos": table_infos}

    except Exception as e:
        logger.error(f"过滤表信息异常：{str(e)}")
        raise