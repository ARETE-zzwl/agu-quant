# 私有部署服务

## 服务定位

私有部署面向希望在自有服务器、内网或专属云环境运行 TradingAgents-Astock 的团队。费用对应部署、集成、培训和持续支持，不包含投资收益承诺，也不出售 Apache 2.0 已授予的源码权利。

## 标准交付范围

- Docker 化 Web 服务与持久化数据卷。
- 一个模型服务商的 API 接入与连通性验证。
- 管理员账号、日志目录和自动日报配置。
- 一次远程部署与一次使用培训。
- 部署文档、环境变量清单和验收记录。

额外数据源、统一身份认证、企业微信通知、GPU 推理和定制 Agent 单独评估。

## 快速部署

1. 准备 Docker Engine 与 Docker Compose。
2. 复制 `.env.enterprise.example` 为 `.env.private`。
3. 设置随机管理员密码和至少一个模型 API Key。
4. 执行：

```powershell
.\scripts\start_private.ps1 -EnvFile .env.private
```

Linux/macOS 可执行：

```bash
python scripts/private_deploy_check.py --env-file .env.private
docker compose --env-file .env.private -f docker-compose.private.yml up -d --build
```

健康检查地址：`http://localhost:8501/_stcore/health`。

## 安全要求

- 管理员账号必须通过环境变量配置，项目不再提供默认管理员密码。
- 公网入口必须由 Nginx、Caddy 或云负载均衡终止 HTTPS。
- `.env.private`、许可证私钥和模型 Key 不得提交到仓库。
- 建议通过防火墙、VPN 或零信任网关限制访问范围。
- 备份 `tradingagents_private_data` 数据卷，并定期验证恢复。
- 上线前核对第三方模型与数据源服务条款。

## 验收标准

- `scripts/private_deploy_check.py` 无错误退出。
- 容器健康检查为 healthy，重启后数据仍存在。
- 管理员可登录，未配置账号无法获得管理员权限。
- 指定模型能完成至少一只测试股票的分析。
- 自动日报能生成并写入持久化目录。
- 日志中不包含完整 API Key、密码或激活码。

## 服务套餐建议

| 服务 | 参考范围 | 交付内容 |
|---|---:|---|
| 标准私有部署 | 2999 元起 | 单机 Docker、一个模型接入、培训与验收 |
| 团队部署 | 7999 元起 | 反向代理、备份、通知、多人使用与升级支持 |
| 定制 Agent | 3000 元/个起 | 需求澄清、工具接入、提示词、测试和文档 |
| 年度支持 | 单独报价 | 升级、故障响应、数据源适配和 SLA |

最终报价应根据服务器数量、网络条件、数据源、模型、交付周期和支持时段确认。
