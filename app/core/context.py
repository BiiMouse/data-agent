from sentry_sdk.utils import ContextVar

"""
需求：为异步 LangGraph Agent 提供请求级别的上下文隔离存储
    在全链路任意节点（日志、SQL执行、异常上报）都能获取到当前请求标识，实现分布式追踪

为什么这样干：
    1. 日志链路区分：并发请求日志混在一起时，通过 request_id 筛选单条提问完整流程（用户提问→召回→生成SQL→执行）
    2. 异常定位：代码抛异常时，从 ContextVar 取 request_id 上报 Sentry，直接定位是哪次用户查询报错
    3. 异步隔离安全：全链路 async 函数，普通全局变量会被并发覆盖；ContextVar 协程隔离，天然无冲突
    4. 贯穿全链路传递：不用把 request_id 一层层传给各节点，任意地方直接 get() 获取，简化代码传参

代码隐含问题：
    1. 必须手动 reset：main.py 中间件调用 set() 后必须调用 reset(token)，否则上下文变量无法释放，长期运行会内存泄漏
    2. 依赖中间件：如果没有 http 中间件设置 request_id，底层 get(None) 会返回 None，日志无法追踪
    3. 缺少默认值策略：get(None) 返回 None 时，日志中会显示 None，建议 get("unknown") 提升可读性

技术选择：
     ContextVar 是上下文变量, 核心能力：协程 / 异步隔离存储，不同 async 请求、不同协程之间变量互不干扰
     request_id_ctx_var 是一个上下文容器，专门用来存储单次请求的唯一追踪 ID（requestId）：
       每一次用户提问、每一次 Agent 执行流程，都会生成一个唯一 request_id；
       存入这个上下文变量后，整个异步链路任意函数都能读取到当前请求 ID；
       你代码里日志 logger.info/logger.error、Sentry 异常上报都可以带上它，实现全链路追踪。
     
     ContextVar（Python 3.7+ 上下文变量）：
        - 对比全局变量 → 并发时会 A 请求覆盖 B 请求的 ID，无法隔离
        - 对比参数传递 → 需要每一层函数都加 request_id 参数，代码膨胀、难以维护
        - ContextVar 优势：协程级别隔离，不同 async 任务互不干扰；无需传参，全局可读

配套用法：
    存值（main.py 中间件）: token = set("req-xxx") →业务逻辑 →reset(token)
    取值（任意节点、日志、异常处理）：req_id = .get(None)  
"""
request_id_ctx_var = ContextVar("request_id")