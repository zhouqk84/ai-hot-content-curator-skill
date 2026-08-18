---
name: ai-hot-content-curator
description: 为抖音 AI 小白账号发现、核验和筛选实时热点选题。用于用户要求热点追踪、AI 一人公司选题、候选话题评分或选题研究时；只输出选题依据与实测任务，不生成短视频脚本、口播稿或成品文案。
---

# AI 热点选题

## 边界

- 只完成热点发现、事实核验、评分和候选排序。
- 最终选题由用户决定。
- 不生成脚本、标题库、口播稿或成品内容。
- 不公开角色档案中的真实姓名、家庭信息、经营数据、亏损、侵权、品牌滥用或平台处罚经历。

## 工作流

1. 读取 `D:\Codex-Private\creator-profile.md`。文件不存在或无法读取时停止并询问路径；不得把档案复制进仓库或输出其敏感内容。
2. 在仓库根目录运行 `python scripts/collect_candidates.py`，记录终端返回的 `raw_candidates.json` 路径。缺少依赖时，说明用途并取得同意后安装 `scripts/requirements.txt`。
3. 读取 `resources/content_curator_sources.json`：
   - 使用 `discovery_sources` 获取初始候选；
   - 使用 `verification_domains` 寻找官方或原始来源；
   - 使用 `heat_queries` 检索中文传播信号，抖音优先；无法直接访问抖音时，使用可公开检索的中文平台信号并标注“替代信号”。
4. 对每个候选核对事件日期、原始出处和核心事实。淘汰无法定位原始来源、事实冲突或已失效的候选。
5. 结合角色档案评分，按总分排序，只保留 5 个候选。默认由 Codex 评分；仅在用户明确指定时调用可选后端。
6. 将结果写入原始候选同目录的 `selection.md`，并在对话中展示同一份内容；不要创建其他报告。

## 可选评分后端

调用外部后端前，先生成最多 20 条 `verified_candidates.json`。每条必须只含 `id`、`title`、`fact_summary`、`primary_sources`、`heat_signals`、`test_task`，不得包含角色档案原文或敏感信息。

- WorkBuddy：确认本机已安装并登录，运行 `python scripts/score_candidates.py verified_candidates.json --provider workbuddy`。可用 `WORKBUDDY_COMMAND` 指定可执行文件。
- 华为云：让用户自行设置 `HUAWEI_MAAS_ENDPOINT`、`HUAWEI_MAAS_MODEL`、`HUAWEI_MAAS_API_KEY`，不得索取或显示 Key；运行 `python scripts/score_candidates.py verified_candidates.json --provider huawei`。

后端结果只作为评分意见。校验失败时报告原因，不自动切换提供商，不绕过用户选择。

## 评分

总分 100：

- AI 小白实用价值：30
- 用户能否亲自测试：25
- AI 一人公司相关性：20
- 当前热度与时效：15
- 制作难度是否适合：10

出现虚假信息、夸大收益、隐私泄露、侵权或无法验证时直接淘汰，不进入评分。

## 输出

每个候选只包含：

1. 中性选题名称
2. 核心事实、事件日期和原始来源链接
3. 中文热度依据及链接；使用替代信号时明确标注
4. 五项分数与总分
5. 与账号定位的适配理由
6. 用户可亲自完成的最小实测任务
7. 建议形式：真人配音录屏、AI 配音或图文
8. 风险与不确定性

结尾只询问用户选择哪个候选，不替用户决定。
