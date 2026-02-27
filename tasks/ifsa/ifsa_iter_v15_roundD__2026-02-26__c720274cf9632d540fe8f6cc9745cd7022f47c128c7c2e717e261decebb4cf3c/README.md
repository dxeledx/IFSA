# IFSA v15 Round-D（结构小改动：log-mix + cov-log-spectrum shrink）

本轮用 **2-setting gate** 快速验证两项“控制结构/稳定性”增强是否能继续抬升 IFSA：

- `a_mix_mode=log`：`A_ref` 从欧式混合改为 log-domain 插值（更符合 SPD 几何）。
- `cov_log_spec_shrink>0`：对每个 trial 协方差做 log-spectrum shrink（更“隔振”的谱稳定）。

## 硬约束（始终满足）

- `R_*` 严格只由 **source subjects** 估计（`x_train/meta_train`），不使用 target。
- target 仅使用协议允许的 **unlabeled subset**（`_target_alignment_subset`），不读 target label。

## Round-D 运行设置

- 运行脚本：`scripts/remote/rl_run_ifsa_iter_v15_roundD.sh`
- 两个 setting：
  - `bci_iv_2a` + `transductive_unlabeled_all`（`method.trigger_tau=0.0`）
  - `bci_iv_2b` + `online_prefix_unlabeled`（`method.trigger_tau=0.5`）

## Round-D variants（新增）

- `ifsa_v15_tg_beta1_full_covlogsh0p1`
- `ifsa_v15_tg_beta1_full_covlogsh0p2`
- `ifsa_v15_logmix_logmean_sh0p1`
- `ifsa_v15_logmix_logmean_sh0p1_covlogsh0p1`

## 结果（人话）

结论：**本轮两项增强都没有超过 v13 / v11 的 best**。

### 2a / transductive（主攻）

| variant | acc_mean | NTR |
|---|---:|---:|
| ifsa_v15_tg_beta1_full_covlogsh0p1 | 0.4936 | 0.111 |
| ifsa_v15_tg_beta1_full_covlogsh0p2 | 0.4884 | 0.111 |
| ifsa_v15_logmix_logmean_sh0p1_covlogsh0p1 | 0.4794 | 0.222 |
| ifsa_v15_logmix_logmean_sh0p1 | 0.4666 | 0.222 |

> 对比：当前 best-trans 仍是 `ifsa_v13_tg_beta1_full`（`0.5031`）。

### 2b / online_prefix（哨兵）

| variant | acc_mean | NTR |
|---|---:|---:|
| ifsa_v15_logmix_logmean_sh0p1 | 0.7230 | 0.222 |
| ifsa_v15_logmix_logmean_sh0p1_covlogsh0p1 | 0.7211 | 0.222 |
| ifsa_v15_tg_beta1_full_covlogsh0p2 | 0.7125 | 0.444 |
| ifsa_v15_tg_beta1_full_covlogsh0p1 | 0.7101 | 0.556 |

> 对比：当前 best-online 仍是 `ifsa_v11_logmean_shrink0p1`（`0.7230` 且 `NTR=0.111`）。

## 产物

- `matrix__csp_lda__acc_mean.csv`
- `matrix__csp_lda__neg_transfer_ratio.csv`
- `matrix__csp_lda__best_variant.csv`
- `summary__bci_iv_2a__transductive_unlabeled_all.csv`
- `summary__bci_iv_2b__online_prefix_unlabeled.csv`
- `env.json` / `config.yaml`（含 `code_snapshot_sha256`）

## 下一步建议（v16，信息增益优先）

1) **真正的“分布项”**（而不是对 cov 本身 shrink）：在白化坐标系下匹配 target 的 `log-eig` 分布统计（均值+方差），或做 TLScale 风格的 dispersion matching（仍不读 label）。
2) **target-guided 但更稳**：仅在 `2a/trans` 上尝试 `cov_trace_norm=true` 或小 `cov_shrink_alpha`（同时对 source/target 做同口径处理），看能否在不牺牲 online 的情况下抬升 trans。
3) 若要让 “online-prefix” NTR 更优：优先围绕 `ifsa_v11_logmean_shrink0p1` 做微调（而不是引入 target-guided）。

