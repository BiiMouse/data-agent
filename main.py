from Lib import uuid
from fastapi import FastAPI, Request

from app.api.routers.query_router import query_router
from app.api.schemas.query_schema import QuerySchema
from app.core.context import request_id_ctx_var
from app.core.lifespan import lifespan

"""
需求：初始化并配置 FastAPI 应用的核心基础设施
    创建 FastAPI 应用实例，绑定 lifespan 生命周期管理器，注册业务路由，
    配置请求上下文中间件，为整个 AI 智能体查询服务提供统一的 Web 框架支撑

为什么这样干：
    1. 统一入口：通过 main.py 作为应用启动的唯一入口，避免配置分散导致维护困难
    2. 生命周期绑定：将 lifespan 函数绑定到 FastAPI 实例，确保应用启动时初始化资源、关闭时释放资源
    3. 路由注册：使用 include_router 将业务路由模块化，避免单个文件路由代码膨胀
    4. 请求追踪：通过中间件为每个请求生成唯一 request_id，方便日志追踪和链路监控

代码隐含问题：
    1. 缺少异常处理：中间件中没有 try-except，如果 call_next(request) 抛出异常，request_id 仍然会被设置但无法记录错误，需要添加异常捕获和日志
    2. 缺少响应头传递：request_id 没有写入响应头（如 X-Request-ID），前端无法获取请求标识用于问题排查
    3. 缺少 CORS 配置：没有配置跨域资源共享策略，前后端分离部署时会导致跨域请求失败
    4. 缺少全局异常处理器：没有注册 @app.exception_handler，未捕获异常会返回默认 HTML 错误页而非 JSON
    5. 缺少健康检查端点：没有提供 /health 或 /ready 端点，Kubernetes 等容器编排平台无法探测应用状态
    6. UUID 生成性能：uuid.uuid4() 每次请求都会调用，对于高并发场景可用雪花算法或 UUID7 提升性能

技术选择：
    FastAPI 框架：
        - 优势1：原生异步支持（基于 Starlette + ASGI），不阻塞事件循环，适合 I/O 密集型业务（数据库查询、向量检索）
        - 优势2：自动生成 OpenAPI 文档（Swagger UI），前端可直接查看接口定义和在线调试
        - 优势3：类型注解驱动（Pydantic 数据校验），参数校验自动化，减少手动编写 if-else 判断
        - 优势4：依赖注入系统，通过 Depends() 可轻松注入数据库会话、配置对象等，代码可测试性强

    lifespan 生命周期管理：
        - 传统替代方案：在 @app.on_event("startup") 中初始化资源，容易忘记释放
        - lifespan 优势：启动和关闭逻辑在同一函数中，用 yield 分隔，代码相邻不易遗漏释放操作

    include_router 路由模块化：
        - 传统替代方案：所有路由写在 main.py 中，文件超过 500 行难以维护
        - include_router 优势：按业务模块拆分路由（query_router、health_router），每个路由文件独立维护，支持版本管理

    中间件机制：
        - 传统替代方案：在每个路由函数中手动生成 request_id 并传入，代码重复度高
        - 中间件优势：全局拦截所有请求/响应，业务路由无需关心 request_id 生成逻辑，符合 AOP 思想
"""
# 创建fastapi的实例
app=FastAPI(lifespan=lifespan)

# 添加路由
app.include_router(query_router)

# 定义中间件
@app.middleware("http")
async def add_request_context_var(request:Request, call_next):
    #赋值上下文变量--用户ID
    request_id_ctx_var.set(uuid.uuid4())
    #请求目标
    response = await call_next(request)

    return response

# 应用启动入口：运行 main.py 即可拉起服务
# 命令：uv run python main.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)

