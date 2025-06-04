import tempfile
import uuid
from typing import List, Dict, Any
from pathlib import Path
import shutil

from fastapi import UploadFile
from backend.pipeline import GraphState, app as pipeline_app # Assuming pipeline_app is the compiled LangGraph

def process_uploaded_files(client_id: uuid.UUID, files: List[UploadFile]) -> Dict[str, Any]:
    """
    Processes uploaded files for a client, simulates file handling, and invokes the (mocked) LangGraph pipeline.
    """
    print(f"INFO: Starting file processing for client_id: {client_id}")

    temp_dir = tempfile.mkdtemp()
    print(f"INFO: Created temporary directory for uploaded files: {temp_dir}")

    resume_file_path_str = None
    source_document_paths_str = []

    for index, file in enumerate(files):
        # Ensure filename is a string and sanitize if necessary (though tempfile names are usually safe)
        filename_str = Path(file.filename).name if file.filename else f"uploaded_file_{index}"
        file_location = Path(temp_dir) / filename_str

        try:
            with open(file_location, "wb+") as file_object:
                shutil.copyfileobj(file.file, file_object)
            print(f"INFO: Saved uploaded file '{filename_str}' to '{file_location}'")

            # Simplified assumption for identifying resume vs. source documents
            if resume_file_path_str is None and ("resume" in filename_str.lower() or index == 0):
                resume_file_path_str = str(file_location)
                print(f"INFO: Identified '{filename_str}' as RESUME.")
            else:
                source_document_paths_str.append(str(file_location))
                print(f"INFO: Identified '{filename_str}' as SOURCE.")

        except Exception as e:
            print(f"ERROR: Could not save file '{filename_str}'. Error: {e}")
        finally:
            if hasattr(file, 'file') and file.file: # Check if file object exists and is not None
                file.file.close()

    if resume_file_path_str is None and source_document_paths_str:
        resume_file_path_str = source_document_paths_str.pop(0)
        print(f"WARNING: No explicit resume file found. Using '{Path(resume_file_path_str).name}' as pseudo-resume.")
    elif resume_file_path_str is None and not source_document_paths_str:
        print("ERROR: No files processed or identified as resume/sources.")
        if Path(temp_dir).exists(): shutil.rmtree(temp_dir)
        return {"message": "No files processed.", "num_files_processed": 0, "pipeline_output": None}

    initial_state = GraphState(
        client_id=str(client_id),
        resume_file_path=resume_file_path_str if resume_file_path_str else "", # Ensure not None
        source_document_paths=source_document_paths_str,
        roles_parsed=[],
        validation_results={},
        feedback_to_synthesizer=None,
        error_message=None,
        trace_id=str(uuid.uuid4())
    )
    # Access GraphState fields as dictionary keys since it's a TypedDict
    print(f"INFO: Prepared initial GraphState: {{client_id='{initial_state['client_id']}', resume_file_path='{initial_state['resume_file_path']}', num_sources={len(initial_state['source_document_paths'])}}}")

    print("INFO: Invoking LangGraph pipeline (app.invoke)...")
    try:
        # This is a placeholder for M4. In tests, this service will be mocked.
        # output = pipeline_app.invoke(initial_state.dict()) # Pass state as dict
        output = {
            "roles_parsed": [{"title": "Mock Role from Pipeline", "company": "Mock Company Inc."}],
            "error_message": None,
            "client_id": str(client_id)
        }
        print(f"INFO: LangGraph pipeline (mock) output: {output}")
        if output.get("error_message"):
            print(f"ERROR: Pipeline execution failed: {output['error_message']}")

    except Exception as e:
        print(f"ERROR: Exception during pipeline invocation: {e}")
        output = {"error_message": str(e), "roles_parsed": []}

    if Path(temp_dir).exists():
        try:
            shutil.rmtree(temp_dir)
            print(f"INFO: Successfully removed temporary directory: {temp_dir}")
        except Exception as e:
            print(f"ERROR: Could not remove temporary directory '{temp_dir}'. Error: {e}")

    return {
        "message": "Files processed (simulated pipeline execution).",
        "num_files_processed": len(files),
        "pipeline_output": output
    }
