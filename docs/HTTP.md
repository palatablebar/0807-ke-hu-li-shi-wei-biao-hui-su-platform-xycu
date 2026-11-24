# 阶段接口

`POST /api/stages/<stage>` 接收 `multipart/form-data`。字段 `sample=dirty`、`sample=clean` 或 `file=<CSV>` 三选一。阶段为 `intake`、`prepare`、`calculate`、`policy`、`balance`。预览不入库。

`POST /api/runs` 接收同样的输入，执行全批并返回运行报告。`GET /api/runs` 返回最近 50 批。`GET /api/runs/<id>` 查询一批和当前复核状态。

`PATCH /api/runs/<id>` 接收 `revision`、`status` 和 `note`。状态使用 `APPROVED` 或 `HELD`。冲突返回 409，客户端读取新版本后重试。

`GET /api/runs/<id>/evidence` 下载内含运行清单、行号隔离、业务证据和复核信息的 JSON。

`POST /api/releases/trial` 接收同样的输入做补录试算，返回按交易时点重算的覆盖变化、未解决交易和时间线问题记录键。试算不入库。

`POST /api/releases` 接收同样的输入发布补录版本，可附试算返回的 `expected` 发布号确保同源；基线变化时返回 409 `TRIAL_STALE`。合并内容相同的重跑返回既有版本，不新增版本号。断档、重叠或未关联交易任一存在时版本保持 `PENDING` 并列出记录键，否则为 `PUBLISHED`。

`GET /api/releases` 返回最近 50 个发布版本。`GET /api/releases/<id>` 查询一个版本的完整报告。`GET /api/releases/<id>/evidence` 下载含合并记录、逐时点对照和问题记录键的 JSON 证据。
