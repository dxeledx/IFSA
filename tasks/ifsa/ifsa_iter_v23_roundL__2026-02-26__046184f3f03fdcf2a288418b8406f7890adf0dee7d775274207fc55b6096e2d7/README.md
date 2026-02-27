# IFSA v23（Round-L）冻结快照：`scale_gain + hard-hold + disc_loss guard`

日期：2026-02-26  
`code_snapshot_sha256`：`046184f3f03fdcf2a288418b8406f7890adf0dee7d775274207fc55b6096e2d7`（见同目录 `env.json`）

## 参照基线（不重跑）
`/Users/jason/workspace/code/workspace/Reserch_experiment/EA++/tasks/baselines/baseline_align_csp_lda_v2__2026-02-26__484bd4af1a217147295125f6d1da869ce4fb2fa9708cb34040384d84afdf1dfa/`

## 本轮结论（CSP+LDA）
以 `matrix__csp_lda__best_variant.csv` 为准：
- **2a / transductive_unlabeled_all**：best IFSA = `ifsa_v23_track_scale_tau0p5_hold0p5_disc0p001`  
  - `acc_mean = 0.509838`，`neg_transfer_ratio = 0.0`  
  - 证据：仅 subject 9 触发 `ifsa_safety_hold==1`（见同目录 `bci_iv_2a__ifsa_v23_track_scale_tau0p5_hold0p5_disc0p001__csp_lda__transductive_unlabeled_all.csv`）
  - 与 best baseline（CORAL `0.510224`）差距 `0.000386`
- **2b / online_prefix_unlabeled**：best IFSA 仍为 `ifsa_v11_logmean_shrink0p1`  
  - `acc_mean = 0.722982`，`neg_transfer_ratio = 0.111111`

## 方法改动摘要（相对 v21）
- 新增 `method.safety_hold_gate_threshold`（仅对 `safety_mode=scale_gain` 生效）：当 `gate_factor < threshold` 时强制回退到 identity（hard hold）。
- 将 v21 的 `disc_loss` 二级 guard 扩展到 `scale_gain`：只有当“候选对齐导致判别结构塌缩”时才允许降增益/hold，避免误伤（例如 subject 5）。

约束保持不变：
- `R_*` 严格只由 source 估计
- target 只用协议允许的 **unlabeled subset**（all / prefix），不读 target label

## 复现实用命令（RLserver-ex）
```bash
./scripts/remote/rl_sync.sh RLserver-ex
./scripts/remote/rl_setup.sh RLserver-ex

# Round-L（2-setting gate）
./scripts/remote/rl_run_ifsa_iter_v23_roundL.sh RLserver-ex
./scripts/remote/rl_fetch_results.sh RLserver-ex

# 汇总（本地）
./.venv/bin/python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all
./.venv/bin/python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=online_prefix_unlabeled

./.venv/bin/python -m eapp.report_matrix \
  --models csp_lda \
  --datasets bci_iv_2a,bci_iv_2b \
  --target-data-usages transductive_unlabeled_all,online_prefix_unlabeled \
  --methods identity,ea,ra,ra_riemann,coral,ifsa
```

## 确定性检查（结论）
在 `runtime.n_jobs=1` 且固定 `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1` 的情况下：
- `runtime.seed=0/1` 对 `acc_mean`（保留 6 位小数）结果一致（见 `results/tables/*repro*`）。

