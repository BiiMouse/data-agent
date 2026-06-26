import asyncio
from datetime import datetime

from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, DateInfoState
from app.core.log import logger


async def add_extra_context(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "添加额外上下文"})
    # 为什么要添加时间和数据库上下文
    """
    1、为什么要添加时间
        解决用户自然语言口语化时间描述，模糊的时间，自动对齐真实业务时间范围。
        注入范围是日期、星期、季度Q1Q2， 统一指标口径，避免时间维度统计逻辑混乱
    2、为什么必须添加数据库配置信息上下文（db_info）
        不同数据库（MySQL/Oracle）语法、函数完全不一样，
        适配数据库方言与版本，生成可直接执行的标准 MySQL 语法
    收益：
        大幅降低 SQL 报错率
        时间口径统一，字段真实存在，关联逻辑正确 => 指标结果精准
        不用硬编码时间、表结构，每天自动刷新当日时间，库变更自动同步 db_info => 通用性强
    隐含问题等待挖掘
    技术选择：没有
    """
    try:
        # 添加时间信息
        today=datetime.today()
        # 当前时间
        date = today.strftime("%Y-%m-%d")
        # 星期
        weekday = today.strftime("%A")
        # 获取月份
        month=today.month
        # 季度
        quarter=f"Q{(month - 1) // 3 + 1}"
        # 封装时间
        date_info = DateInfoState(date=date, weekday=weekday, quarter=quarter)

        #  获取repository 这算是获得了什么呢？应当时mysql数据库的实例
        dw_mysql_repository = runtime.context["dw_mysql_repository"]
        # 添加数据库信息，方言、版本
        db_info = await dw_mysql_repository.get_db_info()

        logger.info(f"额外上下文信息添加，日期信息{date_info},数据库信息{db_info}")

        return {"date_info": date_info, "db_info": db_info}

    except Exception as e:
        logger.error(f"添加额外上下文发生异常：{str(e)}")
        raise