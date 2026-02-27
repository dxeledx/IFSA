# IFSA v33 snapshot (CSP+LDA)

日期：2026-02-27  
代码快照：见同目录 `env.json` 的 `code_snapshot_sha256`

## 目标
- 继续主攻 `bci_iv_2a/transductive_unlabeled_all`：在 v32 已经超过 CORAL 的基础上，进一步消除“非必要 scale”（尤其 subject 8），以稳定拉开差距。
- 约束保持：`R_*` 严格只用 source（LOSO 的 `x_train/meta_train`），不读 target label；target 只用协议允许的 unlabeled subset。

## v33 相对 v32 的唯一差异（仍为 Euclid-thrust）
v33 基于 v32（`thrust_mode=euclid`）不改算法，只调 safety 参数让 gate_factor 更容易到 1：
- `safety_tau_mult: 0.5 -> 0.7`
- `safety_hold_gate_threshold: 0.5 -> 0.6`

对应实验 config：
- v32：`ifsa_v32_euclid_thrust_track_scale_tau0p5_hold0p5_disc0p001`
- v33：`ifsa_v33_euclid_thrust_track_scale_tau0p7_hold0p6_disc0p001`

## 结果（acc_mean / NTR）
以本目录的矩阵文件为准：
- `matrix__csp_lda__acc_mean.csv`
- `matrix__csp_lda__neg_transfer_ratio.csv`
- `matrix__csp_lda__best_variant.csv`

关键结论：
- **2a / transductive_unlabeled_all**
  - CORAL：`0.510224`
  - IFSA(v33)：`0.514082`，`NTR=0.0`
- **2b / transductive_unlabeled_all**
  - best IFSA 仍为 v30：`0.732832`，`NTR=0.0`

## 关键证据：v33 消除 subject 8 的 scale，保留 subject 9 的 hold
文件：
- `results/tables/bci_iv_2a__ifsa_v33_euclid_thrust_track_scale_tau0p7_hold0p6_disc0p001__csp_lda__transductive_unlabeled_all.csv`
- `results/tables/bci_iv_2a__ifsa_v32_euclid_thrust_track_scale_tau0p5_hold0p5_disc0p001__csp_lda__transductive_unlabeled_all.csv`

摘要（v33）：
- subject 8：`ifsa_safety_gate_factor=1.0`，`ifsa_safety_hold=0`，acc 从 `0.656250 -> 0.671875`（+0.015625）
- subject 9：`ifsa_safety_hold=1`（仍 hold），acc 保持 `0.578125`
- 对比 CORAL：subjects 1–8 **完全一致**，仅 subject 9 通过 hold 获得 `+0.034722` 增益（因此 `acc_mean +0.003858`）

## Baseline 参照
- baseline v2（冻结）：
  - `/Users/jason/workspace/code/workspace/Reserch_experiment/EA++/tasks/baselines/baseline_align_csp_lda_v2__2026-02-26__484bd4af1a217147295125f6d1da869ce4fb2fa9708cb34040384d84afdf1dfa/`

## 复现命令（RLserver-ex）
```bash
./scripts/remote/rl_sync.sh RLserver-ex
./scripts/remote/rl_setup.sh RLserver-ex
./scripts/remote/rl_run_ifsa_iter_v33_roundX.sh RLserver-ex
./scripts/remote/rl_fetch_results.sh RLserver-ex

# 生成 4-setting summaries + matrix（在远程执行）
ssh -o BatchMode=yes RLserver-ex "cd /home/wjx/workspace/code/workspace/Reserch_experiment/EA++ && . .venv/bin/activate \
  && python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all \
  && python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=transductive_unlabeled_all \
  && python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=online_prefix_unlabeled \
  && python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=online_prefix_unlabeled \
  && python -m eapp.report_matrix --models csp_lda --datasets bci_iv_2a,bci_iv_2b \
       --target-data-usages transductive_unlabeled_all,online_prefix_unlabeled \
       --methods identity,ea,ra,ra_riemann,coral,ifsa"
```

