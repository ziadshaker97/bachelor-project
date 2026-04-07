from app.seed import load_doc2dial_behaviors, load_doc2dial_examples, load_documents, load_oulad_profiles, load_oulad_splits
from app.services.retrieval import RetrievalService
from app.services.preprocessing import (
    prepare_doc2dial_artifacts,
    prepare_doc2dial_behavior_artifacts,
    prepare_oulad_artifacts,
    validate_doc2dial_raw,
    validate_oulad_raw,
)


def test_documents_are_loaded() -> None:
    documents = load_documents()
    assert len(documents) >= 5


def test_retrieval_returns_ranked_chunks() -> None:
    service = RetrievalService()
    results = service.retrieve("How do I submit leave during onboarding?")
    assert results
    assert any("leave" in item.snippet.lower() for item in results)


def test_preprocessing_outputs_normalized_records(tmp_path) -> None:
    validate_oulad_raw()
    output = tmp_path / "profiles.json"
    records = prepare_oulad_artifacts(output=output)
    assert output.exists()
    assert records[0]["normalized_engagement_score"] > 0


def test_doc2dial_preprocessing_outputs_examples(tmp_path) -> None:
    validate_doc2dial_raw()
    output = tmp_path / "doc2dial.json"
    records = prepare_doc2dial_artifacts(output=output)
    assert output.exists()
    assert records[0]["question"]
    assert records[0]["answer_style"]

    behavior_output = tmp_path / "doc2dial_behaviors.json"
    behavior_records = prepare_doc2dial_behavior_artifacts(source_examples=records, output=behavior_output)
    assert behavior_output.exists()
    assert behavior_records[0]["behavior_type"]


def test_runtime_loaders_read_processed_artifacts() -> None:
    assert load_oulad_profiles()
    assert load_doc2dial_examples()
    assert load_doc2dial_behaviors()
    assert load_oulad_splits()
