# IFSA v18 Round-G（target-guided 安全离合器）：未达 Gate-A，但修复了关键负迁移

本轮目标：在 **target-guided IFSA（`target_beta>0`）** 中加入“安全离合器（hold/thrust）”，对疑似 OOD 的 target subject **回退到 identity** 或 **降低对齐强度**，以修复 `2a/transductive` 少数被试（尤其 subject 9）的负迁移。

## 硬约束（始终满足）

- `R_*` 严格只由 **source subjects** 估计（`x_train/meta_train`），不使用 target。
- target 只使用协议允许的 **unlabeled subset**（`_target_alignment_subset`），不读 target label。

## 本轮实现（代码改动）

文件：`src/eapp/eval/loso.py`（仅在 `method=ifsa` 且 `target_beta>0` 分支生效）

- 计算 target OOD 分数（无标签）：
  - `score_target = _ifsa_track_error_before_from_covs(covs_fit, cfg_ifsa, reference_cov=R_*)`
- 用 source subjects 估计阈值（source-only）：
  - `tau_source = quantile(score_source_subjects, safety_quantile)`
  - `tau_eff = safety_tau_mult * tau_source`
- gate：
  - `safety_mode=scale_gain`：`gate_factor = clamp(tau_eff / score_target, safety_gain_min, 1)`
  - `safety_mode=hold_identity`：若 `score_target > tau_eff` 则直接回退到 identity（`gate_factor=0`）
- 记录到 CSV（便于排查/论文解释）：
  - `ifsa_safety_gate_factor, ifsa_safety_hold, ifsa_safety_score_target, ifsa_safety_tau_source, ifsa_safety_tau_eff, ifsa_safety_quantile`

默认参数（不影响旧结果）：见 `configs/method/ifsa.yaml` 新增的 `safety_*` 字段。

## Round-G 设置（2-setting gate）

- Gate-A：`bci_iv_2a + transductive_unlabeled_all`（主攻，`method.trigger_tau=0.0`）
- Gate-B：`bci_iv_2b + online_prefix_unlabeled`（哨兵，`method.trigger_tau=0.5`）

脚本：`scripts/remote/rl_run_ifsa_iter_v18_roundG.sh`

## v18 variants（4 个）

- `ifsa_v18_ctrl`：复现 v13 backbone（无 safety）
- `ifsa_v18_safety_scale_q0p95`：软门控（scale gain）
- `ifsa_v18_safety_hold_q0p90`：硬门控（hold identity）
- `ifsa_v18_safety_hold_q0p95`：硬门控（hold identity）

## 结果（人话）

### Gate-A：2a / transductive（主攻）

| variant | acc_mean | NTR |
|---|---:|---:|
| ifsa_v18_safety_hold_q0p90 | 0.5046 | 0.000 |
| ifsa_v18_safety_hold_q0p95 | 0.5046 | 0.000 |
| ifsa_v18_ctrl | 0.5031 | 0.111 |
| ifsa_v18_safety_scale_q0p95 | 0.4998 | 0.111 |

- 结论：**安全离合器确实“救回了负迁移被试”**（subject 9），但总体只带来 **+0.0015** 的小幅提升，未达到 Gate-A（目标 ≥0.506）。
- 与最强 baseline（CORAL `0.5102` / RA `0.5091`）仍有差距（gap≈`0.0056`）。

**关键证据：hold 是否触发**

在 `bci_iv_2a__ifsa_v18_safety_hold_q0p95__csp_lda__transductive_unlabeled_all.csv` 中：
- subject 9：`ifsa_safety_hold=1`，并且 `acc` 回退到 `baseline_acc`（identity），从而消除负迁移。
- 但同时 subject 5 也触发了 hold（`ifsa_safety_hold=1`），导致该被试丢失了本来对齐能带来的增益，限制了总体提升。

### Gate-B：2b / online_prefix（哨兵）

本轮 v18 变体本身（target-guided）在 online-prefix 下并不强（~0.70 且 NTR 高），但**哨兵 gate 使用的是 “全体 ifsa 变体中的 best”**，因此：
- best-online 仍是历史最优：`ifsa_v11_logmean_shrink0p1`（`acc_mean=0.7230`, `NTR=0.111`）✅

## 产物

- `matrix__csp_lda__acc_mean.csv`
- `matrix__csp_lda__neg_transfer_ratio.csv`
- `matrix__csp_lda__best_variant.csv`
- `summary__bci_iv_2a__transductive_unlabeled_all.csv`
- `summary__bci_iv_2b__online_prefix_unlabeled.csv`
- `env.json` / `config.yaml`（含 `code_snapshot_sha256`）

## 下一步建议（v19，重点：换 OOD 指标）

v18 的 OOD 分数本质上是“**target 均值协方差离 R_* 的距离**”，它会把“确实需要对齐的被试”（如 subject 5）也误判为 OOD。

更合理的下一步是把 gate 的分数换成“**target 统计的稳定性（噪声/非平稳）**”，例如：

1) **split-half 稳定性分数（无标签）**
- 把 target subset 分成两半，分别求均值协方差 `M_t1, M_t2`
- `score = || logm( M_t1^{-1/2} M_t2 M_t1^{-1/2} ) ||_F`
- 阈值仍用 source subjects 的同款分数分位数（source-only）
- 直觉：如果 target 统计不稳定（噪声大/非平稳），就 hold；如果稳定但“离 reference 远”，反而更应该对齐（不 hold）。

2) **hold 只针对 transductive**
- online-prefix 继续用 v11（已经是 best-online），不要把 target-guided 引入 prefix 小样本场景。

