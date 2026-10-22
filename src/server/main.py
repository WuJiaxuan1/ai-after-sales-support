"""
main.py — FastAPI 应用入口（v2）
================================
普通售后 RAG 与 Safety RAG 分离加载；系统控制规则不进入用户回答 RAG。
"""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.engine.case_manager import CaseManager
from server.engine.handoff import HandoffManager
from server.engine.rag import RAGEngine
from server.engine.safety import SafetyGate
from server.engine.service import AfterSalesService
from server.ai.adapter import AIAdapter
from server.data.mock_data import MockBusinessData
from server.routes.api import create_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    case_mgr = CaseManager()

    kb_dir = Path(__file__).resolve().parent.parent / "knowledge-base"

    ordinary_rag = RAGEngine(name="ordinary")
    for filename in ["after-sales-policies.md", "troubleshooting-knowledge.md"]:
        ordinary_rag.load_from_markdown(str(kb_dir / filename))

    safety_rag = RAGEngine(name="safety")
    safety_rag.load_from_markdown(str(kb_dir / "safety-knowledge.md"))

    handoff_mgr = HandoffManager(case_mgr)
    ai_adapter = AIAdapter(case_mgr, ordinary_rag, safety_rag)
    safety_gate = SafetyGate()
    mock_data = MockBusinessData()
    service = AfterSalesService(case_mgr, handoff_mgr, ai_adapter, safety_gate, mock_data)

    router = create_router(case_mgr, handoff_mgr, service, mock_data)
    app.include_router(router, prefix="/api")

    app.state.case_mgr = case_mgr
    app.state.handoff_mgr = handoff_mgr
    app.state.ordinary_rag = ordinary_rag
    app.state.safety_rag = safety_rag
    app.state.ai_adapter = ai_adapter
    app.state.safety_gate = safety_gate
    app.state.service = service
    app.state.mock_data = mock_data

    print(
        "Server started - ordinary RAG: {} chunks, safety RAG: {} chunks".format(
            len(ordinary_rag._chunks), len(safety_rag._chunks)
        )
    )
    yield
    print("Server shutting down")


app = FastAPI(
    title="After-Sales AI System",
    description="Deterministic Workflow + Longest Reliable Existing Path + RAG + Safety Gate + Human Handoff",
    version="mvp-v2",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "system": "after-sales-ai-v2"}
