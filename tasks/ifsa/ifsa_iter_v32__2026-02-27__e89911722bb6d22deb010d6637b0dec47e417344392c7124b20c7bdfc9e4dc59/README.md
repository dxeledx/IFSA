# IFSA v32 snapshot (CSP+LDA)

日期：2026-02-27  
代码快照：见同目录 `env.json` 的 `code_snapshot_sha256`

## 目标
- 主攻 `bci_iv_2a/transductive_unlabeled_all`：让 IFSA **追平/超越 CORAL**，且 `neg_transfer_ratio=0`。
- 约束保持：`R_*` 严格只用 source（LOSO 的 `x_train/meta_train`），不读 target label；target 只用协议允许的 unlabeled subset。

## v32 创新点：`thrust_mode=euclid`（允许非对称 A）
背景：旧 IFSA thrust 强制 `A` 为对称 SPD（等价于约束 `A M A = desired`），会丢掉“旋转/非对称”自由度；而 CORAL/RA 等方法隐含使用更一般的 congruence 形式（`A M A^T`）。

v32 在 IFSA 内新增 thrust 解法族：
- `thrust_mode=spd`（默认/旧）：保持旧实现不变（`A` 对称 SPD，log-domain 插值）。
- `thrust_mode=euclid`（v32）：闭式解允许 `A` 非对称，满足
  - `A * mean_cov * A^T = desired`
  - `A_full = desired^{1/2} * mean_cov^{-1/2}`
  - 插值改为欧式：`A_new = (1-gain_eff)I + gain_eff*A_full`（避免对非对称矩阵做 `logm`）。

对应代码：
- `/Users/jason/workspace/code/workspace/Reserch_experiment/EA++/src/eapp/alignment/ifsa.py`
- `/Users/jason/workspace/code/workspace/Reserch_experiment/EA++/src/eapp/eval/loso.py`
- `/Users/jason/workspace/code/workspace/Reserch_experiment/EA++/configs/method/ifsa.yaml`

## 方法/配置
实验配置：
- `ifsa_v32_euclid_thrust_track_scale_tau0p5_hold0p5_disc0p001`
  - 基于 v23（`ifsa_v23_track_scale_tau0p5_hold0p5_disc0p001`）
  - **唯一差异**：`method.thrust_mode: euclid`

远程跑批脚本（2-setting gate + seedcheck）：
- `/Users/jason/workspace/code/workspace/Reserch_experiment/EA++/scripts/remote/rl_run_ifsa_iter_v32_roundW.sh`

## 结果（acc_mean / NTR）
以本目录的矩阵文件为准：
- `matrix__csp_lda__acc_mean.csv`
- `matrix__csp_lda__neg_transfer_ratio.csv`
- `matrix__csp_lda__best_variant.csv`

关键结论：
- **2a / transductive_unlabeled_all**
  - CORAL：`0.510224`
  - IFSA(v32)：`0.512346`，`NTR=0.0`（通过 Gate-A）
- **2b / transductive_unlabeled_all**
  - best IFSA 仍为 v30：`0.732832`，`NTR=0.0`（满足 Gate-B）

## 关键证据（subject 9 的 hold + 与 CORAL 的差异来源）
文件：
- `results/tables/bci_iv_2a__ifsa_v32_euclid_thrust_track_scale_tau0p5_hold0p5_disc0p001__csp_lda__transductive_unlabeled_all.csv`
- `results/tables/bci_iv_2a__coral__csp_lda__transductive_unlabeled_all.csv`

摘要（v32 - coral 的 per-subject acc 差异）：
- subject 9：`+0.034722`（v32 触发 hold，负迁移被修复）
- subject 8：`-0.015625`（v32 仍被 scale，gate_factor≈0.740）
- subjects 1–7：与 CORAL **完全一致**

## 确定性（seed）检查
在 RLserver-ex 上复跑 `2a/trans`（`runtime.seed=43`，`runtime.results_dir=results_seedcheck_v32`）：
- per-subject `acc` **完全一致**（max_abs_diff=0）。

## Baseline 参照
- baseline v2（冻结）：
  - `/Users/jason/workspace/code/workspace/Reserch_experiment/EA++/tasks/baselines/baseline_align_csp_lda_v2__2026-02-26__484bd4af1a217147295125f6d1da869ce4fb2fa9708cb34040384d84afdf1dfa/`

## 复现命令（RLserver-ex）
```bash
./scripts/remote/rl_sync.sh RLserver-ex
./scripts/remote/rl_setup.sh RLserver-ex
./scripts/remote/rl_run_ifsa_iter_v32_roundW.sh RLserver-ex
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

