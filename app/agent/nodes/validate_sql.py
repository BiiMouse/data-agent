from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger
import  asyncio

async def validate_sql(state:DataAgentState,runtime:Runtime[DataAgentContext]):
    await asyncio.sleep(1)
    writer = runtime.stream_writer
    writer({"stage": "校验sql语句"})

    try:
        # 校验sql
        # sql:int = 1/0
        logger.info("校验sql正确")
        return {"error":None}
    except Exception as e:
        logger.error(f"校验sql异常{str(e)}")
        return {"error":str(e)}

