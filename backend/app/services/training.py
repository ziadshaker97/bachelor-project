from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..config import (
    OULAD_TRAINING_FILE,
    RECOMMENDATION_MODEL_FILE,
    SUCCESS_MODEL_FILE,
    TRAINING_REPORT_FILE,
)


HASH_DIMENSION = 256
TRAIN_SPLIT_RATIO = 0.8
CLASSIFIER_EPOCHS = 8
REGRESSOR_EPOCHS = 10
CLASSIFIER_LEARNING_RATE = 0.05
REGRESSOR_LEARNING_RATE = 0.001
L2_REGULARIZATION = 1e-4
REGRESSOR_GRADIENT_CLIP = 1.0


@dataclass
class DatasetSplit:
    train: list[dict]
    test: list[dict]


@dataclass
class Preprocessor:
    numeric_features: list[str]
    categorical_features: list[str]
    numeric_means: dict[str, float]
    numeric_stds: dict[str, float]
    hash_dimension: int = HASH_DIMENSION

    @property
    def dimension(self) -> int:
        return len(self.numeric_features) + self.hash_dimension

    def transform(self, example: dict) -> dict[int, float]:
        vector: dict[int, float] = {}
        features = example["features"]

        for index, feature_name in enumerate(self.numeric_features):
            value = features.get(feature_name, 0.0)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                value = 0.0
            mean = self.numeric_means[feature_name]
            std = self.numeric_stds[feature_name]
            normalized = (float(value) - mean) / std if std else 0.0
            if normalized:
                vector[index] = normalized

        for feature_name in self.categorical_features:
            raw_value = features.get(feature_name, "")
            token = f"{feature_name}={raw_value}"
            hashed_index = len(self.numeric_features) + (_stable_hash(token) % self.hash_dimension)
            vector[hashed_index] = vector.get(hashed_index, 0.0) + 1.0

        return vector


def _stable_hash(value: str) -> int:
    return int(hashlib.md5(value.encode("utf-8")).hexdigest(), 16)


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _dot(weights: list[float], vector: dict[int, float]) -> float:
    return sum(weights[index] * value for index, value in vector.items())


def _squared_error(prediction: float, target: float) -> float:
    diff = prediction - target
    return diff * diff


def _clip(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _load_training_examples(path: Path = OULAD_TRAINING_FILE) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _split_examples(examples: list[dict], train_ratio: float = TRAIN_SPLIT_RATIO) -> DatasetSplit:
    ordered = sorted(examples, key=lambda item: item["example_id"])
    train: list[dict] = []
    test: list[dict] = []
    threshold = int(train_ratio * 10_000)
    for example in ordered:
        bucket = _stable_hash(example["example_id"]) % 10_000
        if bucket < threshold:
            train.append(example)
        else:
            test.append(example)
    if not train or not test:
        pivot = max(1, int(len(ordered) * train_ratio))
        train = ordered[:pivot]
        test = ordered[pivot:]
    return DatasetSplit(train=train, test=test)


def _build_preprocessor(train_examples: list[dict]) -> Preprocessor:
    first_features = train_examples[0]["features"]
    numeric_features = sorted(
        name for name, value in first_features.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    )
    categorical_features = sorted(
        name for name, value in first_features.items()
        if isinstance(value, str)
    )

    numeric_means: dict[str, float] = {}
    numeric_stds: dict[str, float] = {}
    for feature_name in numeric_features:
        values = [float(example["features"].get(feature_name, 0.0)) for example in train_examples]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        std = math.sqrt(variance) or 1.0
        numeric_means[feature_name] = mean
        numeric_stds[feature_name] = std

    return Preprocessor(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        numeric_means=numeric_means,
        numeric_stds=numeric_stds,
    )


def _train_logistic_regression(
    train_examples: list[dict],
    preprocessor: Preprocessor,
    target_key: str = "success",
) -> tuple[dict, dict]:
    weights = [0.0] * preprocessor.dimension
    bias = 0.0

    for _ in range(CLASSIFIER_EPOCHS):
        for example in train_examples:
            vector = preprocessor.transform(example)
            target = float(example["labels"][target_key])
            prediction = _sigmoid(_dot(weights, vector) + bias)
            gradient = prediction - target
            for index, value in vector.items():
                weights[index] -= CLASSIFIER_LEARNING_RATE * (gradient * value + L2_REGULARIZATION * weights[index])
            bias -= CLASSIFIER_LEARNING_RATE * gradient

    artifact = {
        "model_type": "logistic_regression_sgd",
        "target": target_key,
        "weights": weights,
        "bias": bias,
        "preprocessor": {
            "numeric_features": preprocessor.numeric_features,
            "categorical_features": preprocessor.categorical_features,
            "numeric_means": preprocessor.numeric_means,
            "numeric_stds": preprocessor.numeric_stds,
            "hash_dimension": preprocessor.hash_dimension,
        },
        "training": {
            "epochs": CLASSIFIER_EPOCHS,
            "learning_rate": CLASSIFIER_LEARNING_RATE,
            "l2_regularization": L2_REGULARIZATION,
        },
    }
    metrics = _evaluate_classifier(train_examples, weights, bias, preprocessor, target_key)
    return artifact, metrics


def _train_linear_regression(
    train_examples: list[dict],
    preprocessor: Preprocessor,
    target_key: str = "recommendation_score",
) -> tuple[dict, dict]:
    weights = [0.0] * preprocessor.dimension
    bias = 0.0

    for _ in range(REGRESSOR_EPOCHS):
        for example in train_examples:
            vector = preprocessor.transform(example)
            target = float(example["labels"][target_key])
            prediction = _dot(weights, vector) + bias
            gradient = _clip(prediction - target, -REGRESSOR_GRADIENT_CLIP, REGRESSOR_GRADIENT_CLIP)
            for index, value in vector.items():
                weights[index] -= REGRESSOR_LEARNING_RATE * (gradient * value + L2_REGULARIZATION * weights[index])
            bias -= REGRESSOR_LEARNING_RATE * gradient

    artifact = {
        "model_type": "linear_regression_sgd",
        "target": target_key,
        "weights": weights,
        "bias": bias,
        "preprocessor": {
            "numeric_features": preprocessor.numeric_features,
            "categorical_features": preprocessor.categorical_features,
            "numeric_means": preprocessor.numeric_means,
            "numeric_stds": preprocessor.numeric_stds,
            "hash_dimension": preprocessor.hash_dimension,
        },
        "training": {
            "epochs": REGRESSOR_EPOCHS,
            "learning_rate": REGRESSOR_LEARNING_RATE,
            "l2_regularization": L2_REGULARIZATION,
        },
    }
    metrics = _evaluate_regressor(train_examples, weights, bias, preprocessor, target_key)
    return artifact, metrics


def _evaluate_classifier(
    examples: list[dict],
    weights: list[float],
    bias: float,
    preprocessor: Preprocessor,
    target_key: str,
) -> dict[str, float]:
    true_positive = 0
    false_positive = 0
    false_negative = 0
    true_negative = 0
    total_loss = 0.0

    for example in examples:
        vector = preprocessor.transform(example)
        target = float(example["labels"][target_key])
        probability = _sigmoid(_dot(weights, vector) + bias)
        total_loss += -(target * math.log(max(probability, 1e-9)) + (1 - target) * math.log(max(1 - probability, 1e-9)))
        prediction = 1 if probability >= 0.5 else 0
        if prediction == 1 and target == 1:
            true_positive += 1
        elif prediction == 1 and target == 0:
            false_positive += 1
        elif prediction == 0 and target == 1:
            false_negative += 1
        else:
            true_negative += 1

    total = len(examples) or 1
    accuracy = (true_positive + true_negative) / total
    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "log_loss": round(total_loss / total, 4),
    }


def _evaluate_regressor(
    examples: list[dict],
    weights: list[float],
    bias: float,
    preprocessor: Preprocessor,
    target_key: str,
) -> dict[str, float]:
    total_abs_error = 0.0
    total_sq_error = 0.0
    targets: list[float] = []

    for example in examples:
        vector = preprocessor.transform(example)
        target = float(example["labels"][target_key])
        prediction = _clip(_dot(weights, vector) + bias, 0.0, 1.0)
        targets.append(target)
        total_abs_error += abs(prediction - target)
        total_sq_error += _squared_error(prediction, target)

    total = len(examples) or 1
    target_mean = sum(targets) / len(targets) if targets else 0.0
    total_sum_squares = sum((target - target_mean) ** 2 for target in targets)
    r2 = 1.0 - (total_sq_error / total_sum_squares) if total_sum_squares else 0.0
    return {
        "mae": round(total_abs_error / total, 4),
        "rmse": round(math.sqrt(total_sq_error / total), 4),
        "r2": round(r2, 4),
    }


def _write_artifact(path: Path, payload: dict) -> None:
    _ensure_parent(path)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def train_oulad_models(
    dataset_path: Path = OULAD_TRAINING_FILE,
    success_model_path: Path = SUCCESS_MODEL_FILE,
    recommendation_model_path: Path = RECOMMENDATION_MODEL_FILE,
    report_path: Path = TRAINING_REPORT_FILE,
) -> dict:
    examples = _load_training_examples(dataset_path)
    split = _split_examples(examples)
    preprocessor = _build_preprocessor(split.train)

    success_artifact, success_train_metrics = _train_logistic_regression(split.train, preprocessor, "success")
    success_test_metrics = _evaluate_classifier(split.test, success_artifact["weights"], success_artifact["bias"], preprocessor, "success")

    recommendation_artifact, recommendation_train_metrics = _train_linear_regression(
        split.train,
        preprocessor,
        "recommendation_score",
    )
    recommendation_test_metrics = _evaluate_regressor(
        split.test,
        recommendation_artifact["weights"],
        recommendation_artifact["bias"],
        preprocessor,
        "recommendation_score",
    )

    generated_at = datetime.now(timezone.utc).isoformat()
    success_artifact["generated_at"] = generated_at
    success_artifact["dataset"] = {
        "path": str(dataset_path),
        "train_examples": len(split.train),
        "test_examples": len(split.test),
    }
    success_artifact["metrics"] = {
        "train": success_train_metrics,
        "test": success_test_metrics,
    }

    recommendation_artifact["generated_at"] = generated_at
    recommendation_artifact["dataset"] = {
        "path": str(dataset_path),
        "train_examples": len(split.train),
        "test_examples": len(split.test),
    }
    recommendation_artifact["metrics"] = {
        "train": recommendation_train_metrics,
        "test": recommendation_test_metrics,
    }

    report = {
        "generated_at": generated_at,
        "dataset": {
            "path": str(dataset_path),
            "total_examples": len(examples),
            "train_examples": len(split.train),
            "test_examples": len(split.test),
        },
        "models": {
            "success_classifier": {
                "path": str(success_model_path),
                "model_type": success_artifact["model_type"],
                "target": "success",
                "metrics": success_artifact["metrics"],
            },
            "recommendation_regressor": {
                "path": str(recommendation_model_path),
                "model_type": recommendation_artifact["model_type"],
                "target": "recommendation_score",
                "metrics": recommendation_artifact["metrics"],
            },
        },
    }

    _write_artifact(success_model_path, success_artifact)
    _write_artifact(recommendation_model_path, recommendation_artifact)
    _write_artifact(report_path, report)
    return report
