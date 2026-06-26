from sqlalchemy import Select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.column_metric_mysql import ColumnMetricMySQL
from app.models.mysql.metric_info_mysql import MetricInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL


class MetaMysqlRepository:
    def __init__(self,session:AsyncSession):
        self.session = session

    async def save_table_infos(self, table_infos:list[TableInfoMySQL]):
        """
        保存表信息到meta数据库
        :param table_infos:
        :return:
        """
        self.session.add_all(table_infos)

    async def save_column_infos(self, column_infos:list[ColumnInfoMySQL]):
        """
        保存字段信息到meta数据库
        :param column_infos:
        :return:
        """
        self.session.add_all(column_infos)

    async def save_metrics(self, metric_infos:list[MetricInfoMySQL]):
        """
        保存指标信息到meta数据库
        :param metric_infos:
        :return:
        """
        self.session.add_all(metric_infos)

    async def save_column_metrics(self, column_metrics:list[ColumnMetricMySQL]):
        """
        保存字段指标关联信息到meta数据
        :param column_metrics:
        :return:
        """
        self.session.add_all(column_metrics)

    async def get_column_info_by_id(self, column_id:str):
        """
        根据字段id查询字段信息对象
        :param column_id:
        :return:
        """
        return await self.session.get(ColumnInfoMySQL, column_id)

    async def get_key_columns_by_table_id(self, table_id:str):
        """
        根据表id查询当前表的主键和外键
        select * from column_info
        where role in ('primary_key', 'foreign_key')
            and table_id = 'fact_order'
        :param table_id:
        :return:
        """
        #定义sql
        sql = """
            select*
            from column_info
            where role in ('primary_key', 'foreign_key'
            and table_id = :table_id)
        """
        # 设置封装结构
        query = Select(ColumnInfoMySQL).from_statement(text(sql))
        # 执行sql，你的 SQL 查询映射了完整 ORM 模型 ColumnInfoMySQL，Result 内部存储的是行元组（Row）
        # 结果ScalarResult-->[(ColumnInfoMysql对象),(ColumnInfoMysql对象),(ColumnInfoMysql对象)]
        result = await self.session.execute(query, {"table_id": table_id})

        """
        .scalars() 作用：剥离行元组，直接取出实体对象
        数据库查询返回的每行数据在 SQLAlchemy 里封装成 Row 对象，哪怕只查一张表完整实体，Row 也是元组容器
        调用 .scalars()：返回 ScalarResult 迭代器，自动取出 Row 里第一个位置的实体对象，丢掉外层元组包装
        """
        """
        .fetchall() 作用：一次性取出迭代器中全部数据，返回 list
        ScalarResult / 原生 Result 都是惰性迭代器，不会主动加载所有数据到内存：
        .fetchall()：一次性遍历迭代器，把所有结果组装成 list[模型对象] 返回；
        """
        return result.scalars().fetchall()

    async def get_table_by_id(self, table_id: str):
        """
        根据表ID查询表信息对象
        :param table_id:
        :return:
        """
        return await self.session.get(TableInfoMySQL, table_id)
