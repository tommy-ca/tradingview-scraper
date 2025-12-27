# pyright: reportGeneralTypeIssues=false
import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, leaves_list, linkage
from scipy.spatial.distance import squareform
from sklearn.covariance import LedoitWolf

from tradingview_scraper.regime import MarketRegimeDetector


def winsorize(df: pd.DataFrame, alpha: float) -> pd.DataFrame:
    if alpha <= 0:
        return df
    lower = df.quantile(alpha, axis=0)
    upper = df.quantile(1 - alpha, axis=0)
    return df.clip(lower=lower, upper=upper, axis=1)


def load_returns(path: Path, min_col_frac: float) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Returns file not found: {path}")
    rets = pd.read_pickle(path)
    # Drop columns with too many NaNs
    min_count = int(min_col_frac * len(rets))
    rets = rets.dropna(axis=1, thresh=int(min_count))  # type: ignore[arg-type]
    rets = rets.dropna(axis=0)
    # Drop zero-variance cols
    var = rets.var()
    rets = rets.loc[:, var > 0]
    return rets


def rolling_avg_corr(rets: pd.DataFrame, window: int) -> pd.Series:
    if len(rets) < window:
        return pd.Series(dtype=float)
    roll = rets.rolling(window).corr()
    # average pairwise per window
    avg = roll.groupby(level=0).mean().mean(axis=1)
    return pd.Series(avg, dtype=float)


def top_corr_pairs(corr: pd.DataFrame, cap: float, limit: int) -> List[Tuple[str, str, float]]:
    symbols = list(corr.columns)
    corr_abs = corr.abs().to_numpy()
    out: List[Tuple[str, str, float]] = []
    seen = set()
    for i in range(len(symbols)):
        for j in range(i):
            v = float(corr_abs[i, j])
            if v < cap:
                continue
            key = (symbols[i], symbols[j])
            if key in seen:
                continue
            seen.add(key)
            out.append((symbols[i], symbols[j], v))
    out.sort(key=lambda x: x[2], reverse=True)
    return out[:limit]


def hrp_weights(rets: pd.DataFrame, linkage_method: str) -> pd.Series:
    if rets.shape[1] == 0:
        return pd.Series(dtype=float)

    cov = rets.cov().to_numpy()
    corr = rets.corr().to_numpy()
    dist = np.sqrt(0.5 * (np.ones_like(corr) - corr))
    condensed = squareform(dist, checks=False)
    link = linkage(condensed, method=linkage_method)
    order = leaves_list(link)
    ordered_cols = rets.columns[order]

    def get_ivp(cov_sub: np.ndarray) -> np.ndarray:
        inv_diag = 1 / np.diag(cov_sub)
        return inv_diag / inv_diag.sum()

    def cluster_var(cov_mat: np.ndarray, idxs: List[int]) -> float:
        sub = cov_mat[np.ix_(idxs, idxs)]
        ivp = get_ivp(sub)
        return float(ivp.T @ sub @ ivp)

    weights = pd.Series(1.0, index=ordered_cols)
    clusters: List[List[int]] = [list(range(len(ordered_cols)))]
    while clusters:
        cluster = clusters.pop(0)
        if len(cluster) <= 1:
            continue
        mid = len(cluster) // 2
        left, right = cluster[:mid], cluster[mid:]
        var_left = cluster_var(cov, left)
        var_right = cluster_var(cov, right)
        alloc_left = var_right / (var_left + var_right)
        alloc_right = var_left / (var_left + var_right)
        weights.iloc[left] *= alloc_left
        weights.iloc[right] *= alloc_right
        clusters.extend([left, right])

    return weights / weights.sum()


def main():
    parser = argparse.ArgumentParser(description="Generate correlation/HRP report")
    parser.add_argument("--returns", default="data/lakehouse/portfolio_returns.pkl")
    parser.add_argument("--out-dir", default="summaries")
    parser.add_argument("--pair-cap", type=float, default=0.85)
    parser.add_argument("--pair-limit", type=int, default=20)
    parser.add_argument("--winsor-alpha", type=float, default=0.0)
    parser.add_argument("--min-col-frac", type=float, default=0.9)
    parser.add_argument("--windows", default="20,60,180")
    parser.add_argument("--regime-z", type=float, default=1.5)
    parser.add_argument("--linkage", default="average")
    parser.add_argument("--hrp", action="store_true", help="Emit HRP weights")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rets = load_returns(Path(args.returns), args.min_col_frac)
    if args.winsor_alpha > 0:
        rets = winsorize(rets, args.winsor_alpha)

    windows = [int(w) for w in args.windows.split(",") if w.strip()]
    avg_corr = {w: rolling_avg_corr(rets, w) for w in windows}
    regime = {}
    for w, series in avg_corr.items():
        if series.empty:
            regime[w] = {"z": None, "flag": False}
            continue
        z = (series.iloc[-1] - series.mean()) / (series.std() + 1e-9)
        regime[w] = {"z": float(z), "flag": bool(abs(z) >= args.regime_z)}

    # Multi-Factor Regime Detection
    detector = MarketRegimeDetector()
    regime_name, regime_score = detector.detect_regime(rets)
    logger_msg = f"Regime Detected: {regime_name} (Score: {regime_score:.2f})"
    print(logger_msg)

    # Adaptive Clustering Threshold
    # CRISIS: t=0.3 (High diversification), NORMAL: t=0.4, QUIET: t=0.5 (Broader buckets)
    dist_threshold = 0.4
    if regime_name == "CRISIS":
        dist_threshold = 0.3
    elif regime_name == "QUIET":
        dist_threshold = 0.5

    lw = LedoitWolf().fit(rets.values)
    cov = lw.covariance_
    diag = np.sqrt(np.diag(cov))
    shrunk_corr = pd.DataFrame(cov / np.outer(diag, diag), index=rets.columns, columns=rets.columns)

    top_pairs = top_corr_pairs(shrunk_corr, args.pair_cap, args.pair_limit)

    report: Dict[str, object] = {
        "params": {
            "pair_cap": args.pair_cap,
            "pair_limit": args.pair_limit,
            "winsor_alpha": args.winsor_alpha,
            "min_col_frac": args.min_col_frac,
            "windows": windows,
            "regime_z": args.regime_z,
            "linkage": args.linkage,
            "hrp": args.hrp,
            "dist_threshold": dist_threshold,
        },
        "n_assets": rets.shape[1],
        "avg_corr": {w: avg_corr[w].iloc[-1] if not avg_corr[w].empty else None for w in windows},
        "regime": {"name": regime_name, "score": regime_score},
        "top_pairs": top_pairs,
    }

    if args.hrp and rets.shape[1] > 1:
        w_hrp = hrp_weights(rets, args.linkage)
        report["hrp_weights"] = w_hrp.to_dict()

        # Extract clusters
        corr = rets.corr().to_numpy()
        dist = np.sqrt(0.5 * (np.ones_like(corr) - corr))
        condensed = squareform(dist, checks=False)
        link = linkage(condensed, method=args.linkage)

        # Form flat clusters based on ADAPTIVE distance threshold
        cluster_assignments = fcluster(link, t=dist_threshold, criterion="distance")

        clusters = {}
        for sym, cluster_id in zip(rets.columns, cluster_assignments):
            c_id = int(cluster_id)
            if c_id not in clusters:
                clusters[c_id] = []
            clusters[c_id].append(sym)

        report["clusters"] = clusters

        # Save cluster mapping for the optimizer
        cluster_path = Path("data/lakehouse/portfolio_clusters.json")
        with open(cluster_path, "w") as f:
            json.dump(clusters, f, indent=2)
        print(f"Saved {len(clusters)} clusters to {cluster_path}")

    json_path = out_dir / "correlation_report.json"
    json_path.write_text(json.dumps(report, indent=2))

    # Markdown summary
    lines = ["# Correlation Report", "", f"Assets: {rets.shape[1]}", ""]
    lines.append(f"## Multi-Factor Regime: {regime_name} (Score: {regime_score:.2f})")
    lines.append(f"Applied Clustering Threshold: t={dist_threshold}")
    lines.append("")
    lines.append("## Rolling Correlations (avg corr, z >= %.2f)" % args.regime_z)
    for w in windows:
        rc = regime[w]
        lines.append(f"- Window {w}d: z={rc['z']}, flag={rc['flag']}")
    lines.append("")
    lines.append("## Top pairs (|corr| >= %.2f)" % args.pair_cap)
    for a, b, v in top_pairs:
        lines.append(f"- {a} / {b}: {v:.3f}")
    if args.hrp and rets.shape[1] > 1:
        lines.append("")
        lines.append("## HRP Weights")
        hrp_dict = report.get("hrp_weights")
        if isinstance(hrp_dict, dict):
            for sym, w in sorted(hrp_dict.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- {sym}: {w:.4f}")
    md_path = out_dir / "correlation_report.md"
    md_path.write_text("\n".join(lines))


if __name__ == "__main__":
    main()
