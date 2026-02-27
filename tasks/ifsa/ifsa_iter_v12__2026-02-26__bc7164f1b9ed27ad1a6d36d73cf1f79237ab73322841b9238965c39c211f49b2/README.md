# IFSA v12 迭代记录（止损快照）

本目录冻结了 **IFSA v12（Round-A + Round-B）** 的迭代实验产物与矩阵，便于后续对照与继续迭代。

## 关键约束

- `R_*`（IFSA 惯性参考）**严格只来自 source subjects**（`x_train/meta_train`），不使用 target。
- 仅使用 target 的 **unlabeled** 数据（`transductive_unlabeled_all` 或 `online_prefix_unlabeled` 允许的 subset）。
- 不读取 target label（协议防泄漏测试已在 `tests/test_protocol_leakage.py` 等覆盖）。

## 基线参照（冻结）

- Baseline v2（CSP+LDA 对齐基线套件）：  
  `tasks/baselines/baseline_align_csp_lda_v2__2026-02-26__484bd4af1a217147295125f6d1da869ce4fb2fa9708cb34040384d84afdf1dfa/`

## 最终“最好结果”矩阵（baseline + ifsa）

见本目录：

- `matrix__csp_lda__acc_mean.csv`
- `matrix__csp_lda__neg_transfer_ratio.csv`
- `matrix__csp_lda__best_variant.csv`

其中 `ifsa` 行代表在该 setting 下 **所有 IFSA variants 的最优**（由 `eapp.report_matrix` 选取）。

**结论（人话）**

- `bci_iv_2a / transductive`：IFSA 仍落后 RA/CORAL（主要瓶颈）
- `bci_iv_2a / online_prefix`：IFSA 与 RA 系列基本持平，略有优势
- `bci_iv_2b / transductive`：IFSA 与 EA/RA 基线非常接近
- `bci_iv_2b / online_prefix`：IFSA 明显强于 RA/CORAL（这是当前最大亮点）

## Round-A（仅用现有 IFSA 开关）

新增 6 个 v12 变体配置：

- `configs/experiment/ifsa_v12_ctrl.yaml`
- `configs/experiment/ifsa_v12_trace_norm.yaml`
- `configs/experiment/ifsa_v12_trace_norm_sh0p1.yaml`
- `configs/experiment/ifsa_v12_trace_norm_sh0p2.yaml`
- `configs/experiment/ifsa_v12_trace_norm_logmean_sh0p1.yaml`
- `configs/experiment/ifsa_v12_trace_norm_logmean_sh0p1_idout.yaml`

结果要点：

- 2a/trans 上 `ifsa_v12_ctrl` 仍是最好（≈0.484），`trace_norm/shrink/logmean` 在当前实现下会显著变差。

## Round-B（target-guided IFSA：已实现但效果不佳）

实现了 `target_beta`（0..1）：

- `src/eapp/alignment/ifsa.py`：`IFSAConfig.target_beta` + `target_mean_cov` 注入
- `src/eapp/eval/loso.py`：当 `target_beta>0` 时，从 `_target_alignment_subset(x_test, protocol)` 计算 target 均值协方差，仅对 **source** 做 IFSA 对齐（target 保持 identity）

对应配置：

- `configs/experiment/ifsa_v12_tg_beta0p5.yaml`
- `configs/experiment/ifsa_v12_tg_beta1p0.yaml`

结果要点：

- 两个 target-guided 变体在 2a/trans 上明显 **更差**（≈0.427～0.436）。

**当前推断的失败原因（最可能）**

1) `cov_trace_norm / cov_shrink_alpha` 会改变 IFSA 内部用于求解 `A` 的协方差目标，但 `A` 最终作用在“原始信号”上；当这些 pre-conditioning 开关开启时，目标与实际变换空间不一致，容易导致 CSP+LDA 下分布错配。  
2) target-guided 的两组配置沿用了 `trace_norm=true` 的设定，而 Round-A 已显示该开关会显著伤害 2a/trans。

> 下一轮若继续做 target-guided，建议先做 “CORAL 一致口径” 的版本：`cov_trace_norm=false`、`cov_shrink_alpha=0`，并直接让 `desired = target_mean_cov`（beta=1）以验证是否能逼近/复现 CORAL 的增益。

## 可复现信息

- `env.json`：含 `code_snapshot_sha256`（本快照目录名即该 hash）
- `config.yaml`：对应其中一次远程 run 的 resolved config

## 复现实验（远程 RLserver-ex）

```bash
./scripts/remote/rl_sync.sh RLserver-ex
./scripts/remote/rl_setup.sh RLserver-ex
./scripts/remote/rl_run_ifsa_iter_roundA.sh RLserver-ex
# Round-B（示例）
./scripts/remote/rl_run_tmux.sh RLserver-ex ifsa_roundB__beta1__2a__trans \
  "python -m eapp.run experiment=ifsa_v12_tg_beta1p0 dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all method.trigger_tau=0.0 runtime.n_jobs=1"
./scripts/remote/rl_fetch_results.sh RLserver-ex
```

本地生成 summary + matrix：

```bash
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

