from langgraph.runtime import Runtime
import asyncio
from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState, TableInfoState, MetricInfoState, ColumnInfoState
from app.core.log import logger
from app.models.es.value_info_es import ValueInfoEs
from app.models.mysql.column_info_mysql import ColumnInfoMySQL
from app.models.mysql.table_info_mysql import TableInfoMySQL
from app.models.qdrant.column_info_qdrant import ColumnInfoQdrant
from app.models.qdrant.metric_info_qdrant import MetricInfoQdrant


async def merge_retrieved_info(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    writer = runtime.stream_writer
    writer({"stage": "合并召回信息"})

    try:
        # 获取召回的字段列表
        retrieved_columns: list[ColumnInfoQdrant] = state["retrieved_columns"]
        # 获取召回的字段取值
        retrieved_values: list[ValueInfoEs] = state["retrieved_values"]
        # 获取召回的指标列表
        retrieved_metrics: list[MetricInfoQdrant] = state["retrieved_metrics"]

        # 获取持久层操作对象, 像这种mysql的持久化的连接，都放在runtime中了
        """
        context.py里的DataAgentContext 静态类型约束规则（给IDE/类型检查看）不生成任何实例，不存数据，没有内存对象
        runtime.context 是运行时真实载体哦！！
        .context 是真正的 Python dict：
            程序启动时提前实例化：ES/Qdrant/MySQL 仓库、embedding 向量模型；
            把所有数据库连接、工具实例塞进这个字典；具体在哪里塞入的的自己看了
            它的结构严格遵守 DataAgentContext 这份 TypedDict 规则。
        """
        meta_mysql_repository = runtime.context["meta_mysql_repository"]

        # 定义收集表信息的列表,
        table_infos: list[TableInfoState] = []
        # 定义收集指标信息列表
        metric_infos: list[MetricInfoState] = []

        ### 阶段1：全局字段字典去重容器初始化
        # 转换召回的字段列表结构为字典结构
        retrieved_columns_map: dict[str, ColumnInfoQdrant] \
            = {retrieved_column["id"]: retrieved_column for
              retrieved_column in retrieved_columns}
        # 1.判断召回的指标中关联的字段是否已经存在, 那就遍历指标，把指标拿出来看。将不存在的查出来，添加到召回字段列表中
        for retrieved_metric in retrieved_metrics:
            # 获取当前指标关联的字段
            relevant_columns = retrieved_metric["relevant_columns"]
            # 遍历指标关联的字段，看召回字段里是不是都召回了
            for relevant_column in relevant_columns:
                if relevant_column not in retrieved_columns_map:
                    # 啥意思呢，召回字段列表里没有 指标所关联的字段，属于缺失，要再召回, 但是没有使用老办法recall_columns: await column_qdrant_repository.search(embedding)
                    # 而是直接到mysql里查，从哪里查没关系，要看查出来的数据怎么用！
                    column_info_mysql: ColumnInfoMySQL =\
                        await meta_mysql_repository.get_column_info_by_id(relevant_column)
                    # 类型转换  ColumnInfoMySQL -> ColumnInfoQdrant
                    column_info_qdrant:ColumnInfoQdrant = _conver_column_info_form_mysql_to_qdrant(column_info_mysql)
                    # 缺的从mysql复查回了，将类型对齐后，我们就可以在召回字段列表中加入“它”了
                    # relevant_column 和 column_info_qdrant["id"] 是一个东西
                    retrieved_columns_map[relevant_column] = column_info_qdrant

        #2.判断召回的字段取值对应的字段信息是否已经存在, 将不存在的查出来，还是要添加到召回字段列表中
        for retrieved_value in retrieved_values:
            # 获得当前值对应的 对象的字段id
            column_id = retrieved_value["column_id"]
            #获得召回的字段取值
            column_value = retrieved_value["value"]
            #判断
            if column_id not in retrieved_columns_map:
                #根据id查询字段信息
                column_info_mysql: ColumnInfoMySQL = await meta_mysql_repository.get_column_info_by_id(column_id)
                #转换类型 ColumnInfoMySql => ColumnInfoQdrant
                column_info_qdrant:ColumnInfoQdrant = _conver_column_info_form_mysql_to_qdrant(column_info_mysql)
                #加入字段类型
                retrieved_columns_map[column_id] = column_info_qdrant

            #判断当前召回的值，是否存在对应字段的 examples:list 属性中, examples是一个字段的取值例子，有多个
            if column_value not in retrieved_columns_map[column_id]["examples"]:
                #存储当前召回的值
                retrieved_columns_map[column_id]["examples"].append(column_value)

        ## 至此，召回的字段列表应当是完整的了。指标依赖的字段、字段值对应的字段都能在字段表里找到，并且字段值也添加到字段的examples中

        #3. 根据所有的字段，以表分组整合
        # 表1----字段1:ColumnInfoQdrant，字段2:ColumnInfoQdrant，字段3:ColumnInfoQdrant
        # 表2----字段1:ColumnInfoQdrant，字段2:ColumnInfoQdrant，字段3:ColumnInfoQdrant
        # key--table_id    value--字段列表
        table_to_column_map:dict[str, list[ColumnInfoQdrant]] = {}
        # 遍历召回的字段列表，构建表和字段的关联
        for column in retrieved_columns_map.values():
            #获取当前字段对应的表信息
            table_id:str = column["table_id"]
            #判断
            if table_id not in table_to_column_map:
                table_to_column_map[table_id] = []
            #添加字段到表的关联中
            table_to_column_map[table_id].append(column)

        # 处理表对应的主键/外键关系
        for table_id in table_to_column_map.keys():

            ####根据表id查询当前表的主键和外键
            key_columns: list[ColumnInfoMySQL] = await meta_mysql_repository.get_key_columns_by_table_id(table_id)

            #获取当前表对应的所有字段的id, 拿出每个字段id
            column_ids: list = [column["id"] for column in table_to_column_map[table_id]]

            #遍历查询的主外键列表
            for key_column in key_columns:
                # 获取ID
                column_id = key_column.id # ???????????
                # 判断是否已经存在
                if column_id not in column_ids:
                    # ??????????
                    table_to_column_map[table_id].append(_conver_column_info_form_mysql_to_qdrant(key_column))

        # 构建表和字段的完整结构信息[(key:value),(key:value)]
        for table_id, columns in table_to_column_map.items():
            # table_id 表ID
            # columns: 对应的字段列表
        
            # ？转换字段列表对应的实体结构 这里的转换为啥不在前面早一点做
            #   - table_to_column_map 里是基于召回数据的经过多层修复、补全后的存储层完整数据集，数据属于存储层
            #   - columns_state 是要LangGraph 流程运行态 State 模型，属于运行视图（运行时）
            #   * 核心分层逻辑：运行、存储是两套独立数据格式
            #   # 前置所有操作都是存储层数据修复逻辑：数据库补查缺失字段、取值examples回填、表-字段分组，全程依赖存储主键id/table_id，因此统一使用存储层模型ColumnInfoQdrant
            #   * 待所有存储层数据加工完成后，再统一转换为流程State实体，供给LangGraph后续节点使用，切换为运行时数据
            # ？提前转换的后果：
            #   * 丢失存储主键，后续分组、查表主外键、匹配指标关联字段、匹配取值column_id全部依赖id/table_id；
            #   * 如果提前转ColumnInfoState，就拿不到主键，无法执行补查、分组、关联修复逻辑
            # ？类型转换写在table遍历循环内部仅为代码简洁性考量
            #  1. 所有存储层数据修复、主外键补全逻辑已在循环外全部完成，循环仅读取完整后的只读存储数据，不再修改原始字段、不再查询数据库；
            #  2. 单张表与下属字段天然绑定，就地完成存储模型→运行态State转换，直接组装TableInfoState，避免二次分组遍历，简化代码。
            columns_state = [
                ColumnInfoState(
                    name= column['name'],
                    type= column['type'],
                    role= column['role'],
                    examples=column['examples'],
                    description= column['description'],
                    alias= column['alias'],
                )for column in columns
            ]
            # 此时还没有表的实体信息，应该通过table_id查出来
            table_info_mysql:TableInfoMySQL = await meta_mysql_repository.get_table_by_id(table_id)
            # 转化结构
            table_info = TableInfoState(
                name = table_info_mysql.name,
                role = table_info_mysql.role,
                description = table_info_mysql.description,
                columns = columns_state
            )
            # 收集表信息对象
            table_infos.append(table_info)

        logger.info(f"合并表信息完成，表信息{[table_info.name for table_info in table_infos]}")

        # 处理指标信息，构建指标数据结构
        for retrieved_metric in retrieved_metrics:
            # 构建实体
            metric_info_state = MetricInfoState(**retrieved_metric)
            # 收集指标数据
            metric_infos.append(metric_info_state)

        logger.info(f"合并指标信息完成，指标信息{[metric_info.name for metric_info in metric_infos]}")


        #### 至此，我们获得了2个关键集合
        # table_infos: list[TableInfoState] 整合后的表 + 字段运行态数据
        # metric_infos: list[MetricInfoState] 转换后的指标运行态数据

        # 下游节点直接通过 state["table_infos"]、state["metric_infos"] 读取整合好的表、指标运行态数据
        return {"table_infos": table_infos, "metric_infos": metric_infos}

    except Exception as e:
        logger.error(f"合并召回信息异常{str(e)}")
        raise


# ColumnInfoQdrant(xxx=xxx) 只是简写语法，运行出来还是普通 dict；
# 函数返回的不是类对象(或实例)，只是符合格式规范的字典。
def _conver_column_info_form_mysql_to_qdrant(column_info_mysql:ColumnInfoMySQL)->ColumnInfoQdrant:
    return ColumnInfoQdrant(
        id=column_info_mysql.id,
        name=column_info_mysql.name,
        type=column_info_mysql.type,
        role=column_info_mysql.role,
        examples=column_info_mysql.examples,
        description=column_info_mysql.description,
        alias=column_info_mysql.alias,
        table_id=column_info_mysql.table_id
    )