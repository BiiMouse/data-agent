from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class DwMysqlRepository:
    def __init__(self,session:AsyncSession):
        self.session = session

    async def get_column_types(self, table_name:str):
        """
        获取表的字段和类型列表
        :param table_name:
        :return:
        """
        # 定义sql
        sql = f"SHOW COLUMNS from {table_name}"
        # 执行sql
        result =  await self.session.execute(text(sql))
        # 获取结果 [(Row),(Row),(Row)]
        return {row.Field: row.Type for row in result.fetchall()}

    async def get_column_values(self, table_name, column_name,limit:int = 10 ):
        """
        查询当前字段的取值实例
        :param table_name:
        :param column_name:
        :return:
        """
        # 定义sql
        sql = f"select distinct {column_name} from {table_name} limit {limit}"
        # 执行sql
        result = await self.session.execute(text(sql))
        # 获取结果scalar 讲第一列数据的所有行，封装到一个列表中
        return result.scalars().fetchall()