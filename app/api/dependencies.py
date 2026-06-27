
from fastapi.params import Depends
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.embedding_client_manager import embedding_client_manager
from app.clients.es_client_manager import es_client_manager
from app.clients.mysql_client_manager import meta_mysql_client_manager, dw_mysql_client_manager
from app.clients.qdrant_client_manager import qdrant_client_manager
from app.repositories.es.values_es_repository import ValueEsRepository
from app.repositories.mysql.dw_mysql_repository import DwMysqlRepository
from app.repositories.mysql.meta_mysql_repository import MetaMysqlRepository
from app.repositories.qdrant.column_qdrant_respository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.services.query_service import QueryService

"""
整体设计：FastAPI 依赖注入层，封装 AI Agent 查询服务的所有底层依赖
    这段代码在干嘛：
    1. 定义一系列依赖函数，将全局单例（embedding_client_manager、qdrant_client_manager）转换为可注入的依赖
    2. 管理 MySQL 数据库会话生命周期（请求时创建、响应时自动释放）
    3. 汇总所有依赖注入到 QueryService，供路由层通过 Depends(get_query_service) 一键获取完整服务

    依赖注入链路：
    路由层 Depends(get_query_service)
        → Depends(get_embeddings) + get_*_repository + get_*_mysql_repository
            → Depends(get_*_session)
                → 客户端管理器（embedding_client_manager、qdrant_client_manager、mysql_client_manager）

为什么这样干：
    1. 解耦测试：路由函数不直接依赖全局变量，通过依赖注入可轻松 mock 进行单元测试
    2. 自动资源管理：MySQL session 用 async with yield 实现请求结束自动释放，避免连接泄漏
    3. 依赖可视化：通过 Depends() 参数清晰看到函数依赖关系，比隐式全局变量更易维护
    4. 复用性强：多个路由可共享同一依赖函数，避免重复初始化代码

技术选择：
    async with yield（异步上下文管理器）：
        - 作用：在请求开始时执行 yield 前的代码（创建会话），请求结束后执行 yield 后的清理（关闭会话）
        - 对比手动 close：无需在路由中显式调用 session.close()，即使路由抛异常也会自动清理
        - 适用场景：数据库连接、文件句柄、网络连接等需要释放的资源
"""
async def get_embeddings() -> HuggingFaceEndpointEmbeddings:
    """获取向量模型实例（全局单例，无状态）"""
    return embedding_client_manager.embeddings


async def get_column_qdrant_repository() -> ColumnQdrantRepository:
    """获取字段向量库仓储（依赖 Qdrant 客户端）"""
    return ColumnQdrantRepository(qdrant_client_manager.client)


async def get_metric_qdrant_repository() -> MetricQdrantRepository:
    """获取指标向量库仓储（依赖 Qdrant 客户端）"""
    return MetricQdrantRepository(qdrant_client_manager.client)


async def get_value_es_repository() -> ValueEsRepository:
    """获取字段取值 ES 仓储（依赖 ES 客户端）"""
    return ValueEsRepository(es_client_manager.client)


async def get_meta_session() -> AsyncSession:
    """
    获取元数据库 MySQL 会话（请求结束后自动释放）
    使用 async with yield 确保：请求结束时 session.close() 自动调用，即使路由抛异常也会执行
    """
    async with meta_mysql_client_manager.session_factory() as session:
        yield session


async def get_meta_mysql_repository(session: AsyncSession = Depends(get_meta_session)) -> MetaMysqlRepository:
    """获取元数据仓储（依赖 MySQL 会话）"""
    return MetaMysqlRepository(session)


async def get_dw_session() -> AsyncSession:
    """
    获取数据仓库 MySQL 会话（请求结束后自动释放）
    与 get_meta_session 独立，支持同时查询元数据库和业务数据库
    """
    async with dw_mysql_client_manager.session_factory() as session:
        yield session


async def get_dw_mysql_repository(session: AsyncSession = Depends(get_dw_session)) -> DwMysqlRepository:
    """获取数据仓库仓储（依赖 MySQL 会话）"""
    return DwMysqlRepository(session)


async def get_query_service(
        # 依赖注入：FastAPI 自动解析依赖树，按需创建并缓存实例
        embeddings: HuggingFaceEndpointEmbeddings = Depends(get_embeddings),
        column_qdrant_repository: ColumnQdrantRepository = Depends(get_column_qdrant_repository),
        metric_qdrant_repository: MetricQdrantRepository = Depends(get_metric_qdrant_repository),
        value_es_repository: ValueEsRepository = Depends(get_value_es_repository),
        meta_mysql_repository: MetaMysqlRepository = Depends(get_meta_mysql_repository),
        dw_mysql_repository: DwMysqlRepository = Depends(get_dw_mysql_repository)
) -> QueryService:
    """
    汇总所有依赖，返回 QueryService 实例
    路由层使用示例：
        @app.post("/query")
        async def query(service: QueryService = Depends(get_query_service)):
            return await service.execute_query("...")
    """
    return QueryService(
        embeddings=embeddings,
        column_qdrant_repository=column_qdrant_repository,
        metric_qdrant_repository=metric_qdrant_repository,
        value_es_repository=value_es_repository,
        meta_mysql_repository=meta_mysql_repository,
        dw_mysql_repository=dw_mysql_repository
    )
