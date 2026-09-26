# 运营报表自动整理与交付工具

[![Tests](https://github.com/jaden20030518-lgtm/ops-report-delivery/actions/workflows/test.yml/badge.svg)](https://github.com/jaden20030518-lgtm/ops-report-delivery/actions/workflows/test.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)

把已有的短视频运营导出表，整理成固定九列的数据源；逐行核验后再交付，并保存可追溯的执行记录。

这是一个从实际运营任务中提取的作品项目。重点是把业务要求变成可执行、可检查的规则：**数据不被误删、长 ID 不丢精度、格式不被美化改写、上传结果不确定时不冒报成功。** 使用 Codex 辅助开发，业务口径、验收标准和方案迭代来自实际操作反馈。

> 仓库只包含通用代码和人工构造的合成数据。默认演示不联网、不需要公司账号，也不读取浏览器登录态。它不会自动下载任何公司的后台报表。

## 先跑一次

需要 Python 3.11 或更高版本。安装依赖需要网络；安装后的演示完全离线。

```bash
git clone https://github.com/jaden20030518-lgtm/ops-report-delivery.git
cd ops-report-delivery
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
report-delivery demo
```

Windows 可使用 `py -m venv .venv`，然后在 PowerShell 运行 `.venv\Scripts\Activate.ps1`。

演示会创建一份三行模拟表，其中包含长 ID、前导零、全零指标行和重复视频 ID。完成后返回：

```json
{
  "status": "demo_completed",
  "rows": 3,
  "zero_rows_retained": 1,
  "network_accessed": false,
  "delivery_method": "local copy with SHA256 verification"
}
```

查看 `demo-output/run/202601短视频数据源.xlsx`、`demo-output/run/manifest.json` 和 `demo-output/local-delivery/`。本地交付副本会核对 SHA256；演示结果不会被标记为真实 NAS 上传成功。重复运行会复用相同结果。

## 流程与关键判断

```mermaid
flowchart LR
    A[已有导出报表] --> B[检查表头和日期]
    B --> C[备份原始文件]
    C --> D[九列转换]
    D --> E[重新读取并逐行核验]
    E --> F{文件已核验?}
    F -->|是| G[预览交付目标]
    G --> H[明确执行上传]
    H --> I[回读路径 大小 修改时间]
    I --> J[记录 uploaded]
    F -->|否| K[停止 保留现场]
```

- **数据口径固定。** 最终列为视频ID、视频发布时间、抖音号ID、发布次数、累计播放次数、累计直接成交金额、累计直接成交券数、累计直接核销金额、累计直接核销券数。发布次数每行填数值 1。
- **保留原始数据行。** 不汇总、不排序、不去重，不再次删除全零行。去掉视频标题、统计日期和附加指标的是整理版，原始备份完整保留。
- **区分标识符与数值。** ID 保留为文本；源文件中超过 15 位的数值型 ID、浮点 ID、公式、空报表、缺失或重复的必需列会被拒绝。
- **格式属于验收条件。** A:I 列宽为 18，默认行高 16.8，General 格式；普通字体 Calibri 11，D1 为宋体-简 11。不自动加宽、加粗表头或添加装饰。
- **日期按业务窗口计算。** 北京时间昨天所属月份的 1 日至昨天。每月 1 日处理上月整月，跨年和闰年同样处理。
- **执行记录控制后续动作。** 只有正式 `verified` 且 `ready_for_upload=true` 的文件可发送。哈希变化会阻止复用；并发运行会被锁拦截；不确定的上传会留下尝试记录，避免盲目覆盖。

## 使用自己的报表

输入必须只有一个工作表，且包含最终列中除“发布次数”之外的八列，以及“视频标题”“统计日期”。统计日期必须明确包含本次起止日期；发布时间必须落在该范围内。Excel 原始导出的后台筛选口径需由操作者事先确认，本工具不能仅凭表格证明后台筛选选项。

```bash
# 计算实际日期范围；--at 仅用于展示日期规则
report-delivery plan
report-delivery plan --at 2026-10-01T10:00:00+08:00

# 日期填写为实际报表范围，每次使用独立输出目录
report-delivery process /path/to/export.xlsx \
  --start 2026-01-01 --end 2026-01-03 --out outputs/example-run

# 独立重读数据、格式和文件哈希
report-delivery verify outputs/example-run/manifest.json
```

`process` 不登录网站，也不调度每日任务。原始 `.xlsx`、输出、日志和本地配置均被 `.gitignore` 排除。

## 可选：上传到自己的 Synology NAS

先复制配置：

```bash
cp examples/nas.example.json nas.local.json
```

在 `nas.local.json` 填写自己的 HTTPS 服务地址和已存在的目标目录。公司地址、账号密码都不应提交到仓库。示例域名 `nas.example.com` 只是占位符。

```bash
# 默认只做本地核验并显示目标，不登录、不上传
report-delivery upload outputs/example-run/manifest.json --config nas.local.json

# 确认目标目录和覆盖授权后显式执行；交互输入账号及不回显的密码
report-delivery upload outputs/example-run/manifest.json --config nas.local.json --execute
```

自动化环境可通过秘密管理功能注入 `REPORT_NAS_ACCOUNT` 与 `REPORT_NAS_PASSWORD`，不要把真实值写进命令示例或配置。自建 CA 可将 `ca_bundle` 配置为本机证书文件路径；不支持关闭 TLS 校验。验证码、二次验证和特殊登录机制不在当前适配范围内。

目标文件名由报表结束月份计算。同名文件会覆盖，不自动新建目录、不删除其他文件。成功条件为 API 返回成功且回读目标路径、字节数、新修改时间均符合预期；**没有校验远端文件哈希**。演示记录不能走真实上传通道。

若上传中断或回读失败，`upload-attempt.json` 保留当次尝试，状态不会被改成 `uploaded`。先人工检查远端，不能为了重试而直接清空记录。详细状态边界见[设计与取舍](docs/design.md)。

## 脚本与 Skill 的分工

`src/report_delivery/` 执行日期计算、表格处理、核验与交付。`skills/report-delivery/` 告诉 Agent 何时调用、怎样理解结果、何时停止；skill 不代替程序的验证。

先安装本项目，再按所用 Agent 的规范安装或读取 `skills/report-delivery/SKILL.md`。不安装 skill 也可以独立运行所有命令。

```text
src/report_delivery/       # 可独立运行的 Python 核心及 CLI
tests/                     # 数据保真、状态门槛、上传协议与失败场景
skills/report-delivery/     # Agent 调用指引
examples/                  # 合成数据说明、虚构 NAS 配置
docs/                      # 设计、验证边界与面试讲解
.github/workflows/         # 自动执行测试和离线演示
```

## 验证与项目边界

```bash
python -m unittest discover -s tests -v
```

测试涵盖日期边界、全零和重复行保留、长 ID、数据及样式篡改、错误统计周期、模拟数据禁止上传、请求协议、分页回读、SSL 错误脱敏、不确定上传与重复交付。

当前公开版验证了离线演示和 NAS 协议替身测试，**没有使用任何真实公司账号重新验收此公开版本**。原始私有流程曾处理数万行级报表并完成接口上传，也遇到过页面控件超时与 SSL 连接失败；这些经验促成了本项目的边界和失败处理，不能当作公开版已经连续稳定无人值守的证明。详见[验证记录](docs/validation.md)。

求职展示时，可从[项目讲解](docs/interview.md)说明业务问题、本人贡献、AI 协作方式和一次失败后的取舍。这里不声称已节省某个百分比或取得未经测量的业务收益。

## 技术依据

表格读写使用 [openpyxl](https://openpyxl.readthedocs.io/en/stable/styles.html)。可选上传适配器依据 [Synology File Station API Guide](https://global.download.synology.com/download/Document/Software/DeveloperGuide/Package/FileStation/All/enu/Synology_File_Station_API_Guide.pdf) 实现；接口实际可用性取决于使用者的服务器版本、权限和网络。

MIT License；依赖各自遵循其许可证。
