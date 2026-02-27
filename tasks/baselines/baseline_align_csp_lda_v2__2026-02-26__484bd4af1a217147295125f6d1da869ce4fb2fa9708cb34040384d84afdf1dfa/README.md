# Baseline Suite v2（对齐基线，CSP+LDA）

该 snapshot 用于“以后不需要重复跑”的 **无标注对齐 baseline** 冻结结果（仅 CSP+LDA 管线），后续新方法（IFSA/EA++/TSA-SS…）只需做增量对比。

## 固定 setting（4 个）

- 数据集：`bci_iv_2a`, `bci_iv_2b`
- 协议：`transductive_unlabeled_all`, `online_prefix_unlabeled`
- 模型：`csp_lda`

对应矩阵列名为：

- `bci_iv_2a__transductive_unlabeled_all`
- `bci_iv_2a__online_prefix_unlabeled`
- `bci_iv_2b__transductive_unlabeled_all`
- `bci_iv_2b__online_prefix_unlabeled`

## 固定对齐方法集合（5 个，全程不读 target label）

- `identity`
- `ea`（Euclidean Alignment）
- `ra`（log-Euclidean re-centering）
- `ra_riemann`（Affine-invariant Riemannian mean re-centering，更贴近 TLCenter 口径）
- `coral`（CORAL / covariance mean matching）

方法搜集与实现位置见：`tasks/baselines/alignment_method_catalog.md`。

## 结果文件

- 矩阵（baseline-only）：
  - `matrix__csp_lda__acc_mean.csv`
  - `matrix__csp_lda__neg_transfer_ratio.csv`
  - `matrix__csp_lda__best_variant.csv`
- setting 汇总（由 `python -m eapp.report` 生成）：
  - `summary__bci_iv_2a__transductive_unlabeled_all.csv`
  - `summary__bci_iv_2a__online_prefix_unlabeled.csv`
  - `summary__bci_iv_2b__transductive_unlabeled_all.csv`
  - `summary__bci_iv_2b__online_prefix_unlabeled.csv`
- 环境/可复现快照：
  - `env.json`（含 `code_snapshot_sha256` 与代码文件 hash manifest）
  - `config.yaml`

## 复现实验（远程 RLserver-ex）

1) 同步+安装：

```bash
./scripts/remote/rl_sync.sh RLserver-ex
./scripts/remote/rl_setup.sh RLserver-ex
```

2) 跑 baseline（20 个任务）：

```bash
./scripts/remote/rl_run_alignment_baselines_csp_lda_v2.sh RLserver-ex
```

3) 拉回结果：

```bash
./scripts/remote/rl_fetch_results.sh RLserver-ex
```

4) 本地生成 summary 与 baseline-only matrix：

```bash
./.venv/bin/python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=transductive_unlabeled_all
./.venv/bin/python -m eapp.report dataset=bci_iv_2a protocol.target_data_usage=online_prefix_unlabeled
./.venv/bin/python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=transductive_unlabeled_all
./.venv/bin/python -m eapp.report dataset=bci_iv_2b protocol.target_data_usage=online_prefix_unlabeled

./.venv/bin/python -m eapp.report_matrix \
  --models csp_lda \
  --datasets bci_iv_2a,bci_iv_2b \
  --target-data-usages transductive_unlabeled_all,online_prefix_unlabeled \
  --methods identity,ea,ra,ra_riemann,coral
```

## 参考文献（关键）

- H. He, D. Wu, “Transfer Learning for Brain-Computer Interfaces: A Euclidean Space Data Alignment Approach,” *IEEE Transactions on Biomedical Engineering*, 2020. DOI: 10.1109/TBME.2019.2913925
- P. Zanini, M. Congedo, C. Jutten, S. Said, Y. Berthoumieu, “Transfer Learning: A Riemannian Geometry Framework With Applications to Brain–Computer Interfaces,” *IEEE Transactions on Biomedical Engineering*, 2018. DOI: 10.1109/TBME.2017.2742541
- B. Sun, K. Saenko, “Deep CORAL: Correlation Alignment for Deep Domain Adaptation,” 2016. arXiv:1607.01719
- P. L. C. Rodrigues et al., “Riemannian Procrustes Analysis: Transfer Learning for Brain-Computer Interfaces,” *IEEE Transactions on Biomedical Engineering*, 2019. DOI: 10.1109/TBME.2018.2889705

