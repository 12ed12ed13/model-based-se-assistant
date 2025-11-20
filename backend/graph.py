"""
LangGraph workflow definition for the Model-Based Software Engineering Assistant.

Implements the multi-agent orchestration graph with proper state management,
routing, and error handling.
"""

import json
import logging
import uuid
from typing import Any, Dict, Optional
from pathlib import Path

from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from backend.agents import (
    ParserAgent,
    AnalysisAgent,
    CodeGenerationAgent,
    TestGenerationAgent,
    CriticAgent
)
from backend.config import PROJECTS_DIR
from backend.memory import ProjectMemory
from backend.storage import ProjectStorage
from backend.exporters.plantuml import write_plantuml

storage = ProjectStorage()

logger = logging.getLogger(__name__)


# ============================================================================
# State Definition
# ============================================================================

class WorkflowState(BaseModel):
    """
    Represents the state of the workflow as it progresses through agents.
    """

    # Input
    project_id: str = Field(description="Unique project identifier")
    model_text: str = Field(description="Raw model text")
    model_format: str = Field(default="plantuml", description="Model format type")
    description: str = Field(default="", description="Natural language description")
    project_tags: list = Field(default_factory=list, description="Project technology tags (e.g., FastAPI, React)")

    # Intermediate results
    model_ir: Dict[str, Any] = Field(default_factory=dict, description="Parsed model IR")
    analysis_report: Dict[str, Any] = Field(default_factory=dict, description="Analysis findings")
    generated_code: Dict[str, Any] = Field(default_factory=dict, description="Generated source code")
    generated_tests: Dict[str, Any] = Field(default_factory=dict, description="Generated test code")
    test_results: Dict[str, Any] = Field(default_factory=dict, description="Test execution results")

    # Final output
    critique: Dict[str, Any] = Field(default_factory=dict, description="Critique and suggestions")
    final_report: Dict[str, Any] = Field(default_factory=dict, description="Final summary report")

    # Execution tracking
    errors: list = Field(default_factory=list, description="Errors encountered")
    retry_count: int = Field(default=0, description="Number of self-correction retries")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Performance metrics")
    version_id: str = Field(default_factory=lambda: uuid.uuid4().hex, description="Version identifier for current run")
    parent_version_id: Optional[str] = Field(default=None, description="Previous version identifier")
    previous_model_ir: Dict[str, Any] = Field(default_factory=dict, description="IR of previous version")
    previous_analysis_report: Dict[str, Any] = Field(default_factory=dict, description="Analysis output from previous version")
    diff_summary: Dict[str, Any] = Field(default_factory=dict, description="Diff summary compared to previous version")
    plantuml_path: Optional[str] = Field(default=None, description="Generated PlantUML path for this version")
    job_id: Optional[str] = Field(default=None, description="Job identifier for workflow execution")


# ============================================================================
# Node Functions
# ============================================================================

def node_parse_model(state: WorkflowState) -> WorkflowState:
    """Parse the input model into an IR."""
    logger.info(f"[PARSE] Processing {state.model_format} model for project {state.project_id}")

    try:
        storage.ensure_project(state.project_id, description=state.description)
        previous_version = storage.get_latest_version(state.project_id)
        if previous_version:
            state.parent_version_id = previous_version.version_id
            state.previous_model_ir = previous_version.model_ir or {}
            state.previous_analysis_report = previous_version.analysis or {}
            logger.info(
                "[PARSE] Loaded previous version %s for project %s",
                previous_version.version_id,
                state.project_id,
            )
    except Exception as storage_error:
        logger.warning(f"[PARSE] Unable to load previous version metadata: {storage_error}")
    
    try:
        agent = ParserAgent()
        model_ir = agent.parse_model(state.model_text, state.model_format)
        state.model_ir = model_ir
        logger.info("[PARSE] Model parsing completed successfully")
    except Exception as e:
        logger.error(f"[PARSE] Error parsing model: {e}")
        state.errors.append(f"Parser error: {str(e)}")

    # Persist partial parse results to version
    try:
        storage.update_version(project_id=state.project_id, version_id=state.version_id, model_ir=state.model_ir, status="running", progress=20)
        # Update job status message
        if state.job_id:
            try:
                storage.update_job(job_id=state.job_id, status="running", message="Parsed model")
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"[PARSE] Unable to persist partial parse results: {e}")
    return state


def node_analyze_model(state: WorkflowState) -> WorkflowState:
    """Analyze the model for design issues."""
    if not state.model_ir or state.errors:
        logger.warning("[ANALYZE] Skipping analysis due to parse errors")
        return state

    logger.info("[ANALYZE] Analyzing model for design issues")

    try:
        agent = AnalysisAgent()
        
        # Enhance description with project tags for better context
        enhanced_description = state.description
        if state.project_tags:
            tags_str = ", ".join(state.project_tags)
            enhanced_description = f"{state.description}\n\nTechnology Stack: {tags_str}" if state.description else f"Technology Stack: {tags_str}"
        
        analysis = agent.analyze_model(
            state.model_ir,
            enhanced_description,
            previous_analysis=state.previous_analysis_report,
            previous_model_ir=state.previous_model_ir,
        )
        state.analysis_report = analysis
        state.diff_summary = analysis.get("trend", {})
        logger.info(f"[ANALYZE] Found {len(analysis.get('findings', []))} issues")
    except Exception as e:
        logger.error(f"[ANALYZE] Error analyzing model: {e}")
        state.errors.append(f"Analysis error: {str(e)}")

    # Persist partial analysis
    try:
        storage.update_version(project_id=state.project_id, version_id=state.version_id, analysis=state.analysis_report, metrics=state.analysis_report.get("quality_metrics", {}), summary=state.analysis_report.get("summary"), progress=40)
        if state.job_id:
            try:
                storage.update_job(job_id=state.job_id, status="running", message="Analysis completed")
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"[ANALYZE] Unable to persist partial analysis: {e}")
    return state


def node_generate_code(state: WorkflowState) -> WorkflowState:
    """Generate code from the model."""
    if not state.model_ir or state.errors:
        logger.warning("[CODEGEN] Skipping code generation due to earlier errors")
        return state

    logger.info("[CODEGEN] Generating source code from model")

    try:
        agent = CodeGenerationAgent()
        code = agent.generate_code(
            state.model_ir,
            language="python",
            analysis_report=state.analysis_report,
            apply_refactorings=True,
        )
        state.generated_code = code
        logger.info(f"[CODEGEN] Generated {len(code.get('files', []))} code files")
    except Exception as e:
        logger.error(f"[CODEGEN] Error generating code: {e}")
        state.errors.append(f"Code generation error: {str(e)}")

    # Persist partial code snapshot
    try:
        storage.update_version(project_id=state.project_id, version_id=state.version_id, code=state.generated_code, progress=60)
        if state.job_id:
            try:
                storage.update_job(job_id=state.job_id, status="running", message="Code generation completed")
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"[CODEGEN] Unable to persist generated code: {e}")
    return state


def node_generate_tests(state: WorkflowState) -> WorkflowState:
    """Generate test cases based on generated code and analysis."""
    logger.info("[TESTGEN] Generating test cases")
    
    try:
        agent = TestGenerationAgent()
        
        # Generate tests with analysis awareness
        result = agent.generate_tests(
            model_ir=state.model_ir,
            generated_code=state.generated_code,
            analysis_report=state.analysis_report,
            framework="pytest",
            include_integration_tests=True
        )
        
        state.generated_tests = result
        logger.info(
            f"[TESTGEN] Generated {len(result.get('test_files', []))} test files "
            f"with ~{result.get('total_tests', 0)} test cases"
        )
    except Exception as e:
        logger.error(f"[TESTGEN] Error generating tests: {e}", exc_info=True)
        state.errors.append(f"Test generation error: {str(e)}")
    
    # Persist partial tests snapshot
    try:
        storage.update_version(project_id=state.project_id, version_id=state.version_id, tests=state.generated_tests, progress=80)
        if state.job_id:
            try:
                storage.update_job(job_id=state.job_id, status="running", message="Tests generated")
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"[TESTGEN] Unable to persist generated tests: {e}")
    return state


def node_save_artifacts(state: WorkflowState) -> WorkflowState:
    """Save generated code and tests to persistent storage."""
    if state.errors:
        logger.warning("[SAVE] Skipping artifact saving due to errors")
        return state
    
    logger.info(f"[SAVE] Saving artifacts for project {state.project_id}")
    
    try:
        # Create project directory
        project_path = PROJECTS_DIR / state.project_id
        project_path.mkdir(parents=True, exist_ok=True)
        version_dir = project_path / "versions" / state.version_id
        version_dir.mkdir(parents=True, exist_ok=True)
        snapshot_src_dir = version_dir / "src"
        snapshot_tests_dir = version_dir / "tests"
        snapshot_src_dir.mkdir(parents=True, exist_ok=True)
        snapshot_tests_dir.mkdir(parents=True, exist_ok=True)
        
        # Save source files to root
        source_files = state.generated_code.get("files", [])
        for file_info in source_files:
            file_path = project_path / file_info.get("path", "unknown.py")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(file_info.get("content", ""))
            logger.debug(f"[SAVE] Saved source file: {file_path}")

            snapshot_path = snapshot_src_dir / file_info.get("path", "unknown.py")
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(file_info.get("content", ""))
        
        # Save test files to tests/ subfolder
        test_files = state.generated_tests.get("test_files", [])
        tests_dir = project_path / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        
        for test_file in test_files:
            # Remove 'tests/' prefix if it exists to avoid duplication
            test_path = test_file.get("path", "test_unknown.py")
            if test_path.startswith("tests/"):
                test_path = test_path[6:]  # Remove 'tests/' prefix
            
            file_path = tests_dir / test_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(test_file.get("content", ""))
            logger.debug(f"[SAVE] Saved test file: {file_path}")

            snapshot_path = snapshot_tests_dir / test_path
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(test_file.get("content", ""))
        
        # Create __init__.py in tests folder
        init_file = tests_dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("# Test package init\n")
        
        # Save analysis report
        if state.analysis_report:
            analysis_file = project_path / "analysis_report.json"
            analysis_file.write_text(json.dumps(state.analysis_report, indent=2))
            logger.debug(f"[SAVE] Saved analysis report: {analysis_file}")

            snapshot_analysis = version_dir / "analysis_report.json"
            snapshot_analysis.write_text(json.dumps(state.analysis_report, indent=2))

        # Persist original model text for auditing
        model_ext = ".puml" if "plantuml" in (state.model_format or "").lower() else ".txt"
        (version_dir / f"model_input{model_ext}").write_text(state.model_text)

        # Generate PlantUML from IR for comparison
        try:
            plantuml_file = write_plantuml(state.model_ir, version_dir / "model_generated.puml")
            state.plantuml_path = str(plantuml_file)
        except Exception as plantuml_error:
            logger.warning(f"[SAVE] Failed to export PlantUML: {plantuml_error}")

        # Write version metadata snapshot
        metadata = {
            "project_id": state.project_id,
            "version_id": state.version_id,
            "parent_version_id": state.parent_version_id,
            "description": state.description,
            "status": "completed" if not state.errors else "partial",
            "analysis_summary": state.analysis_report.get("summary"),
            "quality_score": state.analysis_report.get("quality_score"),
            "diff_summary": state.diff_summary,
            "plantuml_path": state.plantuml_path,
        }
        (version_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

        # Persist version metadata via SQLite storage
        status = metadata["status"]
        summary_text = metadata["analysis_summary"] or metadata["status"]
        try:
            storage.update_version(
                project_id=state.project_id,
                version_id=state.version_id,
                status=status,
                summary=summary_text,
                metrics=state.analysis_report.get("quality_metrics", {}),
                model_ir=state.model_ir,
                analysis=state.analysis_report,
                code=state.generated_code,
                tests=state.generated_tests,
                critique=state.critique,
                plantuml_path=state.plantuml_path,
                quality_score=state.analysis_report.get("quality_score"),
                progress=100,
            )
            if state.job_id:
                try:
                    storage.update_job(job_id=state.job_id, status="running", message="Artifacts saved")
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"[SAVE] Unable to update version metadata: {e}")

        # Save recommendations to separate table (outside try-except so it always runs)
        try:
            if state.analysis_report.get("recommendations"):
                storage.save_recommendations(
                    state.project_id,
                    state.version_id,
                    state.analysis_report.get("recommendations", []),
                )
        except Exception as rec_error:
            logger.warning(f"[SAVE] Unable to save recommendations: {rec_error}")

        # Save diff if this is not the first version
        try:
            if state.diff_summary and state.parent_version_id:
                storage.save_diff(
                    state.project_id,
                    state.parent_version_id,
                    state.version_id,
                    state.diff_summary,
                )
        except Exception as diff_error:
            logger.warning(f"[SAVE] Unable to save diff: {diff_error}")
        
        # Save to project memory
        memory = ProjectMemory(state.project_id)
        memory_state = {
            "model_ir": state.model_ir,
            "generated_files": [f.get("path") for f in source_files],
            "test_files": [f.get("path") for f in test_files],
            "analysis_findings": len(state.analysis_report.get("findings", [])),
            "test_results": state.test_results,
            "status": status,
            "version_id": state.version_id,
            "parent_version_id": state.parent_version_id,
            "diff_summary": state.diff_summary,
            "plantuml_path": state.plantuml_path,
            "quality_score": state.analysis_report.get("quality_score"),
        }
        memory.save(memory_state)
        
        # Add analysis to history
        if state.analysis_report:
            memory.add_analysis(state.analysis_report)
        
        logger.info(
            f"[SAVE] Saved {len(source_files)} source files and "
            f"{len(test_files)} test files to {project_path}"
        )
        
    except Exception as e:
        logger.error(f"[SAVE] Error saving artifacts: {e}", exc_info=True)
        state.errors.append(f"Artifact saving error: {str(e)}")
    
    return state


def node_run_tests(state: WorkflowState) -> WorkflowState:
    """Execute tests and collect results."""
    if not state.generated_tests or state.errors:
        logger.warning("[EXECUTE] Skipping test execution due to earlier errors or no tests")
        return state

    logger.info("[EXECUTE] Running tests")

    try:
        test_files = state.generated_tests.get("test_files", [])
        if not test_files:
            logger.warning("[EXECUTE] No test files to execute")
            return state
        
        # Write test files to temp directory
        import tempfile
        import subprocess
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            
            # Write test files
            for test_file in test_files:
                file_path = tmppath / test_file.get("path", "test_unknown.py")
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(test_file.get("content", ""))
            
            # Also write source files if available
            source_files = state.generated_code.get("files", [])
            for source_file in source_files:
                file_path = tmppath / source_file.get("path", "unknown.py")
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(source_file.get("content", ""))

            # Ensure __init__.py exists for package imports (e.g., src/)
            for p in tmppath.rglob('*'):
                if p.is_dir():
                    init_file = p / "__init__.py"
                    if not init_file.exists():
                        try:
                            init_file.write_text("# Package init\n")
                        except Exception:
                            # Some directories (like tmp root) might be non-writable, ignore
                            pass
            
            # Run pytest
            try:
                import os as _os
                import sys as _sys
                env = _os.environ.copy()
                env["PYTHONPATH"] = str(tmppath)
                
                # Use sys.executable to ensure we use the same Python environment
                cmd = [_sys.executable, "-m", "pytest", str(tmppath), "-v", "--tb=short"]
                
                result = subprocess.run(
                    cmd,
                    cwd=tmpdir,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                # Parse results
                passed = result.stdout.count(" PASSED")
                failed = result.stdout.count(" FAILED")
                errors = result.stdout.count(" ERROR")
                
                state.test_results = {
                    "status": "completed",
                    "passed": passed,
                    "failed": failed,
                    "errors": errors,
                    "exit_code": result.returncode,
                    "stdout": result.stdout[:1000],  # Limit output
                    "stderr": result.stderr[:1000] if result.stderr else ""
                }
                
                logger.info(
                    f"[EXECUTE] Tests completed: "
                    f"{passed} passed, {failed} failed, {errors} errors"
                )
                
            except subprocess.TimeoutExpired:
                logger.error("[EXECUTE] Test execution timeout")
                state.test_results = {
                    "status": "timeout",
                    "message": "Test execution exceeded 60 seconds"
                }
            except FileNotFoundError:
                logger.warning("[EXECUTE] pytest not found, skipping test execution")
                state.test_results = {
                    "status": "skipped",
                    "message": "pytest not installed"
                }
                
    except Exception as e:
        logger.error(f"[EXECUTE] Error executing tests: {e}", exc_info=True)
        state.errors.append(f"Test execution error: {str(e)}")
        state.test_results = {
            "status": "error",
            "message": str(e)
        }

    return state


def node_fix_code(state: WorkflowState) -> WorkflowState:
    """Attempt to fix code based on test failures."""
    logger.info(f"[FIX] Attempting to fix code (Attempt {state.retry_count + 1})")
    
    try:
        agent = CodeGenerationAgent()
        
        # Pass the code files and test results directly
        # The agent expects code_files as Dict[str, Any] containing "files" list
        # and test_results as Dict[str, Any] containing "stderr", "stdout", etc.
        fixed_code = agent.fix_code(
            code_files=state.generated_code,
            test_results=state.test_results
        )
        
        if fixed_code and fixed_code.get("files"):
            state.generated_code = fixed_code
            state.retry_count += 1
            logger.info(f"[FIX] Applied fixes to {len(fixed_code.get('files', []))} files")
        else:
            logger.warning("[FIX] No fixes generated")
            # Increment retry count anyway to avoid infinite loop if agent fails to fix
            state.retry_count += 1
            
    except Exception as e:
        logger.error(f"[FIX] Error fixing code: {e}")
        state.errors.append(f"Fix code error: {str(e)}")
        state.retry_count += 1
        
    return state


def node_critique(state: WorkflowState) -> WorkflowState:
    """Review artifacts and propose improvements."""
    logger.info("[CRITIQUE] Reviewing artifacts and generating critique")

    try:
        agent = CriticAgent()
        critique = agent.critique(
            state.analysis_report,
            state.generated_code,
            state.test_results,
            project_tags=state.project_tags
        )
        state.critique = critique
        logger.info("[CRITIQUE] Critique completed")
    except Exception as e:
        logger.error(f"[CRITIQUE] Error during critique: {e}")
        state.errors.append(f"Critique error: {str(e)}")

    return state


def node_final_report(state: WorkflowState) -> WorkflowState:
    """Assemble the final report."""
    logger.info("[REPORT] Assembling final report")

    state.final_report = {
        "project_id": state.project_id,
        "status": "success" if not state.errors else "partial",
        "errors": state.errors,
        "model_ir_classes": len(state.model_ir.get("classes", [])),
        "generated_files": len(state.generated_code.get("files", [])),
        "test_cases": state.generated_tests.get("total_tests", 0),
        "test_results": state.test_results,
        "analysis_findings": len(state.analysis_report.get("findings", [])),
        "critique_suggestions": len(state.critique.get("refactoring_suggestions", [])),
        "version_id": state.version_id,
        "parent_version_id": state.parent_version_id,
        "diff_summary": state.diff_summary,
        "plantuml_path": state.plantuml_path,
    }

    logger.info("[REPORT] Final report assembled")
    if state.job_id:
        try:
            storage.update_job(job_id=state.job_id, status="completed", message="Workflow completed")
        except Exception:
            pass
    return state


# ============================================================================
# Conditional Routing
# ============================================================================

def should_proceed_to_analysis(state: WorkflowState) -> str:
    """Determine if we should proceed to analysis."""
    if state.errors:
        return "final_report"
    return "analyze"


def check_execution_results(state: WorkflowState) -> str:
    """Determine next step after test execution."""
    # Check for failures
    has_failures = False
    if state.test_results:
        try:
            # Check for failed tests or errors (syntax errors often show up as errors or failures)
            failed = int(state.test_results.get("failed", 0))
            errors = int(state.test_results.get("errors", 0))
            exit_code = state.test_results.get("exit_code", 0)
            
            if failed > 0 or errors > 0 or exit_code != 0:
                has_failures = True
        except Exception:
            pass
            
    # Self-correction loop: if failures exist and we haven't retried too many times
    if has_failures and state.retry_count < 3:
        return "fix_code"
        
    # If no fix needed or max retries reached, proceed to critique or finish
    has_findings = len(state.analysis_report.get("findings", [])) > 0
    
    if has_findings or has_failures:
        return "critique"
    
    return "final_report"


# ============================================================================
# Graph Construction
# ============================================================================

def build_workflow_graph() -> StateGraph:
    """
    Build the LangGraph workflow.

    Returns:
        Compiled StateGraph ready for execution.
    """
    graph = StateGraph(WorkflowState)

    # Add nodes
    graph.add_node("parse", node_parse_model)
    graph.add_node("analyze", node_analyze_model)
    graph.add_node("codegen", node_generate_code)
    graph.add_node("testgen", node_generate_tests)
    graph.add_node("save", node_save_artifacts)
    graph.add_node("execute", node_run_tests)
    graph.add_node("fix_code", node_fix_code)
    graph.add_node("critique", node_critique)
    graph.add_node("final_report", node_final_report)

    # Set entry point
    graph.set_entry_point("parse")

    # Add edges
    graph.add_conditional_edges(
        "parse",
        should_proceed_to_analysis,
        {
            "analyze": "analyze",
            "final_report": "final_report"
        }
    )
    graph.add_edge("analyze", "codegen")
    graph.add_edge("codegen", "testgen")
    graph.add_edge("testgen", "save")
    graph.add_edge("save", "execute")
    graph.add_conditional_edges(
        "execute",
        check_execution_results,
        {
            "fix_code": "fix_code",
            "critique": "critique",
            "final_report": "final_report"
        }
    )
    graph.add_edge("fix_code", "save")
    graph.add_edge("critique", "final_report")
    graph.add_edge("final_report", END)

    return graph




def get_compiled_graph():
    """Get the compiled workflow graph."""
    graph = build_workflow_graph()
    return graph.compile()
