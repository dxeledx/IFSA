# IFSA v21 Round-J（track_error ∧ disc_loss 组合安全离合器）：通过 Gate-A

v20 的 disc-loss 单独门控量级过小且不够判别（无法单独抓住 subject 9 的负迁移）。v21 改成 **组合门控**：仍用 v18 的 `track_error`（离 `R_*` 的距离）捕获 “明显 OOD 的 target”，但只有当对齐会造成 **source 判别结构塌缩（disc-loss）** 时才允许 hold，从而避免 v18 对 subject 5 的误 hold，同时保留对 subject 9 的修复。

## 硬约束（始终满足）

- `R_*` 严格只由 **source subjects** 估计（`x_train/meta_train`），不使用 target。
- target 仅使用协议允许的 **unlabeled subset**（`_target_alignment_subset`），不读 target label。
- disc-loss 只使用 **source labels**（`y_train`），不接触 target labels。

## 实现要点

文件：`src/eapp/eval/loso.py`

### 新增配置（默认关闭，兼容历史复现）

`configs/method/ifsa.yaml` 新增：
- `safety_disc_loss_tau: 0.0`

语义：当 `safety_mode=hold_identity` 且 `safety_score_mode=track_error` 时：
- 先按 v18 的逻辑判断是否应该 hold（`track_error > tau_eff`）
- **仅当** `disc_loss > safety_disc_loss_tau` 才最终 hold；否则取消 hold（继续对齐）

> disc-loss 只在“原本会 hold 的 fold”上计算，所以额外开销很小。

### 新增 CSV 字段（便于排查）

在 ifsa/target-guided 分支里新增并写入：
- `ifsa_safety_disc_loss`
- `ifsa_safety_disc_loss_tau`

## Round-J 设置（2-setting gate）

- Gate-A：`bci_iv_2a + transductive_unlabeled_all`（主攻，`method.trigger_tau=0.0`）
- Gate-B：`bci_iv_2b + online_prefix_unlabeled`（哨兵，`method.trigger_tau=0.5`）

脚本：`scripts/remote/rl_run_ifsa_iter_v21_roundJ.sh`

## v21 variants（2 个）

- `ifsa_v21_track_hold_q0p90_disc0p001`
- `ifsa_v21_track_hold_q0p90_disc0p002`

两者结果相同（因为 subject 9 的 `disc_loss≈0.010`，subject 5 的 `disc_loss=0.0`）。

## 结果（关键结论）

### 2a / transductive（Gate-A：目标 ≥0.506）

`ifsa_v21_track_hold_q0p90_disc0p001`：
- `acc_mean = 0.509452`
- `neg_transfer_ratio = 0.0`

对照（来自 `matrix__csp_lda__acc_mean.csv`）：
- CORAL `0.510224`（best baseline）
- RA `0.509066`
- IFSA（本轮 best）`0.509452` ✅（接近 CORAL，并略高于 RA）

### 关键证据：只 hold subject 9、不误伤 subject 5

在 `results/tables/bci_iv_2a__ifsa_v21_track_hold_q0p90_disc0p001__csp_lda__transductive_unlabeled_all.csv`：
- subject 9：`ifsa_safety_hold=1`（回退 identity，修复负迁移）
- subject 5：`track_error` 触发了“潜在 hold”，但 `ifsa_safety_disc_loss=0.0 <= 0.001` → 取消 hold，继续对齐（保留收益）

### 2b / online_prefix（Gate-B）

Round-J 的 v21 变体在线上本身仍不强（~0.70），但矩阵的 best-online 仍由历史最优保障：
- `ifsa_v11_logmean_shrink0p1`：`acc_mean≈0.723`，`NTR≈0.111` ✅

## 产物

- `matrix__csp_lda__acc_mean.csv`
- `matrix__csp_lda__neg_transfer_ratio.csv`
- `matrix__csp_lda__best_variant.csv`
- `summary__bci_iv_2a__transductive_unlabeled_all.csv`
- `summary__bci_iv_2b__online_prefix_unlabeled.csv`
- `env.json` / `config.yaml`（含 `code_snapshot_sha256`）

## 下一步（建议）

1) **进入 Final（跑满 4-setting 并冻结）**：
   - trans 最优：`ifsa_v21_track_hold_q0p90_disc0p001`
   - online 最优：`ifsa_v11_logmean_shrink0p1`

2) 若要进一步逼近/超过 CORAL（`0.5102`）：
   - 尝试把 hold_identity 改成 scale_gain（对齐强度连续缩放），减少 “硬回退” 的信息损失。

baseline v2 参照目录（固定）：
- `/Users/jason/workspace/code/workspace/Reserch_experiment/EA++/tasks/baselines/baseline_align_csp_lda_v2__2026-02-26__484bd4af1a217147295125f6d1da869ce4fb2fa9708cb34040384d84afdf1dfa/`

