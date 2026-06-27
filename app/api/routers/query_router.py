import asyncio
from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.api.dependencies import get_query_service
from app.api.schemas.query_schema import QuerySchema
from app.services.query_service import QueryService

# 创建路由实例
query_router = APIRouter()

# 定义查询接口
@query_router.post("/api/query")
async def create_item(query: QuerySchema,service:QueryService=Depends(get_query_service)):
    # 调用查询实现
    return StreamingResponse(service.query(query.query),media_type="text/event-stream")


#
# async def fake_video_streamer():
#     for i in range(10):
#         # 添加睡眠，演示延时效果
#         await asyncio.sleep(1)
#         yield f"data: stage:{i} \n\n"
#
#
#
# @query_router.post("/api/query")
# async def query(query: QuerySchema):
#     return  StreamingResponse(fake_video_streamer(),media_type="text/event-stream")

