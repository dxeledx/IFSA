# IFSA v20 Round-I（disc-loss 判别结构塌缩 safety）：未通过 Gate-A

本轮目标：在不读 target label、且 `R_*` 严格只来自 source 的约束下，用 **source 标签**构造一个“判别结构塌缩（disc-loss）”安全离合器，期望在 `bci_iv_2a/transductive` 上避免类似 subject 9 的负迁移，同时不误伤 subject 5。

## 硬约束（始终满足）

- `R_*` 严格只由 **source subjects** 估计（`x_train/meta_train`），不使用 target。
- target 仅使用协议允许的 **unlabeled subset**（`_target_alignment_subset`），不读 target label。

## 实现（新增 safety_score_mode=disc_loss）

文件：`src/eapp/eval/loso.py`

- 新增 `method.safety_score_mode: disc_loss`
- 编码：`ifsa_safety_score_mode` 里 `2=disc_loss`（`0=track_error`，`1=split_half`）
- disc separation（log-euclid，非 congruence-invariant）：
  - 对每个类 `k`：用 `mean_mode` 得到类均值协方差 `M_k`（arith 或 log-euclid）
  - 取 `L_k = logm(M_k)`
  - `disc = mean_{i<j} ||L_i - L_j||_F`
- disc-loss（fold-level）：
  - 先跑一遍 target-guided 的候选对齐（source→target；target 域仍保持 identity）
  - `disc_loss = max(0, 1 - disc_after / max(1e-12, disc_before))`
- 门控（只做 hold，v20 不支持 scale_gain）：
  - `tau_eff = safety_tau_mult`（绝对阈值）
  - `hold_identity`：若 `disc_loss > tau_eff` → `gate_factor=0` 回退 identity
- CSV 记录（沿用 v18/v19 字段）：
  - `ifsa_safety_gate_factor / hold / score_target / tau_eff / score_mode`

## Round-I 设置（2-setting gate）

- Gate-A：`bci_iv_2a + transductive_unlabeled_all`（主攻，`method.trigger_tau=0.0`）
- Gate-B：`bci_iv_2b + online_prefix_unlabeled`（哨兵，`method.trigger_tau=0.5`）

脚本：`scripts/remote/rl_run_ifsa_iter_v20_roundI.sh`

## v20 variants（4 个）

- `ifsa_v20_ctrl`：无 safety
- `ifsa_v20_disc_hold_tau0p05`：disc-loss + hold（`tau=0.05`）
- `ifsa_v20_disc_hold_tau0p10`：disc-loss + hold（`tau=0.10`）
- `ifsa_v20_disc_hold_tau0p15`：disc-loss + hold（`tau=0.15`）

## 结果（人话）

结论：disc-loss 的量级远小于预期（约 `0~0.013`），因此 `tau=0.05~0.15` **完全不会触发 hold**，整体表现与 v13 backbone（`ifsa_v13_tg_beta1_full`）一致，未超过 v18 的最优。

### 2a / transductive（Gate-A，目标 ≥0.506）

| variant | acc_mean | NTR |
|---|---:|---:|
| ifsa_v20_ctrl | 0.5031 | 0.111 |
| ifsa_v20_disc_hold_tau0p05 | 0.5031 | 0.111 |
| ifsa_v20_disc_hold_tau0p10 | 0.5031 | 0.111 |
| ifsa_v20_disc_hold_tau0p15 | 0.5031 | 0.111 |

- Gate-A 失败。
- 当前 `2a/trans` 的 best IFSA 仍为：`ifsa_v18_safety_hold_q0p90`（`acc_mean=0.50463`）
- 对照：best baseline 仍是 CORAL `0.51022` / RA `0.50907`（见 `matrix__csp_lda__acc_mean.csv`）

**关键证据：subject 9 未被 hold**

在 `results/tables/bci_iv_2a__ifsa_v20_disc_hold_tau0p10__csp_lda__transductive_unlabeled_all.csv`：
- subject 9：`disc_loss=0.01007 < tau=0.10` → `ifsa_safety_hold=0`，仍负迁移（`acc=0.5208 < identity=0.5781`）
- subject 5：`disc_loss=0.0` → 未 hold（`acc=0.3108 > identity=0.2674`）

### 2b / online_prefix（Gate-B）

v20 target-guided 变体在线上仍不强（~0.70）。不过矩阵的 best-online 仍由历史最优保障：
- `ifsa_v11_logmean_shrink0p1`：`acc_mean≈0.723`，`NTR≈0.111` ✅

## 产物

- `matrix__csp_lda__acc_mean.csv`
- `matrix__csp_lda__neg_transfer_ratio.csv`
- `matrix__csp_lda__best_variant.csv`
- `summary__bci_iv_2a__transductive_unlabeled_all.csv`
- `summary__bci_iv_2b__online_prefix_unlabeled.csv`
- `env.json` / `config.yaml`（含 `code_snapshot_sha256`）

## 下一步（v21）建议（按信息增益排序）

disc-loss 在当前定义下没能“单独识别 subject 9”。但它**确实把 subject 5 的 false positive（v18 里被误 hold）压到 0**，因此更可能有效的升级是“组合门控”：

1) **track_error ∧ disc_loss**（推荐）
   - 仍用 v18 的 `track_error` 做 OOD（能抓到 subject 9）
   - 但仅当 `disc_loss>0`（或 `>tiny_tau`）时才允许 hold（避免把 subject 5 这种“离得远但对齐有效”的情况误 hold）
   - 目标：只 hold subject 9，理论上 `2a/trans` 可接近 `0.509+`

2) **把 disc-loss 改成“更贴近分类器”的指标**
   - 在 source 上做一个轻量的 CSP feature margin / LDA 近似分数（仍不读 target label）

3) **disc-loss 改为 scale_gain（软门控）**
   - 避免像 subject 8 这种“disc_loss>0 但仍收益”的 fold 被硬回退

baseline v2 参照目录（固定）：
- `/Users/jason/workspace/code/workspace/Reserch_experiment/EA++/tasks/baselines/baseline_align_csp_lda_v2__2026-02-26__484bd4af1a217147295125f6d1da869ce4fb2fa9708cb34040384d84afdf1dfa/`

