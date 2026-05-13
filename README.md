# astrbot_plugin_datacheck

AstrBot 错误日志查询插件，用于查询 AstrBot 近 N 小时内的错误日志，通过 OneBot V11 合并转发消息发送给用户。

## 功能

- **指令触发**：发送 `/查日志` 查询近 N 小时内的错误日志
- **LLM 意图识别**：用户提到"签到失败"、"掉线"、"报错"等关键词时，LLM 自动调用查询工具
- **合并转发**：错误日志以合并转发消息形式发送，避免刷屏
- **权限控制**：支持配置仅管理员可用或所有用户可用
- **日志级别筛选**：可自定义勾选返回 WARN、ERRO、CRIT 级别的日志
- **关键字过滤**：支持正则表达式关键字匹配，在级别过滤基础上进一步筛选

## 适配平台

仅支持 OneBot V11（aiocqhttp）。

## 配置项

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `admin_only` | bool | true | 仅管理员可查询日志 |
| `hours` | int | 24 | 扫描最近多少小时内的日志 |
| `log_levels` | object | ERRO: true, CRIT: true, WARN: false | 勾选要返回的日志级别 |
| `keyword` | string | "" | 关键字正则表达式，留空则不过滤 |

## 前置条件

需要在 AstrBot 中启用文件日志功能，插件会读取 `data/logs/astrbot.log` 及其轮转文件。

## 相关链接

- [AstrBot](https://github.com/AstrBotDevs/AstrBot)
- [AstrBot 插件开发文档](https://docs.astrbot.app/dev/star/plugin-new.html)
