# IFSA v17 Round-F（desired 正则）：未通过 Gate

本轮目标：在 **target-guided IFSA（`target_beta>0`）** 中，对期望参考系 `desired` 做正则，降低 target 均值协方差噪声带来的负迁移（重点修复 `2a/trans` 的少数负迁移被试，如 subject 9）。

## 硬约束（始终满足）

- `R_*` 严格只由 **source subjects** 估计（`x_train/meta_train`），不使用 target。
- target 只使用协议允许的 **unlabeled subset**（`_target_alignment_subset`），不读 target label。

## 本轮实现（新增开关）

在 `src/eapp/alignment/ifsa.py` 的 target-guided 分支（`target_beta>0`）中：

- trace shrink（各向同性）：
  - `desired <- (1-α) desired + α * (tr(desired)/C) I`
  - 参数：`method.desired_shrink_alpha ∈ [0,0.3]`
- log-spectrum shrink（保方向，压特征值离散度）：
  - 复用 `_shrink_log_spectrum(eigh_sym(desired), strength)`
  - 参数：`method.desired_log_spec_shrink ∈ [0,1]`

默认值均为 `0.0`，不影响既有结果。

## Round-F 运行设置（2-setting gate）

- `bci_iv_2a` + `transductive_unlabeled_all`（主攻，`method.trigger_tau=0.0`）
- `bci_iv_2b` + `online_prefix_unlabeled`（哨兵，`method.trigger_tau=0.5`）

脚本：`scripts/remote/rl_run_ifsa_iter_v17_roundF.sh`

## v17 variants（6 个）

- `ifsa_v17_ctrl`（复现 v13 backbone）
- `ifsa_v17_desired_shrink0p05`
- `ifsa_v17_desired_shrink0p10`
- `ifsa_v17_desired_shrink0p20`
- `ifsa_v17_desired_logspec0p20`
- `ifsa_v17_desired_shrink0p10_logspec0p20`

## 结果（人话）

结论：**desired 正则没有提升 `2a/trans`，且大多显著恶化**；因此 v17 未通过 Gate-A（`acc_mean >= 0.506`）。

### 2a / transductive（主攻）

| variant | acc_mean | NTR |
|---|---:|---:|
| ifsa_v17_ctrl | 0.5031 | 0.111 |
| ifsa_v17_desired_logspec0p20 | 0.4583 | 0.222 |
| ifsa_v17_desired_shrink0p10_logspec0p20 | 0.3914 | 0.778 |
| ifsa_v17_desired_shrink0p05 | 0.3754 | 0.778 |
| ifsa_v17_desired_shrink0p10 | 0.3495 | 0.889 |
| ifsa_v17_desired_shrink0p20 | 0.3274 | 0.889 |

> 当前 best-trans 仍是 `ifsa_v13_tg_beta1_full`（`0.5031`，未变化）。

### 2b / online_prefix（哨兵）

v17 变体多数在 `0.70~0.714`，仍低于当前 best-online：
`ifsa_v11_logmean_shrink0p1`（`0.7230`，且 `NTR=0.111`）。

## 产物

- `matrix__csp_lda__acc_mean.csv`
- `matrix__csp_lda__neg_transfer_ratio.csv`
- `matrix__csp_lda__best_variant.csv`
- `summary__bci_iv_2a__transductive_unlabeled_all.csv`
- `summary__bci_iv_2b__online_prefix_unlabeled.csv`
- `env.json` / `config.yaml`（含 `code_snapshot_sha256`）

## 下一步（v18）建议（按信息增益排序）

v17 的结果说明：**直接把 target 均值协方差 “拉回更圆” 会破坏它携带的有用方向信息**，导致整体崩盘。

更可取的下一步是“只在明显异常的 fold/subject 上做安全阀”，而不是全局 shrink：

1) **fold-level 安全阀（无标签）**：仅对 “疑似异常的 target” 降低对齐强度或回退到 identity。
   - 异常判据仅用 unlabeled：例如 target `log-eig` 方差、`track_error_before`、或 target mean cov 的 condition number 超过 source 分布的分位数阈值。
2) **只对 target_mean_cov 做轻度 trace-norm / shrink（且仅在 online-prefix）**：
   - 让 transductive 仍保持 v13 的强对齐口径，online-prefix 再做稳健化（避免小样本噪声过拟合）。

