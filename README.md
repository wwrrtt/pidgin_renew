# PidginHost 免费服务器自动续期

通过 GitHub Actions 定时自动登录 [PidginHost](https://www.pidginhost.com/panel/account/login) 面板，点击 **Extend 30 days** 续期免费服务器，并通过 Telegram 发送执行结果通知。

## 文件结构

```
├── pidgin_renew.py              # 主脚本（GitHub Actions 用）
├── pidgin_login.py              # 本地调试版（有头浏览器，硬编码账号，仅测试用）
├── requirements.txt             # Python 依赖
└── .github/workflows/
    └── pidgin-renew.yml         # GitHub Actions 工作流
```

## 工作原理

`pidgin_renew.py` 执行流程：

1. 打开登录页，输入邮箱 → 点击 "Log in / Sign up"
2. 输入密码 → 回车提交
3. 等待跳转 `/panel/`，进入服务器管理页
4. 读取当前过期天数（如 "This free server expires in 25 days"）
5. 已是 30 天 → 跳过；否则点击 "Extend 30 days"
6. 验证续期后天数变化，通过 Telegram 发送结果

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `PIDGIN_EMAIL` | ✅ | PidginHost 账号邮箱 |
| `PIDGIN_PASSWORD` | ✅ | PidginHost 账号密码 |
| `TG_BOT_TOKEN` | ❌ | Telegram bot token（不配则不发通知） |
| `TG_CHAT_ID` | ❌ | Telegram chat ID |
| `PROXY_SOCKS5` | ❌ | SOCKS5 代理，如 `socks5://127.0.0.1:10808` |
| `XRAY_CONFIG_JSON` | ❌ | Xray 代理配置 JSON（workflow 用） |

## GitHub Actions 配置

1. 把代码推到 GitHub 仓库
2. **Settings → Secrets and variables → Actions** 添加 Secrets：
   - `PIDGIN_EMAIL`、`PIDGIN_PASSWORD`（必填）
   - `TG_BOT_TOKEN`、`TG_CHAT_ID`（可选，Telegram 通知）
   - `XRAY_CONFIG_JSON`（可选，走代理；Vmess 链接可先 base64 解码再转 Xray JSON 格式）
3. 工作流默认每天 UTC 12:00 运行，也可在 **Actions** 页面手动触发（Run workflow）

## 本地运行

```bash
# 设置环境变量（Windows PowerShell）
$env:PIDGIN_EMAIL = "your@email.com"
$env:PIDGIN_PASSWORD = "your-password"

# Linux / macOS
export PIDGIN_EMAIL="your@email.com"
export PIDGIN_PASSWORD="your-password"

python pidgin_renew.py
```

## 退出码

| 状态 | 含义 | 退出码 |
|------|------|--------|
| `success` | 续期成功 | 0 |
| `noop` | 已是 30 天，跳过 | 0 |
| `unchanged` | 天数未变化 | 0 |
| `login_failed` / `exception` 等 | 失败 | 1 |
