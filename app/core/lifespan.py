from contextlib import asynccontextmanager

from app.clients.qdrant_client_manager import qdrant_client_manager
from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager

"""
需求：管理 FastAPI 应用的全生命周期资源
    在应用启动时初始化所有全局依赖（向量模型、数据库连接、向量库客户端等）
    在应用关闭时释放所有长连接资源（数据库连接池、网络连接等），避免内存泄漏

为什么这样干：
    1. 资源集中管理：所有依赖的初始化和释放逻辑集中在一处，避免散落在各个模块中难以维护
    2. 启动优化：应用启动时一次性初始化所有资源，避免首次请求时延迟初始化导致的性能抖动
    3. 优雅关闭：应用接收到关闭信号（SIGTERM/SIGINT）时，先等待当前请求处理完成，再释放资源
    4. 自动化：配合 FastAPI 的 lifespan 机制，无需手动管理启动/关闭逻辑

代码隐含问题：
    1. 初始化失败处理：如果某个 init() 失败（如数据库连接超时），应用启动会中断，需要配合健康检查和重试机制
    2. 关闭顺序依赖：yield 前的初始化顺序应与 yield 后的释放顺序相反（类似栈的 LIFO），避免依赖方先关闭导致被依赖方无法正常关闭
    3. 异常传播：如果某个 close() 抛出异常，会导致后续 close() 不执行，需要包装在 try-except 中确保所有资源都被释放
    4. embedding_client_manager 无 close：HuggingFace 接口无长连接，但其他三个都有 close()，代码逻辑不统一（这是正确的，但需要注释说明）

技术选择：
    @asynccontextmanager（Python 异步上下文管理器装饰器）：
        - 优势1：自动化资源管理，使用 yield 分隔初始化和释放逻辑，代码简洁易读
        - 优势2：异常安全，即使 yield 前抛出异常，yield 后的清理代码也会执行（类似 try-finally）
        - 优势3：符合 Python 上下文管理协议，可被 FastAPI 的 lifespan 参数直接使用
        - 优势4：异步支持，不会阻塞事件循环，适合 I/O 密集型初始化（如数据库握手）

    FastAPI Lifespan 机制：
        - 传统替代方案：在 @app.on_event("startup") 和 @app.on_event("shutdown") 中分别编写初始化和释放逻辑
        - 上下文管理器的优势：逻辑集中在一个函数中，初始化和释放代码相邻，减少忘记释放的风险
        - 官方推荐：FastAPI 0.93.0+ 推荐使用 lifespan 而非事件监听器，更符合依赖注入思想
"""
@asynccontextmanager
async def lifespan():
    # 创建依赖对象
    # 初始化客户端对象
    embedding_client_manager.init()
    qdrant_client_manager.init()
    es_client_manager.init()
    meta_mysql_client_manager.init()
    dw_mysql_client_manager.init()

    yield

    # 释放资源
    """
    原因：embedding_client_manager 是调用第三方 API（HuggingFace 接口），没有长连接本地资源，
    不存在数据库 / 向量库 TCP 连接需要手动关闭；
    而 qdrant、es、mysql 都是本地 / 远程长连接客户端，占用网络连接池，必须手动close()释放连接，
    """
    qdrant_client_manager.close()
    es_client_manager.close()
    meta_mysql_client_manager.close()
    dw_mysql_client_manager.close()