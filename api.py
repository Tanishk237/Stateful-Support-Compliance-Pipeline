"""FastAPI entry point for the billing complaint workflow."""

from typing import Any, Dict, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from persistence import SQLiteStore
from service import ComplaintService
from state.workflow_state import WorkflowState


class ComplaintCreate(BaseModel):
    email: str = Field(min_length=1, description="Customer billing complaint email")


class ClarificationCreate(BaseModel):
    answers: Dict[str, Any] = Field(
        default_factory=dict,
        description="Values keyed by the missing field names returned by the workflow",
    )


def create_app(store: Optional[SQLiteStore] = None) -> FastAPI:
    """Build the API, optionally with an injected store for tests."""
    application = FastAPI(
        title="Billing Complaint Workflow API",
        version="1.0.0",
        description="A small stateful GenAI demo with compliance-first routing.",
    )
    service = ComplaintService(store)
    frontend = Path(__file__).resolve().parent / "frontend"
    application.mount("/assets", StaticFiles(directory=frontend / "assets"), name="assets")

    @application.get("/", response_class=FileResponse, include_in_schema=False)
    def home() -> FileResponse:
        return FileResponse(frontend / "index.html")

    @application.get("/demo-config")
    def demo_config() -> Dict[str, Any]:
        from config import USE_LLM

        return {"llm_enabled": USE_LLM}

    @application.get("/health")
    def health() -> Dict[str, str]:
        if not service.store.healthcheck():
            raise HTTPException(status_code=503, detail="Database is unavailable")
        return {"status": "ok", "database": "connected"}

    @application.post(
        "/complaints",
        response_model=WorkflowState,
        status_code=status.HTTP_201_CREATED,
    )
    def create_complaint(payload: ComplaintCreate) -> WorkflowState:
        try:
            return service.create_complaint(payload.email)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.post(
        "/complaints/{request_id}/clarification",
        response_model=WorkflowState,
    )
    def submit_clarification(
        request_id: str, payload: ClarificationCreate
    ) -> WorkflowState:
        try:
            return service.submit_clarification(request_id, payload.answers)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Complaint not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    def event_response(state: WorkflowState) -> StreamingResponse:
        return StreamingResponse(
            service.stream(state),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @application.post("/complaints/stream")
    def stream_complaint(payload: ComplaintCreate) -> StreamingResponse:
        try:
            return event_response(service.new_state(payload.email))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.post("/complaints/{request_id}/clarification/stream")
    def stream_clarification(request_id: str, payload: ClarificationCreate) -> StreamingResponse:
        try:
            return event_response(service.clarification_state(request_id, payload.answers))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Complaint not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.get("/complaints/{request_id}", response_model=WorkflowState)
    def get_complaint(request_id: str) -> WorkflowState:
        try:
            return service.get_complaint(request_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Complaint not found") from exc

    return application


app = create_app()
