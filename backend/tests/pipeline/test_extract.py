# Tests for extract_node and related functions in backend.pipeline
import pytest
import os
from unittest.mock import patch, MagicMock, call
from backend.pipeline import extract_node, GraphState # Assuming GraphState is defined appropriately

# Define a minimal valid GraphState for use in tests
def get_initial_state(
    resume_path: str | None = None,
    source_paths: list[str] | None = None,
    existing_error: str | None = None
) -> GraphState:
    return GraphState(
        client_id="test_client",
        resume_file_path=resume_path,
        source_document_paths=source_paths if source_paths is not None else [],
        source_document_texts=[], # Output field, initially empty
        resume_text=None,         # Output field, initially None
        roles_draft=None,         # Not used by extract_node
        error_message=existing_error,
        current_node_error=None   # Should be cleared/set by the node
    )

@patch('backend.pipeline.extract_text_from_file')
def test_extract_node_successful_extraction(mock_extract_text):
    """Test successful extraction of resume and multiple source documents."""
    mock_extract_text.side_effect = [
        "Resume text content.",
        "Source doc 1 text.",
        "Source doc 2 text."
    ]

    initial_state = get_initial_state(
        resume_path="dummy/resume.pdf",
        source_paths=["dummy/source1.txt", "dummy/source2.docx"]
    )

    output_state = extract_node(initial_state)

    assert output_state['resume_text'] == "Resume text content."
    assert output_state['source_document_texts'] == ["Source doc 1 text.", "Source doc 2 text."]
    assert output_state['current_node_error'] is None
    assert output_state['error_message'] is None # No initial error, no new error

    expected_calls = [
        call("dummy/resume.pdf"),
        call("dummy/source1.txt"),
        call("dummy/source2.docx")
    ]
    mock_extract_text.assert_has_calls(expected_calls, any_order=False)

@patch('backend.pipeline.extract_text_from_file')
def test_extract_node_with_some_failures(mock_extract_text):
    """Test extraction when some files fail and others succeed."""
    mock_extract_text.side_effect = [
        "Resume text content.",
        Exception("Failed to extract source1.txt"),
        "Source doc 2 text."
    ]

    initial_state = get_initial_state(
        resume_path="dummy/resume.pdf",
        source_paths=["dummy/source1.txt", "dummy/source2.docx"]
    )

    output_state = extract_node(initial_state)

    assert output_state['resume_text'] == "Resume text content."
    assert output_state['source_document_texts'] == ["", "Source doc 2 text."] # Empty string for failed extraction

    assert output_state['current_node_error'] is not None
    assert "Failed to extract source document 'dummy/source1.txt': Failed to extract source1.txt" in output_state['current_node_error']
    assert output_state['error_message'] == output_state['current_node_error']

@patch('backend.pipeline.extract_text_from_file')
def test_extract_node_no_resume_path(mock_extract_text):
    """Test behavior when resume_file_path is None."""
    initial_state = get_initial_state(
        resume_path=None,
        source_paths=["dummy/source1.txt"]
    )
    mock_extract_text.return_value = "Source doc 1 text." # For the source doc

    output_state = extract_node(initial_state)

    assert output_state['resume_text'] is None
    assert output_state['source_document_texts'] == ["Source doc 1 text."]
    # Current implementation of extract_node prints a message but doesn't set an error for missing resume.
    # If this behavior changes to be an error, this assertion should be updated.
    assert output_state['current_node_error'] is None
    assert output_state['error_message'] is None
    mock_extract_text.assert_called_once_with("dummy/source1.txt")


@patch('backend.pipeline.extract_text_from_file')
def test_extract_node_empty_resume_path(mock_extract_text):
    """Test behavior when resume_file_path is an empty string."""
    initial_state = get_initial_state(
        resume_path="", # Empty string
        source_paths=["dummy/source1.txt"]
    )
    mock_extract_text.return_value = "Source doc 1 text."

    output_state = extract_node(initial_state)

    assert output_state['resume_text'] is None # Should treat empty path as no resume
    assert output_state['source_document_texts'] == ["Source doc 1 text."]
    assert output_state['current_node_error'] is None
    assert output_state['error_message'] is None
    mock_extract_text.assert_called_once_with("dummy/source1.txt")


@patch('backend.pipeline.extract_text_from_file')
def test_extract_node_no_source_document_paths(mock_extract_text):
    """Test behavior when source_document_paths is an empty list."""
    initial_state = get_initial_state(
        resume_path="dummy/resume.pdf",
        source_paths=[] # Empty list
    )
    mock_extract_text.return_value = "Resume text content." # For the resume

    output_state = extract_node(initial_state)

    assert output_state['resume_text'] == "Resume text content."
    assert output_state['source_document_texts'] == []
    assert output_state['current_node_error'] is None
    assert output_state['error_message'] is None
    mock_extract_text.assert_called_once_with("dummy/resume.pdf")

@patch('backend.pipeline.extract_text_from_file')
def test_extract_node_error_accumulation(mock_extract_text):
    """Test that new errors are appended to existing error_message."""
    mock_extract_text.side_effect = [
        Exception("Failed to extract resume.pdf"),
        "Source doc 1 text." # This won't be reached if resume fails first and logic changes
    ]
    # For current extract_node, it tries all, so source doc will also be attempted.
    # Let's refine side_effect for clarity:
    mock_extract_text.side_effect = [
        Exception("Failed resume"), # For resume
        Exception("Failed source")  # For source1
    ]

    initial_state = get_initial_state(
        resume_path="dummy/resume.pdf",
        source_paths=["dummy/source1.txt"],
        existing_error="Previous error."
    )

    output_state = extract_node(initial_state)

    assert output_state['resume_text'] is None # Failed
    assert output_state['source_document_texts'] == [""] # Failed

    expected_current_error = (
        "Failed to extract resume 'dummy/resume.pdf': Failed resume; "
        "Failed to extract source document 'dummy/source1.txt': Failed source"
    )
    assert output_state['current_node_error'] == expected_current_error

    expected_accumulated_error = f"Previous error.; {expected_current_error}"
    assert output_state['error_message'] == expected_accumulated_error

@patch('backend.pipeline.extract_text_from_file')
def test_extract_node_all_extractions_fail(mock_extract_text):
    """Test when both resume and all source documents fail extraction."""
    mock_extract_text.side_effect = Exception("Universal extraction failure")

    initial_state = get_initial_state(
        resume_path="dummy/resume.pdf",
        source_paths=["dummy/source1.txt", "dummy/source2.docx"]
    )

    output_state = extract_node(initial_state)

    assert output_state['resume_text'] is None
    assert output_state['source_document_texts'] == ["", ""] # Empty strings for all failed source extractions

    assert output_state['current_node_error'] is not None
    assert "Failed to extract resume 'dummy/resume.pdf': Universal extraction failure" in output_state['current_node_error']
    assert "Failed to extract source document 'dummy/source1.txt': Universal extraction failure" in output_state['current_node_error']
    assert "Failed to extract source document 'dummy/source2.docx': Universal extraction failure" in output_state['current_node_error']

    assert output_state['error_message'] == output_state['current_node_error']

@patch('backend.pipeline.extract_text_from_file')
def test_extract_node_no_files_provided(mock_extract_text):
    """Test behavior when no resume and no source documents are provided."""
    initial_state = get_initial_state(
        resume_path=None,
        source_paths=[]
    )

    output_state = extract_node(initial_state)

    assert output_state['resume_text'] is None
    assert output_state['source_document_texts'] == []
    assert output_state['current_node_error'] is None # No attempt, no error by current logic
    assert output_state['error_message'] is None

    mock_extract_text.assert_not_called()
