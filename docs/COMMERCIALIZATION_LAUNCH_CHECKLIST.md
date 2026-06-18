# 商业化上线清单

以下事项需要维护者的真实账号、凭据或外部运行环境，代码不能代替完成。

## 1. 官方入口

- [ ] 配置 HTTPS 支付或赞助地址 `TA_SUPPORT_URL`。
- [ ] 配置公开支持渠道 `TA_SUPPORT_CONTACT`。
- [ ] 配置企业咨询渠道 `TA_ENTERPRISE_CONTACT`。
- [ ] 核对二维码收款主体后，按需设置 `TA_SPONSOR_QR_ENABLED=true`。
- [ ] 明确退款、发票、服务期限和人工支持范围。
- [ ] 确认页面、邮件和收款主体使用一致的官方身份。

## 2. Windows 与镜像发布

- [ ] 审查并提交当前商业化相关改动，然后推送到 GitHub。
- [ ] 在 GitHub Actions 手动运行一次 `Windows Release`，验证分支构建使用项目版本号。
- [ ] 创建语义版本标签，例如 `v0.3.0`，生成正式 GitHub Release。
- [ ] 下载 ZIP，在一台干净 Windows 机器启动 EXE 并安装每日任务。
- [ ] 如启用国内镜像，在 GitHub Secrets 配置 `MIRROR_ENDPOINT`、`MIRROR_BUCKET`、`MIRROR_PUBLIC_BASE_URL`、`MIRROR_ACCESS_KEY_ID`、`MIRROR_SECRET_ACCESS_KEY` 和 `MIRROR_REGION`。
- [ ] 镜像上传后配置客户端 `TA_UPDATE_MANIFEST_URL`，验证镜像不可用或落后时会回退 GitHub。
- [ ] 决定 GitHub Release 是否公开。公开 Release 不能作为严格 VIP 下载边界；需要限制下载时，应使用支付系统签发的对象存储临时链接。

## 3. 私有部署验收

- [ ] 在具备 Docker Engine 与 Docker Compose 的机器复制 `.env.enterprise.example` 为 `.env.private`。
- [ ] 设置至少 12 位随机管理员密码和一个真实模型 API Key。
- [ ] 运行 `scripts/start_private.ps1 -EnvFile .env.private`。
- [ ] 确认容器 healthy、管理员可登录、模型分析成功、日报写入持久化卷。
- [ ] 确认构建镜像不包含 `.env.private` 或其他密钥文件。
- [ ] 公网部署前配置 HTTPS 反向代理、防火墙、备份和恢复演练。

## 4. 订单与授权

- [ ] 决定支持者版和 Pro 版的订单记录方式、到期时间和设备数。
- [ ] 使用管理员页面或 `python -m tradingagents.auth.admin_tool generate --plan supporter|pro ...` 生成分级激活码。
- [ ] 如需自动发码，选择真实支付服务商并实现服务端回调；不要把支付密钥放进桌面客户端或公开仓库。
- [ ] 记录客户套餐、交付版本、服务起止时间和验收结果。

## 5. 服务边界

- [ ] 私有部署报价前使用 `CUSTOM_AGENT_BRIEF.md` 完成需求澄清。
- [ ] 合同中区分软件部署费、模型费用、数据费用、云资源费和持续支持费。
- [ ] 不承诺证券收益，不把研究报告包装成持牌投资咨询。
- [ ] 明确故障响应时间、升级次数、数据源变更和超范围需求的报价方式。

## 技术边界

当前开源客户端的许可证是便利性和服务权益标记，不是不可绕过的 DRM。真正需要保护的是支付凭据、镜像写入权限、企业数据和服务端自动发码能力，这些必须放在维护者控制的服务端或密钥管理系统中。
