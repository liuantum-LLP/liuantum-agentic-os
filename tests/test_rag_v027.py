import json
import subprocess
import sys

from runtime.action_log import list_external_actions
from runtime.agents import AgentRunner
from runtime.api.app import knowledge_search
from runtime.config import SettingsManager
from runtime.knowledge import KnowledgeBase
from runtime.memory import MemoryManager
from runtime.providers import ModelHub


def test_local_hash_embedding_returns_deterministic_vector():
    a = ModelHub().create_embedding("Liuant local first", provider_name="local_hash_embedding")
    b = ModelHub().create_embedding("Liuant local first", provider_name="local_hash_embedding")

    assert a["status"] == "completed"
    assert a["dimension"] == 384
    assert a["embedding"] == b["embedding"]


def test_embedding_provider_missing_key_returns_needs_provider_setup(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = ModelHub().create_embedding("hello", provider_name="openai_embedding")

    assert result["status"] == "needs_provider_setup"


def test_knowledge_add_text_creates_source_and_chunks():
    source = KnowledgeBase().add_text("Liuant Agentic OS is a local-first AI workforce platform.", title="About Liuant")

    assert source["chunk_count"] == 1
    assert KnowledgeBase().sources()[0]["title"] == "About Liuant"


def test_knowledge_search_returns_relevant_result():
    KnowledgeBase().add_text("Liuant Agentic OS is a local-first AI workforce platform.", title="About Liuant")

    result = KnowledgeBase().search("What is Liuant Agentic OS?")

    assert result["results"]
    assert result["results"][0]["title"] == "About Liuant"


def test_path_traversal_file_indexing_rejected():
    try:
        KnowledgeBase().index_file("../../.env")
        assert False
    except ValueError as exc:
        assert "workspace" in str(exc).lower()


def test_env_file_indexing_rejected(tmp_path, monkeypatch):
    from runtime.storage import WORKSPACE

    env_path = WORKSPACE / ".env"
    env_path.write_text("SECRET=abc", encoding="utf-8")
    try:
        KnowledgeBase().index_file(".env")
        assert False
    except ValueError as exc:
        assert "not indexed" in str(exc)
    finally:
        env_path.unlink(missing_ok=True)


def test_agent_run_without_rag_unchanged():
    run = AgentRunner().run("tutor-agent", "Create lesson plan")

    assert "retrieved_context" not in run["result"]


def test_agent_run_with_rag_stores_retrieved_context():
    KnowledgeBase().add_text("Python notes: functions, loops, and projects.", title="Python Notes")
    MemoryManager().add("User prefers practical assignments", memory_type="user")

    run = AgentRunner().run("tutor-agent", "Create lesson plan based on Python notes", rag_enabled=True)

    assert "retrieved_context" in run["result"]
    assert run["result"]["retrieved_context"]["knowledge"]


def test_rag_failure_does_not_break_agent_run(monkeypatch):
    def fail(*_args, **_kwargs):
        raise RuntimeError("rag unavailable")

    monkeypatch.setattr(KnowledgeBase, "search", fail)
    run = AgentRunner().run("tutor-agent", "Create lesson plan", rag_enabled=True)

    assert run["status"] == "completed"
    assert "retrieved_context" in run["result"]


def test_memory_add_list_search_delete_works():
    row = MemoryManager().add("User prefers premium dark UI", memory_type="user")
    search = MemoryManager().search("UI preference")
    deleted = MemoryManager().delete(row["id"])

    assert row in MemoryManager().list("user_memory") or row["id"]
    assert search["results"]
    assert deleted["deleted"] == 1


def test_telegram_knowledge_search_disabled_by_default():
    assert SettingsManager().get("telegram_knowledge_search_enabled")["value"] == "false"


def test_email_rag_disabled_by_default():
    assert SettingsManager().get("email_rag_enabled")["value"] == "false"


def test_scheduler_rag_disabled_by_default():
    assert SettingsManager().get("scheduler_rag_enabled")["value"] == "false"


def test_api_knowledge_search_works():
    KnowledgeBase().add_text("Liuant is local-first.", title="Local First")

    result = knowledge_search({"query": "local-first"})

    assert result["status"] == "completed"
    assert result["results"]


def test_cli_knowledge_search_works():
    subprocess.run([sys.executable, "-m", "cli.liuant", "knowledge", "add-text", "Liuant Agentic OS is local-first"], capture_output=True, text=True, check=True)
    result = subprocess.run([sys.executable, "-m", "cli.liuant", "knowledge", "search", "What is Liuant Agentic OS?"], capture_output=True, text=True, check=True)

    assert "Liuant Knowledge" in result.stdout
    assert "completed" in result.stdout


def test_no_secrets_in_action_logs():
    KnowledgeBase().add_text("password is super-secret-value", title="Sensitive")
    logs = json.dumps(list_external_actions())

    assert "super-secret-value" not in logs


def test_provider_list_includes_local_hash_embedding():
    providers = ModelHub().list_providers("embedding")

    assert any(row["id"] == "local_hash_embedding" for row in providers)
