# PhysioNetMI 扩展实验（Final IFSA v2 / transductive）快照

- 日期：2026-02-28
- 数据集：`physionet_mi`（MOABB PhysionetMI）
- Setting：`transductive_unlabeled_all`
- 代码快照：见本目录 `env.json` 里的 `code_snapshot_sha256`

## 复现实验（RLserver-ex）

1) 同步/环境（如需）：

```bash
./scripts/remote/rl_sync.sh RLserver-ex
./scripts/remote/rl_setup.sh RLserver-ex
```

2) 跑全量（顺序执行，避免 OOM；关键：固定重采样，避免 epochs sfreq mismatch）：

```bash
./scripts/remote/rl_run_physionet_mi_final_v2_trans.sh RLserver-ex
```

脚本内对所有方法统一加了：`preprocess.resample=160`（见 `scripts/remote/physionet_mi_final_v2_trans_inner.sh`）。

3) 生成 summary / matrix / pairwise：

```bash
bash scripts/remote/rl_run_physionet_mi_final_v2_trans_report.sh RLserver-ex
./scripts/remote/rl_fetch_results.sh RLserver-ex
```

## 主要产物

- Summary：`summary__physionet_mi__transductive_unlabeled_all.csv`
- Matrix：
  - `matrix__csp_lda__acc_mean.csv`
  - `matrix__csp_lda__neg_transfer_ratio.csv`
  - `matrix__csp_lda__best_variant.csv`
  - `matrix__tangent_lda__acc_mean.csv`
  - `matrix__tangent_lda__neg_transfer_ratio.csv`
  - `matrix__tangent_lda__best_variant.csv`
- Pairwise（审稿人用）：
  - `pairwise__physionet_mi__transductive_unlabeled_all__csp_lda__ifsa_final_v2.csv`
  - `pairwise__physionet_mi__transductive_unlabeled_all__tangent_lda__tsa_ss.csv`

## 结果摘要（n_subjects=109）

### CSP+LDA（同 pipeline）
- `identity`: acc_mean=0.617319
- `ea`: acc_mean=0.688487, NTR(vs identity)=0.146789
- `ra_riemann`: acc_mean=0.685148, NTR(vs identity)=0.155963
- `ifsa_final_v2`: acc_mean=0.675434, NTR(vs identity)=0.174312

### IFSA(final) 配对检验（Wilcoxon + Holm，多重比较修正）
见：`pairwise__physionet_mi__transductive_unlabeled_all__csp_lda__ifsa_final_v2.csv`

- IFSA vs identity：Δ=+0.058115，`p_holm=7.887e-08`
- IFSA vs EA：Δ=-0.013053，`p_holm=0.1031`
- IFSA vs RA-Riemann：Δ=-0.009714，`p_holm=0.0770`

> 结论：在 PhysioNetMI/trans 上，IFSA-final 显著优于不对齐（identity），但在该数据集上未超过 EA/RA-Riemann；差异在 Holm 校正后未达到显著（p<0.05）。
