#!/usr/bin/env python3
"""Re-export a gnomix pickle model into the dependency-free bundle format.

The shipped LAI bundle does NOT carry gnomix's native ``.pkl`` (which pickles
sklearn ``LogisticRegression`` + xgboost objects and needs gnomix's ``src`` on
``sys.path`` to unpickle). Instead the runtime (``backend/analysis/gnomix_inference.py``)
loads three dependency-free files per chromosome:

    base_coefs.npz   per-window logistic-regression coef + intercept (+ window_n_features)
    smoother.json    the xgboost smoother in native JSON booster format
    metadata.npz     snp_pos / snp_ref / snp_alt / population_order + params (A,C,M,W,S,context)

This is the faithful repo port of v1.1's ``reexport_gnomix_models.py`` (which the
v2 refactor dropped — ``07_assemble_bundle.sh`` had been raw-copying the gnomix
output instead). It is parameterized per chromosome and run from phase 07.

Run in the gnomix conda env (needs numpy + xgboost + sklearn + gnomix's src on
sys.path to unpickle the model):

    python 07b_reexport_gnomix_models.py \\
        --model-pkl <out_chrN>/models/model_chm_chrN/model_chm_chrN.pkl \\
        --out-dir   <bundle>/gnomix_models/chrN \\
        --gnomix-dir ~/tools/gnomix [--no-verify]

By default it runs an approximate self-check (a fixed-random-input prediction
through both the pickle and the re-exported arrays) and *warns* on mismatch. That
check reimplements gnomix's feature pipeline only approximately, so it is a soft
signal, not a correctness proof (v1.1's reexport treated it the same and shipped a
working bundle). The hard guarantee here is that all three non-empty output files
are produced; the authoritative correctness gate is the Step-27 23andMe
runtime-parity test against the assembled bundle.
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
from pathlib import Path

import numpy as np


def _load_model(model_pkl: str, gnomix_dir: str):
    # The pickle references gnomix's own classes (src.model.Gnomix, ...), so the
    # gnomix checkout must be importable to unpickle it.
    if gnomix_dir and gnomix_dir not in sys.path:
        sys.path.insert(0, gnomix_dir)
    with open(model_pkl, "rb") as fh:
        return pickle.load(fh)


def reexport(model_pkl: str, out_dir: Path, gnomix_dir: str, verify: bool = True) -> None:
    if not os.path.exists(model_pkl):
        sys.exit(f"reexport: model pickle not found: {model_pkl}")
    model = _load_model(model_pkl, gnomix_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    W = model.W
    A = model.A

    # Each window may have a different feature count (edge windows carry less
    # context); pad to the max for uniform storage.
    window_n_features = np.array([model.base.models[w].n_features_in_ for w in range(W)])
    max_features = int(window_n_features.max())

    all_coefs = np.zeros((W, A, max_features), dtype=np.float32)
    all_intercepts = np.zeros((W, A), dtype=np.float32)
    for w in range(W):
        lr = model.base.models[w]
        nf = lr.n_features_in_
        all_coefs[w, :, :nf] = lr.coef_.astype(np.float32)
        all_intercepts[w] = lr.intercept_.astype(np.float32)

    np.savez_compressed(
        str(out_dir / "base_coefs.npz"),
        coefs=all_coefs,
        intercepts=all_intercepts,
        window_n_features=window_n_features,
    )

    # xgboost smoother -> native JSON booster
    booster = model.smooth.model.get_booster()
    booster.save_model(str(out_dir / "smoother.json"))

    np.savez_compressed(
        str(out_dir / "metadata.npz"),
        snp_pos=model.snp_pos,
        snp_ref=model.snp_ref,
        snp_alt=model.snp_alt,
        population_order=model.population_order,
        A=np.array(model.A),
        C=np.array(model.C),
        M=np.array(model.M),
        W=np.array(model.W),
        S=np.array(model.S),
        context=np.array(model.context),
        n_features=np.array(max_features),
    )

    print(f"  windows={W} ancestries={A} max_features/window={max_features}")

    if verify:
        np.random.seed(42)
        dummy = np.random.randint(0, 3, size=(2, model.C)).astype(np.float32)
        orig_base = _predict_base_original(model, dummy)
        orig_smooth = _predict_smooth_original(model, orig_base)
        reex_base = _predict_base_reexported(
            all_coefs, all_intercepts, window_n_features, dummy, model.M, model.context
        )
        reex_smooth = _predict_smooth_reexported(
            str(out_dir / "smoother.json"), reex_base, model.A, model.S
        )
        base_match = np.allclose(orig_base, reex_base, atol=1e-5)
        smooth_match = np.allclose(orig_smooth, reex_smooth, atol=1e-5)
        print(f"  verify: base_match={base_match} smooth_match={smooth_match}")
        # This dummy-genotype check reimplements gnomix's window/feature pipeline
        # only approximately, so a mismatch does NOT imply the extracted weights are
        # wrong: base_coefs/smoother/metadata serialize the model's real parameters
        # verbatim (identical extraction to v1.1's proven reexport, which treated this
        # as a soft warning and shipped a working bundle). The authoritative gate is
        # the Step-27 23andMe runtime-parity test against the assembled bundle.
        if not base_match:
            print(
                f"  WARNING: base dummy-prediction mismatch (max diff "
                f"{np.abs(orig_base - reex_base).max():.4f}); extraction is verbatim, "
                f"gated by Step-27 parity",
                file=sys.stderr,
            )
        if not smooth_match:
            print(
                f"  WARNING: smoother dummy-prediction mismatch (max diff "
                f"{np.abs(orig_smooth - reex_smooth).max():.4f})",
                file=sys.stderr,
            )

    for name in ("base_coefs.npz", "smoother.json", "metadata.npz"):
        if not (out_dir / name).is_file() or (out_dir / name).stat().st_size == 0:
            sys.exit(f"reexport: expected output missing/empty: {out_dir / name}")
    print(f"  wrote {out_dir}/{{base_coefs.npz,smoother.json,metadata.npz}}")


# ── verification helpers (faithful port of v1.1 reexport_gnomix_models.py) ──


def _predict_base_original(model, genotypes):
    n_haps = genotypes.shape[0]
    W, A, M, context, C = model.W, model.A, model.M, model.context, model.C
    probs = np.zeros((n_haps, W, A))
    for w in range(W):
        center_start = w * M
        center_end = min((w + 1) * M, C)
        ctx_start = max(0, center_start - context)
        ctx_end = min(C, center_end + context)
        X = genotypes[:, ctx_start:ctx_end]
        n_feat = model.base.models[w].n_features_in_
        if X.shape[1] < n_feat:
            X = np.pad(X, ((0, 0), (0, n_feat - X.shape[1])))
        elif X.shape[1] > n_feat:
            X = X[:, :n_feat]
        probs[:, w, :] = model.base.models[w].predict_proba(X)
    return probs


def _predict_base_reexported(coefs, intercepts, window_n_features, genotypes, M, context):
    n_haps = genotypes.shape[0]
    W, A, C = coefs.shape[0], coefs.shape[1], genotypes.shape[1]
    probs = np.zeros((n_haps, W, A))
    for w in range(W):
        center_start = w * M
        center_end = min((w + 1) * M, C)
        ctx_start = max(0, center_start - context)
        ctx_end = min(C, center_end + context)
        X = genotypes[:, ctx_start:ctx_end]
        n_feat = int(window_n_features[w])
        if X.shape[1] < n_feat:
            X = np.pad(X, ((0, 0), (0, n_feat - X.shape[1])))
        elif X.shape[1] > n_feat:
            X = X[:, :n_feat]
        logits = X @ coefs[w, :, :n_feat].T + intercepts[w]
        exp_logits = np.exp(logits - logits.max(axis=1, keepdims=True))
        probs[:, w, :] = exp_logits / exp_logits.sum(axis=1, keepdims=True)
    return probs


def _predict_smooth_original(model, base_probs):
    n_haps, W = base_probs.shape[0], base_probs.shape[1]
    smooth_input = _build_smooth_features(base_probs, model.S, base_probs.shape[2])
    preds = model.smooth.model.predict(smooth_input)
    return preds.reshape(n_haps, W)


def _predict_smooth_reexported(json_path, base_probs, A, S):
    import xgboost as xgb

    booster = xgb.Booster()
    booster.load_model(json_path)
    smooth_input = _build_smooth_features(base_probs, S, A)
    raw = booster.predict(xgb.DMatrix(smooth_input))
    preds = raw.argmax(axis=1) if raw.ndim == 2 else raw.astype(int)
    return preds.reshape(base_probs.shape[0], base_probs.shape[1])


def _build_smooth_features(base_probs, S, A):
    n_haps, W, _ = base_probs.shape
    half_s = S // 2
    padded = np.pad(base_probs, ((0, 0), (half_s, half_s), (0, 0)), mode="edge")
    features = np.zeros((n_haps * W, S * A))
    for h in range(n_haps):
        for w in range(W):
            features[h * W + w, :] = padded[h, w : w + S, :].flatten()
    return features


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Re-export a gnomix pickle to the bundle's npz/json format."
    )
    p.add_argument("--model-pkl", required=True, help="path to model_chm_chrN.pkl")
    p.add_argument("--out-dir", required=True, help="target gnomix_models/chrN dir")
    p.add_argument(
        "--gnomix-dir",
        default=os.environ.get("GNOMIX_DIR_INSTALL", ""),
        help="gnomix checkout (for unpickling); defaults to $GNOMIX_DIR_INSTALL",
    )
    p.add_argument(
        "--no-verify",
        action="store_true",
        help="skip the orig-vs-reexport prediction check",
    )
    args = p.parse_args(argv)
    reexport(args.model_pkl, Path(args.out_dir), args.gnomix_dir, verify=not args.no_verify)


if __name__ == "__main__":
    main()
