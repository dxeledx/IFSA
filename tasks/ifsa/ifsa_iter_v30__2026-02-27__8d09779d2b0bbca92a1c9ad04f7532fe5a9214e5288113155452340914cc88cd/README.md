# IFSA v30 snapshot (CSP+LDA)

日期：2026-02-27  
代码快照：见同目录 `env.json` 的 `code_snapshot_sha256`

## 目标
- 修复 `bci_iv_2b/transductive_unlabeled_all` 里 **subject 1 的负迁移**（NTR 从 0.111 → 0），同时 `bci_iv_2a/transductive_unlabeled_all` 不回退。
- 硬约束保持：`R_*` 只来自 source，不读 target label。

## v30 改动（只改 IFSA 的 LOSO 控制策略）
新增一个“低分无需对齐 hold”规则（仅在 target-guided 且 safety 启用时生效）：
- 若 `score_target < safety_low_score_mult * tau_eff` → 直接 `hold_identity`（`gate_factor=0`）。
- 本轮取：`safety_low_score_mult = 0.85`。

对应代码：`/Users/jason/workspace/code/workspace/Reserch_experiment/EA++/src/eapp/eval/loso.py`

## 方法/配置
- 对照（control）：`ifsa_v29_track_scale_tau0p5_hold0p5_disc0p008`
- 新方法：`ifsa_v30_track_scale_tau0p5_hold0p5_disc0p008_low0p85`
  - 与 v29 唯一差异：`method.safety_low_score_mult: 0.85`

## 结果（acc_mean / NTR）
以 `results/tables/matrix__csp_lda__acc_mean.csv` 与 `matrix__csp_lda__neg_transfer_ratio.csv` 为准。

- **2a / transductive_unlabeled_all**
  - IFSA best：`0.509838`（best variant 仍为 v23；v30 与其持平，不回退）
- **2b / transductive_unlabeled_all**
  - IFSA best：`0.732832`，`NTR=0.0`
  - 对比 EA baseline：`0.728496`

## 关键证据（2b-trans 的 hold 是否命中 subject 1）
文件：
- `results/tables/bci_iv_2b__ifsa_v30_track_scale_tau0p5_hold0p5_disc0p008_low0p85__csp_lda__transductive_unlabeled_all.csv`

摘要：
- subject 1：`ifsa_safety_low_hold=1`，`ifsa_safety_gate_factor=0`，`acc=0.701389`（回退到 identity）
- subject 9：`ifsa_safety_low_hold=0`（未被误 hold）

## 确定性检查
- 在 RLserver-ex 复跑 `bci_iv_2b/trans`（`runtime.seed=43`，`runtime.results_dir=results_seedcheck_v30`）得到 per-subject 表与主结果 **完全一致**（max_abs_diff=0）。

## Baseline 参照
- baseline v2（冻结）：
  - `/Users/jason/workspace/code/workspace/Reserch_experiment/EA++/tasks/baselines/baseline_align_csp_lda_v2__2026-02-26__484bd4af1a217147295125f6d1da869ce4fb2fa9708cb34040384d84afdf1dfa/`

## 复现命令（RLserver-ex）
```bash
./scripts/remote/rl_sync.sh RLserver-ex
./scripts/remote/rl_setup.sh RLserver-ex
./scripts/remote/rl_run_ifsa_iter_v30_roundU.sh RLserver-ex
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
