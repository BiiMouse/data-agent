import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.runtime import Runtime
import asyncio

from app.agent.context import DataAgentContext
from app.agent.llm import llm
from app.agent.state import DataAgentState, TableInfoState, MetricInfoState
from app.core.log import logger
from app.prompt.prompt_loader import loader_prompt


async def generate_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):

    writer = runtime.stream_writer
    writer({"stage": "生成sql语句"})
    """
    需求：生成SQL, 写一个提示词模板，再加上合并表信息、指标信息、时间信息、数据库环境信息、原始问题
        注入到提示词模板，发个LLM来识别，最后呢生成SQL
    节点隐含问题: SQL生成有瞎编的字段，SQL根本是错的，准确率不足90%，将来要解决的
    技术选择：yaml.dump() 核心目的：
        这些提示信息是对象列表(无法直接序列化给大模型读)，转换成人 + 大模型都易读懂、中文正常显示、原有顺序不变的文本，
        然后再填入提示词，让 LLM 准确理解。
        - 降低识别出错概率
        - allow_unicode=True：保留中文不转义
        - sort_keys=False：不自动排序字典 key，原始召回、合并的表顺序有业务意义，强制排序会打乱原有数据顺序
    """
    try:
        # 获取数据表信息如下：
        table_infos=state["table_infos"]
        # 获取可参考的指标信息如下：
        metric_infos=state["metric_infos"]
        # 获取当前的时间信息如下：
        date_info=state["date_info"]
        # 获取数据库环境如下：
        db_info=state["db_info"]
        # 获取问题
        query=state["query"]

        # 获取提示词模板
        tml=await loader_prompt("generate_sql")
        prompt=PromptTemplate(template=tml, input_variables=[
            "query", "table_infos", "metric_infos", "date_info", "db_info"
        ])
        # 定义转化器
        output_parser = StrOutputParser()
        # 定义chain链
        chain = prompt | llm | output_parser
        # 执行chain链
        sql = await chain.ainvoke({
            "query": query,
            "table_infos": yaml.dump(table_infos, allow_unicode=True, sort_keys=False),
            "metric_infos": yaml.dump(metric_infos, allow_unicode=True, sort_keys=False),
            "date_info": yaml.dump(date_info, allow_unicode=True, sort_keys=False),
            "db_info": yaml.dump(db_info, allow_unicode=True, sort_keys=False),
        })

        logger.info(f"生成的[sql]语句\n：{sql}")
        return {"sql": sql}

    except Exception as e:
        logger.error(f"生成sql异常：{str(e)}")
        raise