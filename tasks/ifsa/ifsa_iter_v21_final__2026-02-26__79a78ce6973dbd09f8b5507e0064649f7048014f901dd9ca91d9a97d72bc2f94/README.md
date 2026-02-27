# IFSA v21 Final（全 4-setting 汇总 + 冻结快照）

本快照包含：
- IFSA v21 的核心改动（target-guided 下的组合安全离合器：`track_error ∧ disc_loss`）
- 在 `bci_iv_2a/bci_iv_2b × transductive/online_prefix × CSP+LDA` 的 **4-setting** 上，生成的最终 summary 与矩阵（含 baseline 对齐法）

## 关键硬约束（始终满足）

- `R_*` 严格只由 **source subjects** 估计（`x_train/meta_train`），不使用 target。
- target 仅使用协议允许的 **unlabeled subset**（`_target_alignment_subset`），不读 target label。
- `disc_loss` 只使用 **source labels**（`y_train`），不接触 target labels。

## v21 核心机制（组合安全离合器）

文件：`src/eapp/eval/loso.py`

- v18 的 `track_error` 门控能抓到 subject 9，但会误 hold subject 5。
- v20 的 `disc_loss` 单独门控量级太小且不够判别。
- v21 把二者结合：先按 `track_error` 识别“潜在应 hold 的 fold”，再用 `disc_loss` 过滤假阳性（避免误 hold）。

新增参数（默认关闭，不影响历史复现）：
- `configs/method/ifsa.yaml:safety_disc_loss_tau`
  - 当 `safety_mode=hold_identity` 且 `safety_score_mode=track_error` 时：
    - 若 `track_error` 超阈值触发 hold，才计算 `disc_loss`
    - 仅当 `disc_loss > safety_disc_loss_tau` 才最终 hold

## 本轮运行脚本（远程 RLserver-ex）

- 同步：`./scripts/remote/rl_sync.sh RLserver-ex`
- 运行（tmux 并行）：`./scripts/remote/rl_run_ifsa_iter_v21_final.sh RLserver-ex`
- 拉回：`./scripts/remote/rl_fetch_results.sh RLserver-ex`
- 汇总：
  - `./.venv/bin/python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all`
  - `./.venv/bin/python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=online_prefix_unlabeled`
  - `./.venv/bin/python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=transductive_unlabeled_all`
  - `./.venv/bin/python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=online_prefix_unlabeled`
  - `./.venv/bin/python -m eapp.report_matrix --models csp_lda --datasets bci_iv_2a,bci_iv_2b --target-data-usages transductive_unlabeled_all,online_prefix_unlabeled --methods identity,ea,ra,ra_riemann,coral,ifsa`

## 最终矩阵（acc_mean / NTR / best_variant）

见同目录文件：
- `matrix__csp_lda__acc_mean.csv`
- `matrix__csp_lda__neg_transfer_ratio.csv`
- `matrix__csp_lda__best_variant.csv`

关键结论（从矩阵读取）：
- `2a/trans`：IFSA = **0.509452**（best variant=`ifsa_v21_track_hold_q0p90_disc0p001`），`NTR=0.0`  
  - 接近 best baseline CORAL `0.510224`，且略高于 RA `0.509066`
- `2b/online`：IFSA = **0.722982**（best variant=`ifsa_v11_logmean_shrink0p1`），`NTR≈0.111`

## 产物清单

- 4 个 summary：
  - `summary__bci_iv_2a__transductive_unlabeled_all.csv`
  - `summary__bci_iv_2a__online_prefix_unlabeled.csv`
  - `summary__bci_iv_2b__transductive_unlabeled_all.csv`
  - `summary__bci_iv_2b__online_prefix_unlabeled.csv`
- 3 个矩阵：
  - `matrix__csp_lda__acc_mean.csv`
  - `matrix__csp_lda__neg_transfer_ratio.csv`
  - `matrix__csp_lda__best_variant.csv`
- 环境快照：
  - `env.json`（含 `code_snapshot_sha256`）
  - `config.yaml`

## baseline v2 参照（固定，不重跑）

- `/Users/jason/workspace/code/workspace/Reserch_experiment/EA++/tasks/baselines/baseline_align_csp_lda_v2__2026-02-26__484bd4af1a217147295125f6d1da869ce4fb2fa9708cb34040384d84afdf1dfa/`

