# Tests for extract_node and related functions in backend.pipeline
from unittest.mock import call, patch

from backend.pipeline import (
    GraphState,
    extract_node,
)


# Define a minimal valid GraphState for use in tests
def get_initial_state(
    resume_path: str | None = None,
    source_paths: list[str] | None = None,
    existing_error: str | None = None,
) -> GraphState:
    return GraphState(
        client_id="test_client",
        resume_file_path=resume_path,
        source_document_paths=source_paths if source_paths is not None else [],
        source_document_texts=[],  # Output field, initially empty
        resume_text=None,  # Output field, initially None
        roles_draft=None,  # Not used by extract_node
        error_message=existing_error,
        current_node_error=None,  # Should be cleared/set by the node
    )


@patch("backend.pipeline.extract_text_from_file")
def test_extract_node_successful_extraction(mock_extract_text):
    """Test successful extraction of resume and multiple source documents."""
    mock_extract_text.side_effect = [
        "Resume text content.",
        "Source doc 1 text.",
        "Source doc 2 text.",
    ]

    initial_state = get_initial_state(
        resume_path="dummy/resume.pdf",
        source_paths=["dummy/source1.txt", "dummy/source2.docx"],
    )

    output_state = extract_node(initial_state)

    assert output_state["resume_text"] == "Resume text content."
    assert output_state["source_document_texts"] == [
        "Source doc 1 text.",
        "Source doc 2 text.",
    ]
    assert output_state["current_node_error"] is None
    assert output_state["error_message"] is None  # No initial error, no new error

    expected_calls = [
        call("dummy/resume.pdf"),
        call("dummy/source1.txt"),
        call("dummy/source2.docx"),
    ]
    mock_extract_text.assert_has_calls(expected_calls, any_order=False)


@patch("backend.pipeline.extract_text_from_file")
def test_extract_node_with_some_failures(mock_extract_text):
    """Test extraction when some files fail and others succeed."""
    mock_extract_text.side_effect = [
        "Resume text content.",
        Exception("Failed to extract source1.txt"),
        "Source doc 2 text.",
    ]

    initial_state = get_initial_state(
        resume_path="dummy/resume.pdf",
        source_paths=["dummy/source1.txt", "dummy/source2.docx"],
    )

    output_state = extract_node(initial_state)

    assert output_state["resume_text"] == "Resume text content."
    assert output_state["source_document_texts"] == [
        "",
        "Source doc 2 text.",
    ]  # Empty string for failed extraction

    assert output_state["current_node_error"] is not None
    assert (
        "Failed to extract source document 'dummy/source1.txt': Failed to extract source1.txt"
        in output_state["current_node_error"]
    )
    assert output_state["error_message"] == output_state["current_node_error"]


@patch("backend.pipeline.extract_text_from_file")
def test_extract_node_no_resume_path(mock_extract_text):
    """Test behavior when resume_file_path is None."""
    initial_state = get_initial_state(
        resume_path=None, source_paths=["dummy/source1.txt"]
    )
    mock_extract_text.return_value = "Source doc 1 text."  # For the source doc

    output_state = extract_node(initial_state)

    assert output_state["resume_text"] is None
    assert output_state["source_document_texts"] == ["Source doc 1 text."]
    # Current implementation of extract_node prints a message but doesn't set an error for missing resume.
    # If this behavior changes to be an error, this assertion should be updated.
    assert output_state["current_node_error"] is None
    assert output_state["error_message"] is None
    mock_extract_text.assert_called_once_with("dummy/source1.txt")


@patch("backend.pipeline.extract_text_from_file")
def test_extract_node_empty_resume_path(mock_extract_text):
    """Test behavior when resume_file_path is an empty string."""
    initial_state = get_initial_state(
        resume_path="", source_paths=["dummy/source1.txt"]  # Empty string
    )
    mock_extract_text.return_value = "Source doc 1 text."

    output_state = extract_node(initial_state)

    assert output_state["resume_text"] is None  # Should treat empty path as no resume
    assert output_state["source_document_texts"] == ["Source doc 1 text."]
    assert output_state["current_node_error"] is None
    assert output_state["error_message"] is None
    mock_extract_text.assert_called_once_with("dummy/source1.txt")


@patch("backend.pipeline.extract_text_from_file")
def test_extract_node_no_source_document_paths(mock_extract_text):
    """Test behavior when source_document_paths is an empty list."""
    initial_state = get_initial_state(
        resume_path="dummy/resume.pdf", source_paths=[]  # Empty list
    )
    mock_extract_text.return_value = "Resume text content."  # For the resume

    output_state = extract_node(initial_state)

    assert output_state["resume_text"] == "Resume text content."
    assert output_state["source_document_texts"] == []
    assert output_state["current_node_error"] is None
    assert output_state["error_message"] is None
    mock_extract_text.assert_called_once_with("dummy/resume.pdf")


@patch("backend.pipeline.extract_text_from_file")
def test_extract_node_error_accumulation(mock_extract_text):
    """Test that new errors are appended to existing error_message."""
    mock_extract_text.side_effect = [
        Exception("Failed to extract resume.pdf"),
        "Source doc 1 text.",  # This won't be reached if resume fails first and logic changes
    ]
    # For current extract_node, it tries all, so source doc will also be attempted.
    # Let's refine side_effect for clarity:
    mock_extract_text.side_effect = [
        Exception("Failed resume"),  # For resume
        Exception("Failed source"),  # For source1
    ]

    initial_state = get_initial_state(
        resume_path="dummy/resume.pdf",
        source_paths=["dummy/source1.txt"],
        existing_error="Previous error.",
    )

    output_state = extract_node(initial_state)

    assert output_state["resume_text"] is None  # Failed
    assert output_state["source_document_texts"] == [""]  # Failed

    expected_current_error = (
        "Failed to extract resume 'dummy/resume.pdf': Failed resume; "
        "Failed to extract source document 'dummy/source1.txt': Failed source"
    )
    assert output_state["current_node_error"] == expected_current_error

    expected_accumulated_error = f"Previous error.; {expected_current_error}"
    assert output_state["error_message"] == expected_accumulated_error


@patch("backend.pipeline.extract_text_from_file")
def test_extract_node_all_extractions_fail(mock_extract_text):
    """Test when both resume and all source documents fail extraction."""
    mock_extract_text.side_effect = Exception("Universal extraction failure")

    initial_state = get_initial_state(
        resume_path="dummy/resume.pdf",
        source_paths=["dummy/source1.txt", "dummy/source2.docx"],
    )

    output_state = extract_node(initial_state)

    assert output_state["resume_text"] is None
    assert output_state["source_document_texts"] == [
        "",
        "",
    ]  # Empty strings for all failed source extractions

    assert output_state["current_node_error"] is not None
    assert (
        "Failed to extract resume 'dummy/resume.pdf': Universal extraction failure"
        in output_state["current_node_error"]
    )
    assert (
        "Failed to extract source document 'dummy/source1.txt': Universal extraction failure"
        in output_state["current_node_error"]
    )
    assert (
        "Failed to extract source document 'dummy/source2.docx': Universal extraction failure"
        in output_state["current_node_error"]
    )

    assert output_state["error_message"] == output_state["current_node_error"]


@patch("backend.pipeline.extract_text_from_file")
def test_extract_node_no_files_provided(mock_extract_text):
    """Test behavior when no resume and no source documents are provided."""
    initial_state = get_initial_state(resume_path=None, source_paths=[])

    output_state = extract_node(initial_state)

    assert output_state["resume_text"] is None
    assert output_state["source_document_texts"] == []
    assert (
        output_state["current_node_error"] is None
    )  # No attempt, no error by current logic
    assert output_state["error_message"] is None

    mock_extract_text.assert_not_called()


# --- Tests for extract_text_from_file ---
import pytest
import os # For os.path.exists mock
import mimetypes # For mimetypes.guess_type mock
from unittest.mock import MagicMock, mock_open

from backend.pipeline import extract_text_from_file # The function to test
# FileNotFoundError and OSError are built-in but importing for clarity if needed for specific checks
# from backend.pipeline import FileNotFoundError, OSError


# Helper to create mock Unstructured elements
def create_mock_unstructured_element(text_content: str):
    el = MagicMock()
    el.text = text_content
    return el


@patch("backend.pipeline.os.path.exists", return_value=True)
@patch("backend.pipeline.mimetypes.guess_type", return_value=("application/pdf", None))
@patch("backend.pipeline.auto") # Patch the imported module 'auto'
def test_extract_text_unstructured_success(mock_auto_module, mock_guess_type, mock_exists):
    """4. Test successful extraction using unstructured.io."""
    mock_auto_module.partition_file.return_value = [create_mock_unstructured_element("Unstructured text")]
    result = extract_text_from_file("dummy.pdf")
    assert result == "Unstructured text"
    mock_auto_module.partition_file.assert_called_once_with(filename="dummy.pdf")


@patch("backend.pipeline.os.path.exists", return_value=True)
@patch("backend.pipeline.mimetypes.guess_type", return_value=("application/pdf", None))
@patch("backend.pipeline.auto") # Patch the imported module 'auto'
@patch("backend.pipeline.PdfReader")
def test_extract_text_pypdf_fallback_success_on_unstructured_exception(
    mock_pdf_reader, mock_auto_module, mock_guess_type, mock_exists
):
    """5. Test successful extraction using pypdf when unstructured.io fails."""
    mock_auto_module.partition_file.side_effect = Exception("Unstructured failed")
    mock_pdf_instance = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "PDF text"
    mock_pdf_instance.pages = [mock_page]
    mock_pdf_reader.return_value = mock_pdf_instance

    with patch("builtins.open", mock_open(read_data=b"dummy pdf data")) as mock_file_open:
        result = extract_text_from_file("dummy.pdf")
        assert result == "PDF text"
        mock_file_open.assert_called_once_with("dummy.pdf", "rb")
        mock_pdf_reader.assert_called_once_with(mock_file_open.return_value)


@patch("backend.pipeline.os.path.exists", return_value=True)
@patch("backend.pipeline.mimetypes.guess_type", return_value=("application/pdf", None))
@patch("backend.pipeline.auto") # Patch the imported module 'auto'
@patch("backend.pipeline.PdfReader")
def test_extract_text_pypdf_fallback_success_on_unstructured_empty(
    mock_pdf_reader, mock_auto_module, mock_guess_type, mock_exists
):
    """5. Test successful extraction using pypdf when unstructured.io returns empty."""
    mock_auto_module.partition_file.return_value = [] # Unstructured returns no elements
    mock_pdf_instance = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "PDF text from empty"
    mock_pdf_instance.pages = [mock_page]
    mock_pdf_reader.return_value = mock_pdf_instance

    with patch("builtins.open", mock_open(read_data=b"dummy pdf data")) as mock_file_open:
        result = extract_text_from_file("dummy.pdf")
        assert result == "PDF text from empty"
        mock_file_open.assert_called_once_with("dummy.pdf", "rb")


@patch("backend.pipeline.os.path.exists", return_value=True)
@patch(
    "backend.pipeline.mimetypes.guess_type",
    return_value=(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        None,
    ),
)
@patch("backend.pipeline.auto") # Patch the imported module 'auto'
@patch("backend.pipeline.Document") # Mock docx.Document
def test_extract_text_docx_fallback_success_on_unstructured_exception(
    mock_docx_document, mock_auto_module, mock_guess_type, mock_exists
):
    """6. Test successful extraction using python-docx when unstructured.io fails."""
    mock_auto_module.partition_file.side_effect = Exception("Unstructured failed")
    mock_doc_instance = MagicMock()
    mock_para1 = MagicMock()
    mock_para1.text = "Docx para 1"
    mock_para2 = MagicMock()
    mock_para2.text = "Docx para 2"
    mock_doc_instance.paragraphs = [mock_para1, mock_para2]
    mock_docx_document.return_value = mock_doc_instance

    result = extract_text_from_file("dummy.docx")
    assert result == "Docx para 1\nDocx para 2"
    mock_docx_document.assert_called_once_with("dummy.docx")


@patch("backend.pipeline.os.path.exists", return_value=True)
@patch(
    "backend.pipeline.mimetypes.guess_type",
    return_value=(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        None,
    ),
)
@patch("backend.pipeline.auto") # Patch the imported module 'auto'
@patch("backend.pipeline.Document") # Mock docx.Document
def test_extract_text_docx_fallback_success_on_unstructured_empty(
    mock_docx_document, mock_auto_module, mock_guess_type, mock_exists
):
    """6. Test successful extraction using python-docx when unstructured.io returns empty."""
    mock_auto_module.partition_file.return_value = [] # Unstructured returns no elements
    mock_doc_instance = MagicMock()
    mock_para1 = MagicMock()
    mock_para1.text = "Docx para 1 empty"
    mock_doc_instance.paragraphs = [mock_para1]
    mock_docx_document.return_value = mock_doc_instance

    result = extract_text_from_file("dummy.docx")
    assert result == "Docx para 1 empty"


@pytest.mark.parametrize(
    "file_ext, mime_type, expected_content",
    [
        (".txt", "text/plain", "Plain text content"),
        (".md", "text/markdown", "Markdown content"),
        (".html", "text/html", "HTML content"),
    ],
)
@patch("backend.pipeline.os.path.exists", return_value=True)
@patch("backend.pipeline.auto") # Patch the imported module 'auto'
def test_extract_text_direct_read_fallback_success(
    mock_auto_module, mock_exists, file_ext, mime_type, expected_content
):
    """7. Test direct read for .txt/.md/.html when unstructured fails."""
    mock_auto_module.partition_file.side_effect = Exception("Unstructured failed")
    file_path = f"dummy{file_ext}"

    with patch("backend.pipeline.mimetypes.guess_type", return_value=(mime_type, None)):
        with patch("builtins.open", mock_open(read_data=expected_content)) as mock_file:
            result = extract_text_from_file(file_path)
            assert result == expected_content
            mock_file.assert_called_once_with(file_path, encoding="utf-8", errors="ignore")


@patch("backend.pipeline.os.path.exists", return_value=True)
@patch("backend.pipeline.mimetypes.guess_type", return_value=("application/pdf", None))
@patch("backend.pipeline.auto") # Patch the imported module 'auto'
@patch("backend.pipeline.PdfReader")
def test_extract_text_unstructured_empty_then_pypdf_success(
    mock_pdf_reader, mock_auto_module, mock_guess_type, mock_exists
):
    """8. Test unstructured returns empty, then pypdf fallback is used."""
    mock_auto_module.partition_file.return_value = []  # Empty list of elements

    mock_pdf_instance = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "PDF text after empty unstructured"
    mock_pdf_instance.pages = [mock_page]
    mock_pdf_reader.return_value = mock_pdf_instance

    with patch("builtins.open", mock_open(read_data=b"dummy pdf data")) as mock_file_open:
        result = extract_text_from_file("dummy.pdf")
        assert result == "PDF text after empty unstructured"


@patch("backend.pipeline.os.path.exists", return_value=True)
@patch("backend.pipeline.mimetypes.guess_type", return_value=("application/unknown", None))
@patch("backend.pipeline.auto") # Patch the imported module 'auto'
def test_extract_text_unsupported_type_returns_empty_string(
    mock_auto_module, mock_guess_type, mock_exists, capsys
):
    """9. Test unsupported file type returns empty string and logs warning (no OSError)."""
    mock_auto_module.partition_file.side_effect = Exception("Unstructured failed")
    # Also test when unstructured returns empty
    # mock_auto_module.partition_file.return_value = []

    result = extract_text_from_file("dummy.xyz")
    assert result == ""

    # Check that it tried unstructured
    mock_auto_module.partition_file.assert_called_once_with(filename="dummy.xyz")

    # Check print output for the unsupported message
    captured = capsys.readouterr()
    assert "Unsupported file type for fallback: application/unknown for file dummy.xyz" in captured.out
    # Crucially, no OSError should be raised here by extract_text_from_file directly


@patch("backend.pipeline.os.path.exists", return_value=False)
def test_extract_text_file_not_found(mock_exists):
    """10. Test FileNotFoundError is raised if file doesn't exist."""
    with pytest.raises(FileNotFoundError, match="File not found: non_existent_file.txt"):
        extract_text_from_file("non_existent_file.txt")
    mock_exists.assert_called_once_with("non_existent_file.txt")


@patch("backend.pipeline.os.path.exists", return_value=True)
@patch("backend.pipeline.mimetypes.guess_type", return_value=("application/pdf", None))
@patch("backend.pipeline.auto") # Patch the imported module 'auto'
@patch("backend.pipeline.PdfReader")
def test_extract_text_all_methods_fail_oserror(
    mock_pdf_reader, mock_auto_module, mock_guess_type, mock_exists, capsys
):
    """11. Test OSError is raised if all extraction methods fail for a supported fallback type."""
    mock_auto_module.partition_file.side_effect = Exception("Unstructured failed badly")
    mock_pdf_reader.side_effect = Exception("PdfReader failed badly")

    with patch("builtins.open", mock_open(read_data=b"dummy pdf data")) as mock_file_open:
        with pytest.raises(OSError) as exc_info:
            extract_text_from_file("dummy_corrupted.pdf")

    assert "Failed to extract text from dummy_corrupted.pdf using all methods" in str(exc_info.value)
    assert "PdfReader failed badly" in str(exc_info.value) # Check last error is mentioned

    # Check that unstructured was tried
    mock_auto_module.partition_file.assert_called_once_with(filename="dummy_corrupted.pdf")
    # Check that pypdf was tried
    mock_file_open.assert_called_once_with("dummy_corrupted.pdf", "rb")
    mock_pdf_reader.assert_called_once_with(mock_file_open.return_value)

    # Verify logs/prints
    captured = capsys.readouterr()
    assert "unstructured.io failed for dummy_corrupted.pdf" in captured.out
    assert "Unstructured failed badly" in captured.out
    assert "Attempting fallback extraction for dummy_corrupted.pdf" in captured.out
    assert "Fallback extraction failed for dummy_corrupted.pdf: PdfReader failed badly" in captured.out
