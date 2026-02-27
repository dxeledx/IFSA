# IFSA Final（主线版本）：`ifsa_final_v2`

本目录冻结了 **统一候选算法（Final IFSA v2）** 的关键产物，用于回答审稿人关于「算法到底是什么」「是否过拟合」「是否显著优于强基线」「是否减少负迁移」等核心问题。

> 说明：当前矩阵里 IFSA 的 **best-variant** 仍会随 setting 变化（online 最优常由历史 v11/v21 提供）。这里的主线结论以 **统一版本 `ifsa_final_v2`** 为准；后续若要在 4 setting 都逼近 best，将在不读 target label 的约束下做“无标签自适应切换/强度选择”。

---

## 1) Final IFSA v2（唯一算法定义）

**Pipeline（固定）：** `model=csp_lda`（CSP + LDA）

**Final IFSA v2 的核心模块：**

1. **Target-guided desired（不读 target label）**  
   `target_beta=1.0`，`mean_mode=logeuclid`，`ref_subject_mean_mode=logeuclid`
2. **Euclid-thrust（允许非对称 A，引入旋转自由度）**  
   `thrust_mode=euclid`（`A` 可非对称，但协方差始终按 `A C A^T` 传播，保证 SPD）
3. **Chicken-head safety clutch（只用 source + target unlabeled）**  
   `safety_score_mode=track_error` + `safety_mode=scale_gain`  
   并带两级 guard：  
   - `safety_hold_gate_threshold`（gate 太小直接 hold）  
   - `safety_disc_loss_tau`（disc-loss 二级 guard，避免误 hold/误 scale）  
4. **v30 低分 hold（“无需对齐就别动”）**  
   当 `score_target < safety_low_score_mult * tau_eff` 时回退 identity，避免注入噪声。

**配置文件：**
- `configs/experiment/ifsa_final_v2.yaml`

**关键超参数（`ifsa_final_v2`）：**
- `target_beta=1.0`
- `mean_mode=logeuclid`, `ref_subject_mean_mode=logeuclid`
- `lambda_track=4.0`, `k_steps=1`, `lr=0.3`, `ema_alpha=1.0`
- `thrust_mode=euclid`, `a_mix_mode=euclid`
- safety clutch：
  - `safety_mode=scale_gain`
  - `safety_score_mode=track_error`
  - `safety_quantile=0.90`
  - `safety_tau_mult=0.7`
  - `safety_hold_gate_threshold=0.6`
  - `safety_disc_loss_tau=0.001`
  - `safety_low_score_mult=0.6`

---

## 2) 四个 setting（统一评估入口）

本轮同时导出了你要求的 **4-setting**：

- `bci_iv_2a/transductive_unlabeled_all`（trans，`method.trigger_tau=0.0`）
- `bci_iv_2b/transductive_unlabeled_all`（trans，`method.trigger_tau=0.0`）
- `bci_iv_2a/online_prefix_unlabeled`（online，`method.trigger_tau=0.5`）
- `bci_iv_2b/online_prefix_unlabeled`（online，`method.trigger_tau=0.5`）

---

## 3) 主线结果（Final IFSA v2 across 4 settings）

从 `summary__*.csv` 直接读取 `variant=ifsa_final_v2` 行：

| setting | acc_mean | NTR(vs identity) |
|---|---:|---:|
| 2a/trans | 0.514082 | 0.000 |
| 2b/trans | 0.731614 | 0.000 |
| 2a/online | 0.466242 | 0.222 |
| 2b/online | 0.708685 | 0.444 |

> 备注：目前 `ifsa_final_v2` 的主优势集中在 **trans（2a/2b）**；online 的 best 仍由历史 v11/v21 提供，后续若要统一版本 4-setting 全面强，需要在“无标签”约束下继续做自适应策略。

---

## 4) 审稿人级统计：IFSA(final) vs 强基线（Wilcoxon + Holm）

对应 4 个 setting 的 pairwise 输出（每个 baseline 一行，含 `delta_mean / p_value / p_holm / effect_rank_biserial / neg_transfer_ratio`）：
- `pairwise__bci_iv_2a__transductive_unlabeled_all__csp_lda__ifsa_final_v2.csv`
- `pairwise__bci_iv_2b__transductive_unlabeled_all__csp_lda__ifsa_final_v2.csv`
- `pairwise__bci_iv_2a__online_prefix_unlabeled__csp_lda__ifsa_final_v2.csv`
- `pairwise__bci_iv_2b__online_prefix_unlabeled__csp_lda__ifsa_final_v2.csv`

---

## 5) 确定性（seed check）

远程在 RLserver-ex 对 `bci_iv_2a/trans` 复跑 `runtime.seed=43`，并用脚本对比 per-subject acc：
- `scripts/analysis/check_seed_determinism_csv.py`
- 结果：`max_abs_diff=0.0`（完全一致）

---

## 6) 与 baseline v2 的对比参照（固定引用）

baseline v2 快照目录（冻结、不可变）：
- `/Users/jason/workspace/code/workspace/Reserch_experiment/EA++/tasks/baselines/baseline_align_csp_lda_v2__2026-02-26__484bd4af1a217147295125f6d1da869ce4fb2fa9708cb34040384d84afdf1dfa/`

---

## 7) 复现实用命令（远程 RLserver-ex）

### 7.1 同步 / 安装
```bash
./scripts/remote/rl_sync.sh RLserver-ex
./scripts/remote/rl_setup.sh RLserver-ex
```

### 7.2 跑齐 Final IFSA v2（4 setting + seedcheck）
```bash
./scripts/remote/rl_run_ifsa_final_v2_unify.sh RLserver-ex
```

### 7.3 生成 4 个 summary + 2 个 matrix + pairwise
在 RLserver-ex：
```bash
python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all
python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=online_prefix_unlabeled
python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=transductive_unlabeled_all
python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=online_prefix_unlabeled

python -m eapp.report_matrix \
  --models csp_lda,tangent_lda \
  --datasets bci_iv_2a,bci_iv_2b \
  --target-data-usages transductive_unlabeled_all,online_prefix_unlabeled \
  --methods identity,ea,ra,ra_riemann,coral,ifsa,tsa,tsa_ss

python -m eapp.report_pairwise --dataset bci_iv_2a --target-data-usage transductive_unlabeled_all --model csp_lda --target-variant ifsa_final_v2 --no-plot
python -m eapp.report_pairwise --dataset bci_iv_2a --target-data-usage online_prefix_unlabeled --model csp_lda --target-variant ifsa_final_v2 --no-plot
python -m eapp.report_pairwise --dataset bci_iv_2b --target-data-usage transductive_unlabeled_all --model csp_lda --target-variant ifsa_final_v2 --no-plot
python -m eapp.report_pairwise --dataset bci_iv_2b --target-data-usage online_prefix_unlabeled --model csp_lda --target-variant ifsa_final_v2 --no-plot
```

### 7.4 拉回结果
```bash
./scripts/remote/rl_fetch_results.sh RLserver-ex
```

---

## 8) 文献与备注

- CORAL 原论文题目：**Correlation Alignment for Unsupervised Domain Adaptation**（Sun, Feng, Saenko）
- Deep CORAL：**Deep CORAL: Correlation Alignment for Deep Domain Adaptation**
- `coral_safe`：用于验证/诊断 “safety clutch” 直觉的内部对照变体；主线迭代目标始终是 IFSA。

