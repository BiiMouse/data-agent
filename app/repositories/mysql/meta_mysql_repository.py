from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mysql.column_info_mysql import ColumnInfoMySQL
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
