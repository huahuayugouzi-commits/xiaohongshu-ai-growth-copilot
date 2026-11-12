# Growth Copilot 私人试用部署（Ubuntu 24.04）

2026-11-12。目标：腾讯云香港、5–10 名邀请用户。不是公开注册 SaaS。
用户已选择 A：服务器使用全新空数据库。本地历史账号、研究、草稿、评委演示库一律不上传。

## 边界与路径

- 公网入口：Caddy HTTPS → `127.0.0.1:7860` → `web.production:create_app`。
- **禁止**将旧的 `web.app:app`、开发用 Vite 或评委共用账号入口用于独立用户部署。
- 用户由管理员创建，不开放注册。登录密码使用 scrypt；会话只存令牌哈希，有效期8小时。注销/禁用可撤销。
- 新账号与登录用户在同一事务中绑定。所有 Growth 路由在操作/模型调用前校验所有者；历史未归属记录默认不可访问。
- `/opt/growth-copilot/releases/版本号`：只读代码及每版本虚拟环境；`current` 指向当前版本。
- `/var/lib/growth-copilot/growth.sqlite3`：业务、用户、会话与限额。数据库不在发布目录内，升级保留。
- `/var/lib/growth-copilot/profiles`：私有画像导出，不提供公网文件访问。
- `/var/backups/growth-copilot`：每日数据库快照和画像归档。
- `/etc/growth-copilot/app.env`：root所有，0600。由 systemd 注入模型配置，不能提交Git。
- 每用户模型请求4次/分钟、60次/滚动24小时。失败尝试也计数；这是次数限额，不是金额上限。无自动付费调用测试。

## 本地发布包

先运行 TypeScript、lint、production build；确认授权/核心回归通过。将审核过的源码暂存或提交后运行：

```powershell
.\.venv\Scripts\python.exe deploy/ubuntu24/package_release.py outputs/releases/growth-private-20261112.tar.gz
```

只打包白名单中的已跟踪运行源码、部署文件、License、README及编译好的前端。无Git历史、.env、SQLite、profiles、原始用户数据、日志或模型输出。脚本不会覆盖同名包。`release-manifest.json`用于传输完整性验证，不是数字签名；只使用自己生成并通过SSH传送的包。

## 服务器准备（实际执行前确认目标主机）

1. 确认香港 Ubuntu 24.04 新主机、可用磁盘、sudo SSH、域名解析。不要把SSH私钥/密码发到聊天中。
2. 安全组仅对外开放80/443；SSH限制为管理员IP；**不开放7860**。
3. 上传发布包到管理员目录；只解压本地已审核的包，且目标版本目录必须为空。不要复制整个本地项目。

```bash
sudo install -d -m 0755 /opt/growth-copilot/releases/20261112
sudo tar -xzf growth-private-20261112.tar.gz -C /opt/growth-copilot/releases/20261112
sudo bash /opt/growth-copilot/releases/20261112/deploy/ubuntu24/prepare.sh
```

prepare安装Python3.12/虚拟环境及现有依赖，建立专用growth用户、独立数据库与systemd单元；不启动公网、不覆盖已有环境文件、不切换运行版本。重复执行保留用户/数据库；已有未归属历史数据时拒绝初始化。当前未优化原Easel依赖，因此首次安装可能较慢、占用数GB，Ubuntu上的安装可用性须在目标服务器实际验收。

## 用户与模型配置

```bash
cd /opt/growth-copilot/releases/20261112
sudo -u growth .venv/bin/python -m easel.growth.private_auth --data-dir /var/lib/growth-copilot create-user reviewer01
sudoedit /etc/growth-copilot/app.env
```

密码在终端隐藏输入两次，至少12字符，不放入命令行、Git或聊天。为每名用户单独执行create-user。用户名3–40个字母/数字/`_.-`。

私有app.env中填写：
- `GROWTH_PRIVATE_DATA_DIR=/var/lib/growth-copilot`
- `GROWTH_PUBLIC_ORIGIN=https://实际域名`（无末尾斜杠，必须与Caddy一致）
- `GROWTH_LLM_BASE_URL`、`GROWTH_LLM_MODEL`、`GROWTH_LLM_API_KEY`：服务端模型配置。不要在终端打印文件。

不要上传本机.env。更改环境变量后重启growth-copilot。禁用用户：
```bash
sudo -u growth .venv/bin/python -m easel.growth.private_auth --data-dir /var/lib/growth-copilot disable-user reviewer01
```

## 启动与 HTTPS

```bash
sudo bash /opt/growth-copilot/releases/20261112/deploy/ubuntu24/activate.sh
```

activate切换前自动备份SQLite，启动一个worker、loopback绑定的生产服务；启动失败尝试恢复原代码链接。**不自动降级或覆盖数据库。**

按[Caddy官方安装说明](https://caddyserver.com/docs/install#debian-ubuntu-raspbian)安装免费Caddy。将`Caddyfile.example`的域名替换后加入`/etc/caddy/Caddyfile`，保留已有站点配置。没有静态目录映射，所有页面/数据经过应用认证。

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo systemctl enable --now caddy
sudo systemctl reload caddy
```

DNS必须已解析到服务器，80/443可达；不要添加错误AAAA记录。Caddy自动申请证书。参考[官方systemd运行说明](https://caddyserver.com/docs/running)。尚未配置域名时，不应宣称公网HTTPS已就绪。

## 上线验收 checklist

- [ ] Ubuntu依赖安装及pip check通过；应用仅监听127.0.0.1:7860。
- [ ] 新数据库无本地历史数据；两个独立用户已经创建。
- [ ] 公网HTTPS证书有效；未登录访问数据返回401；旧配置/文件/docs接口不开放。
- [ ] 用户A完成账号→诊断→研究→TOP3→草稿V1/V2；用户B看不到A的数据。
- [ ] 以B登录伪造A的账号/Research/Topic/Draft ID返回404，无模型调用或写入。
- [ ] 刷新、退出重登、服务重启后仍隔离且保留数据。
- [ ] 同一浏览器换登录用户后清除旧账号选择；访问`/logout`退出。
- [ ] 用户许可后再做真实模型验收，确认结构化结果、错误状态、证据与版本。
- [ ] 备份timer和快照恢复验证通过；管理员已保存异机副本。
- [ ] 账号密码通过私密渠道交付，Key不会出现在前端、Git或日志。

## 备份、恢复与维护

每日03:15附近定时调用SQLite在线backup API，支持写入期间的一致性快照；不用直接复制运行中的数据库/WAL。[SQLite官方说明](https://www.sqlite.org/backup.html)。画像是单独不可变导出副本，数据库为权威来源。

```bash
sudo systemctl start growth-backup.service
sudo systemctl list-timers growth-backup.timer
```

默认不自动删除备份，避免误删。每周检查磁盘并将最新加密备份复制到独立设备；同机备份不能防服务器损坏或被删除。备份包含敏感数据和会话哈希，不能公开或提交Git。

恢复先在**全新目录**操作：把快照复制为growth.sqlite3，校验`PRAGMA integrity_check`和`foreign_key_check`，检查用户/账号关联，再清除副本中的private_sessions撤销旧会话。画像归档如需恢复也解到新目录。不要覆盖正在使用的生产文件；正式切换数据目录前停机、再次备份并单独确认。恢复演练在本地临时库已测试；服务器演练仍待执行。

升级使用新release目录，重复prepare/provision（仅新用户）/activate；模型Key与数据目录始终不变。业务迁移/历史导入不在本次范围，遇到相关需求先停下确认。

## 已知限制

5–10人邀请试用的最小服务端隔离，不含公开注册、找回密码、邮件、计费或高级权限。SQLite和单worker适用于小规模验证，不保证高并发。会话8小时后需重登；多标签页切换登录身份应刷新/关闭旧标签页。暂不承诺生产SLA或模型效果。依赖未锁定，服务器首装后保存pip freeze作为部署记录。禁止把本地版入口直接绑定公网。
