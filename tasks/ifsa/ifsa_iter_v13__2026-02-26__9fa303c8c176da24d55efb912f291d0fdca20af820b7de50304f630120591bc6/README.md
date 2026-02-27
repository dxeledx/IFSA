# IFSA v13 迭代记录（通过 Round-C Gate + Final 4-setting）

本目录冻结了 **IFSA v13** 的关键产物（矩阵 + 4 个 setting 的 summary + env/config），用于后续论文与方法迭代时“可复用对照”。

## 硬约束（始终满足）

- `R_*`（IFSA 惯性参考）**严格只来自 source subjects**（`x_train/meta_train`），不使用 target。
- target 侧仅使用 **unlabeled** 数据，且只允许使用协议规定的 subset（`transductive_unlabeled_all` / `online_prefix_unlabeled`）。
- 不读取 target label。

## Baseline 参照（冻结）

- Baseline v2（CSP+LDA 对齐基线套件）：
  `tasks/baselines/baseline_align_csp_lda_v2__2026-02-26__484bd4af1a217147295125f6d1da869ce4fb2fa9708cb34040384d84afdf1dfa/`

## 结果矩阵（最终交付）

- `matrix__csp_lda__acc_mean.csv`
- `matrix__csp_lda__neg_transfer_ratio.csv`
- `matrix__csp_lda__best_variant.csv`

### 关键结论（人话）

- **2a / transductive（主攻）**：IFSA 通过 v13 的 target-guided 变体显著抬升到 `0.5031`，与最强 baseline（CORAL `0.5102` / RA `0.5091`）差距缩小到 `~0.007`。
- **2b / online_prefix（哨兵）**：IFSA 仍保持显著优势（`0.7230`，且 `NTR=0.111` 明显优于 RA/CORAL 的 `0.556`）。

## Final 选用的 IFSA variants

从 `matrix__csp_lda__best_variant.csv` 读取：

- `bci_iv_2a__transductive_unlabeled_all`：`ifsa_v13_tg_beta1_full`
- `bci_iv_2a__online_prefix_unlabeled`：`ifsa_no_damp_lr0_15`
- `bci_iv_2b__transductive_unlabeled_all`：`ifsa_v13_tg_beta1_full`
- `bci_iv_2b__online_prefix_unlabeled`：`ifsa_v11_logmean_shrink0p1`

### variant 定义（关键参数）

1) `ifsa_v13_tg_beta1_full`（本轮新增，目标是更贴近 CORAL 口径）
- experiment config：`configs/experiment/ifsa_v13_tg_beta1_full.yaml`
- 关键：`target_beta=1.0`（desired=target mean cov，仍满足 `R_*` source-only）
- 关闭 preconditioning：`cov_trace_norm=false`, `cov_shrink_alpha=0`, `lambda_damp=0`
- 关闭额外约束：`lambda_spec=0`, `lambda_u=0`
- 强对齐：`ema_alpha=1`, `k_steps=1`, `lr=0.3`, `lambda_track=4.0`（使 `gain_eff≈1`）

2) `ifsa_v11_logmean_shrink0p1`（历史 best-online）
- 由 `configs/experiment/ifsa_v11_2b_online.yaml` 定义（`experiment_name` 即该 variant）
- 关键：`mean_mode=logeuclid`, `ref_subject_mean_mode=logeuclid`, `cov_shrink_alpha=0.1`
- `trigger_tau`：online 用 `0.5`；transductive 用 CLI override 成 `0.0`

3) `ifsa_no_damp_lr0_15`（历史 best-online/2a-online）
- 来自历史实验结果（不在本轮新增配置），后续若要固化可再补一个显式 experiment yaml。

## 可复现信息

- `env.json`：含 `code_snapshot_sha256` 与代码文件 hash manifest
- `config.yaml`：来自一次 Final run 的 resolved config

## 复现实验（远程 RLserver-ex）

1) 同步 + 安装：
```bash
./scripts/remote/rl_sync.sh RLserver-ex
./scripts/remote/rl_setup.sh RLserver-ex
```

2) Round-C（2-setting 筛选，8 个 tmux 任务）：
```bash
./scripts/remote/rl_run_ifsa_iter_v13_roundC.sh RLserver-ex
```

3) Final（4-setting 全跑，8 个 tmux 任务）：
```bash
./scripts/remote/rl_run_ifsa_iter_v13_final.sh RLserver-ex
```

4) 拉回结果：
```bash
./scripts/remote/rl_fetch_results.sh RLserver-ex
```

5) 本地生成 4 个 summary + 最终矩阵：
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

## 下一步（v14 最小增益建议）

优先级按“信息增益 / 改动小”排序：

1) 只针对 `2a/trans` 做 **协方差估计更稳** 的对照：
- 在 best-trans variant 上追加 1–2 个 run：`preprocess.covariance.estimator=ledoit_wolf`（不改算法结构）。

2) 若仍追不上 CORAL/RA：加一个“分布项”而不只均值：
- 在白化坐标系下对齐 `log-eig` 的均值/方差（dispersion matching），仍保持无标注。

3) 控制律层面升级：
- 把当前 `a_ref=(1-α)I+α a_new` 的欧式混合改为 log-domain 插值（减少 SPD 空间混合误差）。
