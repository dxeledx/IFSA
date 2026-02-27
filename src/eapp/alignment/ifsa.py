from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from eapp.representation.covariance import CovarianceConfig, compute_covariances
from eapp.utils.spd import (
    Eigendecomp,
    clamp_eigenvalues,
    eigh_sym,
    expm_sym,
    invsqrtm_spd,
    log_eigvals_spd,
    log_euclidean_mean,
    logm_spd,
    sqrtm_spd,
    sym,
)


@dataclass(frozen=True)
class IFSAMetrics:
    spec_var_before: float
    spec_var_after: float
    control_energy: float
    track_error_before: float
    track_error_after: float
    triggered: int
    trigger_tau_eff: float
    dispersion_target: float
    dispersion_before: float
    dispersion_after: float
    dispersion_scale_eff: float


@dataclass(frozen=True)
class IFSAConfig:
    lambda_track: float
    lambda_spec: float
    lambda_damp: float
    cov_trace_norm: bool
    cov_shrink_alpha: float
    cov_log_spec_shrink: float  # 0..1; shrink log-spectrum of trial covariances
    mean_mode: str  # arith | logeuclid
    target_beta: float  # 0..1; blend desired ref between source inertial R_* and target mean cov
    desired_shrink_alpha: float  # 0..0.3; isotropic trace-shrink on desired (target-guided only)
    desired_log_spec_shrink: float  # 0..1; log-spectrum shrink on desired (target-guided only)
    lambda_u: float
    k_steps: int
    lr: float
    ema_alpha: float
    thrust_mode: str  # spd | euclid
    a_mix_mode: str  # euclid | log
    lambda_disp: float  # 0..1; dispersion matching strength (target-guided only)
    disp_scale_min: float
    disp_scale_max: float
    trigger_tau: float
    trigger_mode: str  # fixed | source_quantile (computed in LOSO)
    trigger_quantile: float
    damp_mode: str  # euclid_ema | log_ema
    output_space: str  # reference | identity
    ref_subject_mean_mode: str  # arith | logeuclid (used for reference estimation only)


def _shrink_log_spectrum(decomp: Eigendecomp, strength: float) -> np.ndarray:
    values = clamp_eigenvalues(decomp.values, 1e-30)
    log_vals = np.log(values)
    mean_log = float(np.mean(log_vals))
    log_new = mean_log + (1.0 - strength) * (log_vals - mean_log)
    return decomp.vectors @ np.diag(np.exp(log_new)) @ decomp.vectors.T


def _ema_smooth_covs(covs: np.ndarray, rho: float) -> np.ndarray:
    if covs.shape[0] <= 1 or rho <= 0.0:
        return covs
    out = np.empty_like(covs)
    out[0] = covs[0]
    for i in range(1, covs.shape[0]):
        out[i] = sym((1.0 - rho) * out[i - 1] + rho * covs[i])
    return out


def _ema_smooth_covs_log(covs: np.ndarray, rho: float, eps: float) -> np.ndarray:
    if covs.shape[0] <= 1 or rho <= 0.0:
        return covs
    out = np.empty_like(covs)
    prev = logm_spd(covs[0], eps=eps)
    out[0] = covs[0]
    for i in range(1, covs.shape[0]):
        cur = logm_spd(covs[i], eps=eps)
        prev = sym((1.0 - rho) * prev + rho * cur)
        out[i] = expm_sym(prev)
    return out


def _trace_shrink_covs(covs: np.ndarray, alpha: float) -> np.ndarray:
    alpha = float(alpha)
    if covs.shape[0] == 0 or alpha <= 0.0:
        return covs
    alpha = max(0.0, min(0.3, alpha))
    dim = covs.shape[1]
    eye = np.eye(dim, dtype=float)
    out = np.empty_like(covs)
    for i, cov in enumerate(covs):
        t = float(np.trace(cov)) / float(dim)
        out[i] = sym((1.0 - alpha) * cov + alpha * t * eye)
    return out


def _log_spec_shrink_covs(covs: np.ndarray, strength: float) -> np.ndarray:
    strength = float(strength)
    if covs.shape[0] == 0 or strength <= 0.0:
        return covs
    strength = max(0.0, min(1.0, strength))
    out = np.empty_like(covs)
    for i, cov in enumerate(covs):
        out[i] = sym(_shrink_log_spectrum(eigh_sym(cov), strength=strength))
    return out


def _trace_normalize_covs(covs: np.ndarray, eps: float) -> np.ndarray:
    if covs.shape[0] == 0:
        return covs
    dim = covs.shape[1]
    out = np.empty_like(covs)
    for i, cov in enumerate(covs):
        t = float(np.trace(cov)) / float(dim)
        t = max(float(eps), t)
        out[i] = sym(cov / t)
    return out


def _mean_spd(covs: np.ndarray, mode: str, eps: float) -> np.ndarray:
    if mode == "arith":
        return sym(np.mean(covs, axis=0))
    if mode == "logeuclid":
        return log_euclidean_mean(covs, eps=eps)
    raise ValueError(f"Unknown IFSA mean_mode={mode!r}")


def _mean_whitened_cov(
    a: np.ndarray,
    covs: np.ndarray,
    w: np.ndarray,
    *,
    mean_mode: str,
    eps: float,
) -> np.ndarray:
    # Use A cov A^T and W (...) W (A may be non-symmetric depending on thrust_mode).
    cov_a = np.einsum("ij,njk,lk->nil", a, covs, a)
    cov_w = np.einsum("ij,njk,lk->nil", w, cov_a, w)
    return _mean_spd(cov_w, mode=mean_mode, eps=eps)


def _project_spd(matrix: np.ndarray, eps: float) -> np.ndarray:
    """Project an arbitrary square matrix to symmetric positive definite."""
    decomp = eigh_sym(sym(matrix))
    values = clamp_eigenvalues(decomp.values, eps)
    return decomp.vectors @ np.diag(values) @ decomp.vectors.T


class IFSASignalAligner:
    def __init__(
        self,
        cov_cfg: CovarianceConfig,
        cfg: IFSAConfig,
        reference_cov: np.ndarray,
        *,
        target_mean_cov: np.ndarray | None = None,
        target_dispersion: float | None = None,
    ):
        self.cov_cfg = cov_cfg
        self.cfg = cfg
        self.reference_cov = sym(reference_cov)
        self.target_mean_cov = sym(target_mean_cov) if target_mean_cov is not None else None
        self.target_dispersion = (
            float(target_dispersion) if target_dispersion is not None else None
        )
        self.matrix: np.ndarray | None = None
        self.metrics: IFSAMetrics | None = None

    def _dispersion(
        self,
        a: np.ndarray,
        covs: np.ndarray,
        *,
        w_ref: np.ndarray,
        desired_inv_sqrt: np.ndarray,
    ) -> float:
        cov_a = np.einsum("ij,njk,lk->nil", a, covs, a)
        cov_w = np.einsum("ij,njk,lk->nil", w_ref, cov_a, w_ref)
        cov_n = np.einsum("ij,njk,lk->nil", desired_inv_sqrt, cov_w, desired_inv_sqrt)
        vals = []
        for cov in cov_n:
            logm = logm_spd(sym(cov), eps=self.cov_cfg.epsilon)
            vals.append(float(np.linalg.norm(logm, ord="fro") ** 2))
        if not vals:
            return 0.0
        return float(np.mean(np.asarray(vals, dtype=float)))

    def fit(self, x: np.ndarray) -> IFSASignalAligner:
        covs_raw = compute_covariances(x, self.cov_cfg)
        covs_alg = covs_raw
        if bool(self.cfg.cov_trace_norm):
            covs_alg = _trace_normalize_covs(covs_alg, eps=self.cov_cfg.epsilon)
        covs_alg = _trace_shrink_covs(covs_alg, alpha=float(self.cfg.cov_shrink_alpha))
        covs_alg = _log_spec_shrink_covs(
            covs_alg, strength=float(self.cfg.cov_log_spec_shrink)
        )

        rho = max(0.0, min(0.99, float(self.cfg.lr) * float(self.cfg.lambda_damp)))
        if self.cfg.damp_mode == "euclid_ema":
            covs_smooth = _ema_smooth_covs(covs_alg, rho=rho)
        elif self.cfg.damp_mode == "log_ema":
            covs_smooth = _ema_smooth_covs_log(covs_alg, rho=rho, eps=self.cov_cfg.epsilon)
        else:
            raise ValueError(f"Unknown IFSA damp_mode={self.cfg.damp_mode!r}")

        beta = float(self.cfg.target_beta)
        if beta < 0.0 or beta > 1.0:
            raise ValueError(f"IFSA target_beta must be in [0,1], got {beta}")
        if beta > 0.0 and self.target_mean_cov is None:
            raise ValueError("IFSA target_mean_cov must be provided when target_beta > 0")

        desired = self.reference_cov
        if beta > 0.0:
            desired = expm_sym(
                (1.0 - beta) * logm_spd(self.reference_cov, eps=self.cov_cfg.epsilon)
                + beta * logm_spd(self.target_mean_cov, eps=self.cov_cfg.epsilon)  # type: ignore[arg-type]
            )

            alpha_des = max(0.0, min(0.3, float(self.cfg.desired_shrink_alpha)))
            if alpha_des > 0.0:
                dim = int(desired.shape[0])
                eye = np.eye(dim, dtype=float)
                t = float(np.trace(desired)) / float(dim)
                desired = sym((1.0 - alpha_des) * desired + alpha_des * t * eye)

            strength_des = max(0.0, min(1.0, float(self.cfg.desired_log_spec_shrink)))
            if strength_des > 0.0:
                desired = sym(_shrink_log_spectrum(eigh_sym(desired), strength=strength_des))

        w_ref = invsqrtm_spd(self.reference_cov, eps=self.cov_cfg.epsilon)
        desired_white = sym(w_ref @ desired @ w_ref)
        desired_inv_sqrt = invsqrtm_spd(desired_white, eps=self.cov_cfg.epsilon)

        desired_sqrt = sqrtm_spd(desired, eps=self.cov_cfg.epsilon)
        identity = np.eye(covs_raw.shape[1], dtype=float)

        mean_white = _mean_whitened_cov(
            identity,
            covs_smooth,
            w_ref,
            mean_mode=str(self.cfg.mean_mode),
            eps=self.cov_cfg.epsilon,
        )
        error0 = logm_spd(
            sym(desired_inv_sqrt @ mean_white @ desired_inv_sqrt),
            eps=self.cov_cfg.epsilon,
        )
        track_error_before = float(np.linalg.norm(error0, ord="fro"))

        a_ref = identity
        triggered = 0
        disp_target = (
            float(self.target_dispersion) if self.target_dispersion is not None else float("nan")
        )
        disp_before = float("nan")
        disp_after = float("nan")
        disp_scale_eff = 1.0

        want_disp = bool(float(self.cfg.lambda_disp) > 0.0 and self.target_dispersion is not None)
        if want_disp:
            disp_before = self._dispersion(
                identity,
                covs_smooth,
                w_ref=w_ref,
                desired_inv_sqrt=desired_inv_sqrt,
            )
        if (
            track_error_before > float(self.cfg.trigger_tau)
            and int(self.cfg.k_steps) > 0
            and float(self.cfg.lambda_track) != 0.0
        ):
            triggered = 1
            thrust_mode = str(getattr(self.cfg, "thrust_mode", "spd"))
            if thrust_mode not in {"spd", "euclid"}:
                raise ValueError(f"Unknown IFSA thrust_mode={thrust_mode!r}")

            if thrust_mode == "euclid":
                if float(self.cfg.lambda_spec) != 0.0:
                    raise ValueError("IFSA thrust_mode='euclid' requires lambda_spec=0")
                if float(self.cfg.lambda_u) != 0.0:
                    raise ValueError("IFSA thrust_mode='euclid' requires lambda_u=0")
                if float(self.cfg.lambda_disp) != 0.0:
                    raise ValueError("IFSA thrust_mode='euclid' requires lambda_disp=0")
                if str(self.cfg.a_mix_mode) != "euclid":
                    raise ValueError("IFSA thrust_mode='euclid' requires a_mix_mode='euclid'")
                if str(self.cfg.output_space) != "reference":
                    raise ValueError(
                        "IFSA thrust_mode='euclid' requires output_space='reference'"
                    )

            mean_cov = _mean_spd(
                covs_smooth,
                mode=str(self.cfg.mean_mode),
                eps=self.cov_cfg.epsilon,
            )

            if thrust_mode == "spd":
                # Closed-form "recoloring" to match the desired reference:
                # pick A SPD such that A * mean_cov * A = desired.
                # One SPD solution is:
                #   A = R^{1/2} (R^{1/2} M R^{1/2})^{-1/2} R^{1/2}
                # where R=desired, M=mean_cov.
                s = sym(desired_sqrt @ mean_cov @ desired_sqrt)
                a_full = sym(
                    desired_sqrt
                    @ invsqrtm_spd(s, eps=self.cov_cfg.epsilon)
                    @ desired_sqrt
                )
            else:
                # Euclid-thrust (non-symmetric): pick A such that
                #   A * mean_cov * A^T = desired.
                # A closed-form solution is:
                #   A = desired^{1/2} * mean_cov^{-1/2}
                a_full = desired_sqrt @ invsqrtm_spd(mean_cov, eps=self.cov_cfg.epsilon)

            gain_step = max(0.0, min(1.0, float(self.cfg.lr) * float(self.cfg.lambda_track)))
            steps = max(0, int(self.cfg.k_steps))
            gain_eff = 0.0 if steps <= 0 else 1.0 - (1.0 - gain_step) ** steps

            if thrust_mode == "spd":
                # Interpolate between I and a_full on the SPD manifold (log-domain),
                # so gain_eff=0 -> I (no alignment), gain_eff=1 -> a_full.
                log_a = logm_spd(a_full, eps=self.cov_cfg.epsilon)
                a_new = expm_sym(gain_eff * log_a)

                # Optional: match target dispersion (in reference-whitened coords),
                # using only unlabeled target subset statistics computed in LOSO.
                if (
                    want_disp
                    and float(self.target_dispersion) > 0.0  # type: ignore[arg-type]
                ):
                    disp_src = self._dispersion(
                        a_new,
                        covs_smooth,
                        w_ref=w_ref,
                        desired_inv_sqrt=desired_inv_sqrt,
                    )
                    ratio = float(
                        np.sqrt(
                            max(1e-12, disp_src)
                            / max(1e-12, float(self.target_dispersion))
                        )
                    )
                    lam = max(0.0, min(1.0, float(self.cfg.lambda_disp)))
                    disp_scale_eff = 1.0 + lam * (ratio - 1.0)
                    disp_scale_eff = max(
                        float(self.cfg.disp_scale_min),
                        min(float(self.cfg.disp_scale_max), disp_scale_eff),
                    )
                    a_new = expm_sym((gain_eff * disp_scale_eff) * log_a)

                strength_spec = max(
                    0.0, min(1.0, float(self.cfg.lr) * float(self.cfg.lambda_spec))
                )
                if strength_spec > 0:
                    a_new = _shrink_log_spectrum(eigh_sym(a_new), strength=strength_spec)

                if float(self.cfg.lambda_u) > 0:
                    decomp_u = eigh_sym(a_new)
                    values = clamp_eigenvalues(decomp_u.values, 1e-30)
                    log_vals = np.log(values)
                    log_vals = (1.0 - float(self.cfg.lr) * float(self.cfg.lambda_u)) * log_vals
                    a_new = decomp_u.vectors @ np.diag(np.exp(log_vals)) @ decomp_u.vectors.T

                alpha = float(self.cfg.ema_alpha)
                if alpha <= 0.0:
                    a_ref = identity
                elif alpha >= 1.0:
                    a_ref = sym(a_new)
                elif self.cfg.a_mix_mode == "euclid":
                    a_ref = sym((1.0 - alpha) * identity + alpha * a_new)
                elif self.cfg.a_mix_mode == "log":
                    a_ref = expm_sym(alpha * logm_spd(sym(a_new), eps=self.cov_cfg.epsilon))
                else:
                    raise ValueError(f"Unknown IFSA a_mix_mode={self.cfg.a_mix_mode!r}")
            else:
                # Euclid interpolation (avoid logm on non-symmetric matrices).
                a_new = (1.0 - gain_eff) * identity + gain_eff * a_full

                alpha = float(self.cfg.ema_alpha)
                if alpha <= 0.0:
                    a_ref = identity
                elif alpha >= 1.0:
                    a_ref = a_new
                else:
                    a_ref = (1.0 - alpha) * identity + alpha * a_new

        mean_white = _mean_whitened_cov(
            a_ref,
            covs_smooth,
            w_ref,
            mean_mode=str(self.cfg.mean_mode),
            eps=self.cov_cfg.epsilon,
        )
        error1 = logm_spd(
            sym(desired_inv_sqrt @ mean_white @ desired_inv_sqrt),
            eps=self.cov_cfg.epsilon,
        )
        track_error_after = float(np.linalg.norm(error1, ord="fro"))

        a_out = a_ref
        if self.cfg.output_space == "reference":
            pass
        elif self.cfg.output_space == "identity":
            a_out = _project_spd(w_ref @ a_ref, eps=self.cov_cfg.epsilon)
        else:
            raise ValueError(f"Unknown IFSA output_space={self.cfg.output_space!r}")

        if want_disp:
            disp_after = self._dispersion(
                a_ref,
                covs_smooth,
                w_ref=w_ref,
                desired_inv_sqrt=desired_inv_sqrt,
            )

        covs_aligned = np.einsum("ij,njk,lk->nil", a_out, covs_raw, a_out)
        spec_var_before = float(
            np.mean([np.var(log_eigvals_spd(cov, self.cov_cfg.epsilon)) for cov in covs_raw])
        )
        spec_var_after = float(
            np.mean(
                [np.var(log_eigvals_spd(cov, self.cov_cfg.epsilon)) for cov in covs_aligned]
            )
        )
        control_energy = float(np.linalg.norm(a_out - identity, ord="fro"))

        self.matrix = a_out
        self.metrics = IFSAMetrics(
            spec_var_before=spec_var_before,
            spec_var_after=spec_var_after,
            control_energy=control_energy,
            track_error_before=track_error_before,
            track_error_after=track_error_after,
            triggered=int(triggered),
            trigger_tau_eff=float(self.cfg.trigger_tau),
            dispersion_target=float(disp_target),
            dispersion_before=float(disp_before),
            dispersion_after=float(disp_after),
            dispersion_scale_eff=float(disp_scale_eff),
        )
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        if self.matrix is None:
            raise RuntimeError("IFSASignalAligner not fit")
        return np.einsum("ij,njt->nit", self.matrix, x)
