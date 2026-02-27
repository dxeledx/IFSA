# PRD：跨被试 EEG 数据对齐研究 Infra（EA++ / TSA-SS，CPU 优先，RLserver-ex 运行）

> 本 PRD 为本仓库的“研究基础设施（infra）”实现规格，目标是支撑可复现基准 + 快速迭代新方法。

## 1. Introduction / Overview

在当前仓库中搭建一套“可复现基准优先”的研究基础设施（infra），用于跨被试（LOSO）EEG 数据对齐研究，支持快速迭代两条主线新方法：

- **EA++**：在 EA 基础上加入谱稳定/控制能量约束/可选闭环迭代更新
- **TSA-SS**：在 TSA 框架下引入稳定子空间锁定（先做最小可用版本）

Infra 的核心价值：**一键跑通标准协议 + 严格防泄漏 + 自动产出论文级表图 + 远程 CPU 服务器可稳定批量跑实验**。

## 2. Goals（可量化）

- **G1 一键复现**：单命令跑通指定数据集/协议/方法组合，输出结果表、图与统计检验。
- **G2 快速迭代**：新增一种对齐方法（或消融开关）不需要改动评估框架，只需新增/修改少量模块与配置。
- **G3 严谨防泄漏**：目标域（target subject）数据使用方式（无标注/少标注/在线前缀）在配置中显式声明，并在代码中强约束。
- **G4 CPU 友好**：默认路径在 CPU 上可运行（缓存、并行、数值稳定），远程 RLserver-ex 能稳定跑批。
- **G5 论文产出友好**：自动导出可直接进入论文的 CSV 表格、统计检验结果与图。

## 3. Scope（MVP）

### 数据集

- BCI Competition IV 2a（MOABB：`BNCI2014_001`）
- BCI Competition IV 2b（MOABB：`BNCI2014_004`）
- PhysioNet eegmmidb（MOABB：`PhysionetMI`）

### 协议

- LOSO（leave-one-subject-out）为第一优先
- 预留跨会话接口（本版本不强制完成）

### 方法与基线

- 对齐：`identity`（不对齐）、`EA`、`RA`、`TSA`（MVP）、`EA++`、`TSA-SS`（MVP）
- 模型：`CSP+LDA`、`MDM`（可选：切空间 + LDA）

### 远程运行

- 目标服务器：`RLserver-ex`（CPU-only）
- 标准流程：`rsync` 同步代码 → `tmux` 远程跑实验 → 拉回 tables/figures/logs

## 4. Non-Goals

- 不做：深度网络大规模训练、AutoML sweep、Web UI、Slurm 等作业调度

## 5. Acceptance Criteria（验收要点）

- `python -m eapp.run experiment=smoke` 在本地与远程可跑通（首次会下载数据）
- 输出 `results/tables/*.csv`、`results/figures/*.png`
- 在 `protocol.target_data_usage=*unlabeled*` 模式下，代码路径不允许访问 target labels
