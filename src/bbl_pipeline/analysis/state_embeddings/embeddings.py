from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from .evaluation import META_COLUMNS


def select_numeric_feature_columns(df: pd.DataFrame, extra_exclude: Sequence[str] | None = None) -> List[str]:
    exclude = set(META_COLUMNS)
    if extra_exclude:
        exclude.update(extra_exclude)
    numeric_cols = df.select_dtypes(include=[np.number, "bool"]).columns.tolist()
    return [column for column in numeric_cols if column not in exclude]


def fit_embedding_models(
    corpus_df: pd.DataFrame,
    train_mask: np.ndarray,
    output_dir: Path,
    seed: int = 42,
    pca_components: int = 12,
    n_clusters: int = 6,
) -> Tuple[pd.DataFrame, List[str], Dict[str, float]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_columns = select_numeric_feature_columns(corpus_df)
    if not feature_columns:
        raise ValueError("No numeric feature columns available for embedding fit")

    filled = corpus_df[feature_columns].fillna(0.0)
    train_df = filled.loc[train_mask]
    if len(train_df) < 10:
        raise ValueError("Need at least 10 training rows for PCA/KMeans fitting")

    scaler = StandardScaler()
    train_scaled = scaler.fit_transform(train_df)
    full_scaled = scaler.transform(filled)

    actual_components = max(1, min(pca_components, train_scaled.shape[1], train_scaled.shape[0] - 1))
    pca = PCA(n_components=actual_components, random_state=seed)
    train_embeddings = pca.fit_transform(train_scaled)
    full_embeddings = pca.transform(full_scaled)

    actual_clusters = max(2, min(n_clusters, len(train_embeddings)))
    kmeans = KMeans(n_clusters=actual_clusters, n_init=20, random_state=seed)
    kmeans.fit(train_embeddings)
    labels = kmeans.predict(full_embeddings)
    distances = kmeans.transform(full_embeddings)
    min_distance = distances.min(axis=1)
    confidence = 1.0 / (1.0 + min_distance)

    embedding_columns = [f"embedding_{idx}" for idx in range(actual_components)]
    assignments_df = corpus_df.copy()
    for index, column in enumerate(embedding_columns):
        assignments_df[column] = full_embeddings[:, index]
    assignments_df["regime_id"] = labels.astype(int)
    assignments_df["centroid_distance"] = min_distance.astype(float)
    assignments_df["regime_confidence"] = confidence.astype(float)
    assignments_df["fit_role"] = np.where(train_mask, "train", "validation")

    cluster_stats = (
        assignments_df.loc[train_mask]
        .groupby("regime_id")
        .agg(
            regime_cluster_win_rate=("is_winner", "mean"),
            regime_cluster_size=("row_key", "size"),
        )
        .reset_index()
    )
    assignments_df = assignments_df.merge(cluster_stats, on="regime_id", how="left")

    joblib.dump(scaler, output_dir / "scaler.joblib")
    joblib.dump(pca, output_dir / "pca.joblib")
    joblib.dump(kmeans, output_dir / "kmeans.joblib")

    explained_variance = {
        "pca_components": actual_components,
        "explained_variance_ratio_sum": float(np.sum(pca.explained_variance_ratio_)),
        "explained_variance_ratio": [float(value) for value in pca.explained_variance_ratio_],
    }
    (output_dir / "explained_variance.json").write_text(json.dumps(explained_variance, indent=2), encoding="utf-8")
    return assignments_df, feature_columns, explained_variance
