# IFSA v23（Final）冻结快照：4-setting 汇总 + 基线对照矩阵

日期：2026-02-27  
`code_snapshot_sha256`：`43c80dea6364ac09e6f75eb169126efde00d634fc61b040d0c23f02cd3966660`（见同目录 `env.json`）

## 参照基线（CSP+LDA，对齐 baselines v2）
`/Users/jason/workspace/code/workspace/Reserch_experiment/EA++/tasks/baselines/baseline_align_csp_lda_v2__2026-02-26__484bd4af1a217147295125f6d1da869ce4fb2fa9708cb34040384d84afdf1dfa/`

## 矩阵结论（CSP+LDA）
以 `matrix__csp_lda__best_variant.csv` 为准：
- `bci_iv_2a / transductive_unlabeled_all`：`ifsa_v23_track_scale_tau0p5_hold0p5_disc0p001`（`acc_mean=0.509838`，`NTR=0.0`）
  - 仅 subject 9 触发 hold（见同目录 `bci_iv_2a__ifsa_v23_track_scale_tau0p5_hold0p5_disc0p001__csp_lda__transductive_unlabeled_all.csv`）
  - 与 CORAL baseline（`0.510224`）差距 `0.000386`
- `bci_iv_2a / online_prefix_unlabeled`：`ifsa_v21_track_hold_q0p90_disc0p001`
- `bci_iv_2b / transductive_unlabeled_all`：`ifsa_v13_tg_beta1_full`
- `bci_iv_2b / online_prefix_unlabeled`：`ifsa_v11_logmean_shrink0p1`

## v23 方法改动摘要（相对 v21）
- `safety_mode=scale_gain` 下新增 `method.safety_hold_gate_threshold`：当 `gate_factor < threshold` 时强制 hard-hold（回退 identity），用于“极端 OOD”被试（如 subject 9）。
- `disc_loss` 二级 guard 同时作用于 `scale_gain`：避免仅凭 track_error 误伤（如 subject 5）。

约束保持不变：
- `R_*` 严格只由 source 估计
- target 只用协议允许的 **unlabeled subset**（all / prefix），不读 target label

## 复现命令（RLserver-ex）
```bash
./scripts/remote/rl_sync.sh RLserver-ex
./scripts/remote/rl_setup.sh RLserver-ex

# Round-L（2-setting gate）
./scripts/remote/rl_run_ifsa_iter_v23_roundL.sh RLserver-ex

# Final：补齐缺失 setting（best_trans=v23 + best_online=v11）
./scripts/remote/rl_run_ifsa_iter_v23_final_missing.sh RLserver-ex

./scripts/remote/rl_fetch_results.sh RLserver-ex

./.venv/bin/python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all
./.venv/bin/python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=online_prefix_unlabeled
./.venv/bin/python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=transductive_unlabeled_all
./.venv/bin/python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=online_prefix_unlabeled

./.venv/bin/python -m eapp.report_matrix \
  --models csp_lda \
  --datasets bci_iv_2a,bci_iv_2b \
  --target-data-usages transductive_unlabeled_all,online_prefix_unlabeled \
  --methods identity,ea,ra,ra_riemann,coral,ifsa
```

## 确定性检查（结论）
在 `runtime.n_jobs=1` 且固定 `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1` 的情况下：
- `runtime.seed=0/1` 对 `acc_mean`（6 位小数）结果一致（见 `results/tables/*repro*`）。

