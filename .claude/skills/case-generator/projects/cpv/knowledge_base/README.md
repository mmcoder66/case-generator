# knowledge_base 读取说明

`knowledge_base` 用于维护 CPV 项目背景、菜单结构、业务术语、用户角色和核心业务流程。生成测试用例时，本目录只提供业务上下文补充，不会默认全量读取。

## 读取原则

- 仅在需要项目背景、菜单结构、业务术语、用户角色或核心流程上下文时读取本目录文件。
- 业务术语统一维护在 `business_glossary.md`，其他知识库文件只引用术语，不重复维护术语解释。
- 项目背景、站点关系、菜单层级和标准模块名统一维护在 `project_overview.md`；产品数据权限适用范围只在 `user_roles.md` 维护。
- `core_flows/` 下的流程文件按命中的业务场景读取。例如数据分析、监控项目分析、相关性分析或一键分析相关需求，才读取对应流程说明。
- 除非信息不足、校验失败或用户明确要求，不主动读取全部 `knowledge_base` 文件，避免无关背景干扰当前模块用例。


## 当前核心流程文件

- `core_flows/cpv_business_flow.md`：CPV 主业务链路。
- `core_flows/login_flow.md`：登录与站点入口流程。
- `core_flows/data_analysis_flow.md`：数据分析工作台、监控项目和相关性分析三类入口的数据分析流程。
- `core_flows/one_click_analysis_flow.md`：一键分析、数据替换和自动重分析流程。
