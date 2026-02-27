# IFSA v16 Round-E（Dispersion matching：未通过 Gate）

本轮实现并验证了 “分布项 / dispersion matching” 的一个 **NumPy MVP**：在 **reference-whitened 坐标系**下计算 target 的 dispersion（无标注），并用该 dispersion 对 IFSA 的对齐强度做自适应缩放（仍满足 `R_*` source-only）。

## 硬约束（始终满足）

- `R_*` 严格只由 **source subjects** 估计（`x_train/meta_train`），不使用 target。
- target 只使用协议允许的 **unlabeled subset**（`_target_alignment_subset`），不读 target label。

## 实现改动（关键开关）

- `configs/method/ifsa.yaml` 新增：
  - `lambda_disp, disp_scale_min, disp_scale_max`
- `src/eapp/alignment/ifsa.py`：
  - 在 thrust 更新中：若 `lambda_disp>0` 且传入 `target_dispersion`，则根据
    `ratio = sqrt(disp_source / disp_target)` 计算 `disp_scale_eff`，并用它缩放对齐强度。
- `src/eapp/eval/loso.py`：
  - 在 `target_beta>0` 分支，基于 `_target_alignment_subset(x_test, protocol)` 计算 `target_dispersion` 并传入 IFSA（只对 source 训练数据做对齐，target 测试仍保持 identity）。

## Round-E variants

2 个新 variant（各跑 2-setting gate）：

- `ifsa_v16_tg_beta1_full_disp0p5`：`lambda_disp=0.5`
- `ifsa_v16_tg_beta1_full_disp1p0`：`lambda_disp=1.0`

脚本：`scripts/remote/rl_run_ifsa_iter_v16_roundE.sh`

## 结果（人话）

结论：**dispersion matching 这版实现没有提升 transductive，且 online 明显变差**，因此 v16 未通过 gate。

### 2a / transductive（主攻）

| variant | acc_mean | NTR |
|---|---:|---:|
| ifsa_v16_tg_beta1_full_disp0p5 | 0.4919 | 0.111 |
| ifsa_v16_tg_beta1_full_disp1p0 | 0.4765 | 0.111 |

> 对比：当前 best-trans 仍是 `ifsa_v13_tg_beta1_full`（`0.5031`）。

### 2b / online_prefix（哨兵）

| variant | acc_mean | NTR |
|---|---:|---:|
| ifsa_v16_tg_beta1_full_disp0p5 | 0.6969 | 0.444 |
| ifsa_v16_tg_beta1_full_disp1p0 | 0.6904 | 0.556 |

> 对比：当前 best-online 仍是 `ifsa_v11_logmean_shrink0p1`（`0.7230` 且 `NTR=0.111`）。

## 产物

- `matrix__csp_lda__acc_mean.csv`
- `matrix__csp_lda__neg_transfer_ratio.csv`
- `matrix__csp_lda__best_variant.csv`
- `summary__bci_iv_2a__transductive_unlabeled_all.csv`
- `summary__bci_iv_2b__online_prefix_unlabeled.csv`
- `env.json` / `config.yaml`（含 `code_snapshot_sha256`）

## 下一步建议（v17，最小增益优先）

dispersion matching 的核心问题是：**“用一个全局对齐矩阵 A” 很难复现 TLScale 那种逐样本的 manifold stretching**，反而可能在 online-prefix 小样本下放大噪声。

更有希望的两条路（仍不读 label，且 `R_*` source-only）：

1) **target-guided 的“更稳 desired”**：保留 `target_mean_cov` 信息，但在 `desired` 上做正则（例如 `(1-α) desired + α * (tr(desired)/C) I` 或对 `log-eig(desired)` 做 shrink），避免 online-prefix 过拟合。
2) **协方差估计更稳（但不换 LedoitWolf 全局）**：只对 target 子集用更强的 `epsilon I` / shrink，source 维持原估计，减少 target 小样本带来的病态。

