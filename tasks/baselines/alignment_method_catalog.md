# 跨被试 EEG 数据对齐方法 Catalog（对齐基线选型依据）

本表用于记录“常见对齐方法 / 关键论文 / 代码实现 / 是否需要 target 标签 / 是否兼容本仓库的两种协议”。

## 本仓库协议口径

- `transductive_unlabeled_all`：允许使用 **全部 target trial 的无标注数据** 做对齐（但禁止读 target label）。
- `online_prefix_unlabeled`：只允许使用 **前 N 个 target trial 的无标注数据** 做对齐（典型：在线递推/冷启动前缀）。

## 方法总表

| 方法 | 类别 | 是否需要 target 标签 | transductive | online_prefix | 关键论文/出处 | 本仓库/开源实现 |
|---|---|---:|:---:|:---:|---|---|
| `identity` | signal | 否 | ✅ | ✅ | - | `src/eapp/alignment/identity.py` |
| `ea`（Euclidean Alignment） | signal | 否 | ✅ | ✅ | He & Wu, *Transfer Learning for Brain-Computer Interfaces: A Euclidean Space Data Alignment Approach*, IEEE TBME 2020. DOI: 10.1109/TBME.2019.2913925 | `src/eapp/alignment/ea.py` |
| `ra`（Log-Euclidean re-centering） | signal | 否 | ✅ | ✅ | TLCenter 思想来自 Zanini et al., *Transfer Learning: A Riemannian Geometry Framework With Applications to Brain–Computer Interfaces*, IEEE TBME 2018. DOI: 10.1109/TBME.2017.2742541（本实现用 log-Euclidean mean） | `src/eapp/alignment/ra.py` |
| `ra_riemann`（Affine-invariant Riemannian mean re-centering） | signal | 否 | ✅ | ✅ | 同上（更贴近 TLCenter 的 riemann mean 口径） | `src/eapp/alignment/ra_riemann.py`（内部调用 `pyriemann.utils.mean.mean_riemann`） |
| `coral`（CORAL / covariance matching） | signal | 否 | ✅ | ✅ | Sun & Saenko, *Deep CORAL: Correlation Alignment for Deep Domain Adaptation*, ECCV workshop 2016. arXiv: 1607.01719 | `src/eapp/alignment/coral.py`（使用 `_target_alignment_subset()` 获取 target 子集） |
| `tl_center_scale`（TLCenter + TLScale） | cov | 否 | ✅ | ✅ | pyRiemann `pyriemann.transfer`（TLCenter / TLScale） | `src/eapp/eval/loso.py`（仅 `model=mdm` 支持） |
| `rpa`（Riemannian Procrustes Analysis） | cov/tangent | **通常需要**（target label 或 pseudo label） | ⚠️ | ⚠️ | Rodrigues et al., *Riemannian Procrustes Analysis: Transfer Learning for Brain-Computer Interfaces*, IEEE T-BME 2019. DOI: 10.1109/TBME.2018.2889705 | pyRiemann `pyriemann.transfer`（如 `TLRotate` 等；多数需要 target label） |
| `tsa`（Tangent Space Alignment） | tangent | 否（但用 pseudo-label 做 anchor） | ✅ | ✅ | 仓库内方法（后续可补齐对应论文 mapping） | `src/eapp/alignment/tsa.py`（`model=tangent_lda`） |
| `tsa_ss`（TSA + stable subspace） | tangent | 否（pseudo-label anchor） | ✅ | ✅ | 仓库内方法（MVP） | `src/eapp/alignment/tsa_ss.py`（`model=tangent_lda`） |
| `ea_pp`（EA++） | signal | 否 | ✅ | ✅ | 仓库内方法（EA 改进线） | `src/eapp/alignment/ea_pp.py` |
| `ifsa`（鸡头稳定启发） | signal | 否 | ✅ | ✅ | 仓库内方法（创新线） | `src/eapp/alignment/ifsa.py` |
| MEKT（Manifold Embedded Knowledge Transfer） | cov+tangent+DA | 否（用 target unlabeled） | ✅ | ✅ | Zhang & Wu, *Manifold Embedded Knowledge Transfer for Brain-Computer Interfaces*, 2019（arXiv: 1910.05878） | 目前未在本仓库实现（后续可做扩展 baseline） |

> 说明：本仓库的“baseline suite v2（CSP+LDA）”只选择 `identity/ea/ra/ra_riemann/coral`，原因是它们在 **不读 target label** 的前提下，与 `transductive_unlabeled_all` 和 `online_prefix_unlabeled` 都天然兼容，且能直接嵌入 CSP+LDA 信号管线。

