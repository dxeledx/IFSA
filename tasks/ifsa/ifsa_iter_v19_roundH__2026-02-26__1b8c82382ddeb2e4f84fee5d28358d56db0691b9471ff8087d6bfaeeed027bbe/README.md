# IFSA v19 Round-H（split-half 稳定性 safety score）：未通过 Gate-A

本轮目标：把 v18 的 safety 分数从“离 `R_*` 的距离（track_error）”替换为“**split-half 统计稳定性**”，希望避免误把“离得远但应当对齐”的被试（如 subject 5）判成 OOD，同时仍能修复 subject 9 的负迁移。

## 硬约束（始终满足）

- `R_*` 严格只由 **source subjects** 估计（`x_train/meta_train`），不使用 target。
- target 仅使用协议允许的 **unlabeled subset**（`_target_alignment_subset`），不读 target label。

## 本轮实现（新增开关）

文件：`src/eapp/eval/loso.py`

- 新增 `method.safety_score_mode: track_error | split_half`
  - `track_error`：v18 原逻辑（距离分数）
  - `split_half`：把 target subset 的协方差序列一分为二，分别算均值协方差 `M1/M2`，分数为  
    `|| logm( M1^{-1/2} M2 M1^{-1/2} ) ||_F`
- 记录到 CSV：
  - `ifsa_safety_score_mode`（0=track_error, 1=split_half）
  - 复用 v18 的其它安全阀字段：`ifsa_safety_gate_factor/hold/score_target/tau_*`

默认值（不影响旧结果）：`configs/method/ifsa.yaml` 新增 `safety_score_mode: track_error`。

## Round-H 设置（2-setting gate）

- Gate-A：`bci_iv_2a + transductive_unlabeled_all`（主攻，`method.trigger_tau=0.0`）
- Gate-B：`bci_iv_2b + online_prefix_unlabeled`（哨兵，`method.trigger_tau=0.5`）

脚本：`scripts/remote/rl_run_ifsa_iter_v19_roundH.sh`

## v19 variants（4 个）

- `ifsa_v19_ctrl`：无 safety
- `ifsa_v19_split_hold_q0p95`：split-half + hold（q=0.95）
- `ifsa_v19_split_hold_q0p90`：split-half + hold（q=0.90）
- `ifsa_v19_split_scale_q0p95`：split-half + scale gain（q=0.95）

## 结果（人话）

结论：**split-half 稳定性分数无法识别 subject 9 的负迁移**，反而对 subject 2（以及 q0.90 时的 subject 5）触发了 hold/降增益，导致整体更差。

### 2a / transductive（主攻）

| variant | acc_mean | NTR |
|---|---:|---:|
| ifsa_v19_ctrl | 0.5031 | 0.111 |
| ifsa_v19_split_scale_q0p95 | 0.5017 | 0.111 |
| ifsa_v19_split_hold_q0p95 | 0.4983 | 0.111 |
| ifsa_v19_split_hold_q0p90 | 0.4934 | 0.111 |

- Gate-A（目标 ≥0.506）失败。
- 对照：最强 baseline 仍是 CORAL `0.5102` / RA `0.5091`（见 `matrix__csp_lda__acc_mean.csv`）。

**关键证据：subject 9 没有被 hold**

在 `bci_iv_2a__ifsa_v19_split_hold_q0p95__csp_lda__transductive_unlabeled_all.csv` 中：
- subject 9：`ifsa_safety_hold=0`，仍然负迁移（`acc=0.5208 < identity=0.5781`）
- 反而 subject 2 被 hold（`ifsa_safety_hold=1`），直接回退到 identity（`0.2639`）

### 2b / online_prefix（哨兵）

v19 变体本身在 online-prefix 仍不强（~0.70）。不过“哨兵门槛”看的是矩阵里 ifsa 的 best-online：
- best-online 仍为历史 `ifsa_v11_logmean_shrink0p1`（`acc_mean≈0.723`, `NTR≈0.111`）✅

## 产物

- `matrix__csp_lda__acc_mean.csv`
- `matrix__csp_lda__neg_transfer_ratio.csv`
- `matrix__csp_lda__best_variant.csv`
- `summary__bci_iv_2a__transductive_unlabeled_all.csv`
- `summary__bci_iv_2b__online_prefix_unlabeled.csv`
- `env.json` / `config.yaml`（含 `code_snapshot_sha256`）

## 下一步（v20）建议：用“可判别结构”做安全阀（仍不读 target label）

本轮失败说明：subject 9 的负迁移 **不是因为 target 统计不稳定**，而是“对齐到 target mean cov 的方向本身会伤到分类器”。

下一步更可能有效的是：在 target-guided 求出 `A` 之后，用 **source 标签** 做一个“判别结构保真”检查（不涉及 target label）：

- 用 source 数据计算各类的协方差均值（或 tangent 特征的类中心）
- 看对齐后（`A * cov * A^T`）类间距离是否被显著压缩
- 若压缩过强，则对该 target subject 降低 `lambda_track` 或直接回退 identity

这样才能区分：
- “离得远但对齐后仍保留判别结构”（应该对齐，例如 subject 5）
- “离得远且对齐会压扁判别结构”（应该 hold，例如 subject 9）

