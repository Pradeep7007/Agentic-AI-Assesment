"""Tasks 7 and 8: four tools. Names, arguments, outputs, errors, metric and log names are FIXED (the autograder checks them).

The heavy parts are PROVIDED (kb/store.py: stats / outline / delete_document, kb/pipeline.py: ingest_file).
You write the tool wrappers: signature + docstring (the docstring is the prompt: say WHEN to use it, describe each argument),
validation, ToolException with `ERROR[CODE]: what happened. Next step: what to do.`, the metric, the log line, `handle_tool_error = True`.
All four are `async def` (blocking calls go through asyncio.to_thread). They act on the CALLING USER's knowledge base:
`runtime.context.user_id` (task 6), never on another user's. build_custom_tools(kb) returns all four.
Look at kb/tools.py for the pattern (ToolRuntime, ToolException, handle_tool_error).
"""
import asyncio
import time

from langchain.tools import ToolRuntime
from langchain_core.tools import ToolException, tool
from opentelemetry import metrics

from app.context import Ctx
from app.errors import to_tool_exception
from app.kb import files
from app.kb.pipeline import ingest_file
from app.kb.store import KnowledgeBase
from app.telemetry import log

_meter = metrics.get_meter("agent")
KBSTATS_CALLS = _meter.create_counter("kbstats.calls", unit="1", description="kb_stats calls")
OUTLINE_CALLS = _meter.create_counter("outline.calls", unit="1", description="outline calls")


def build_custom_tools(kb: KnowledgeBase) -> list:
    @tool
    async def kb_stats(runtime: ToolRuntime[Ctx], top_keywords: int = 5) -> str:
        """Get summary statistics for the knowledge base (document count, section count, chunk count,
        and top keywords across all documents). Use when the user asks about the size, scope or overall topics
        of the knowledge base.

        Args:
            top_keywords: Number of top keywords to return (between 1 and 20, default 5).
        """
        user_id = runtime.context.user_id or runtime.context.session_id
        t0 = time.perf_counter()
        success = False
        try:
            if top_keywords < 1 or top_keywords > 20:
                raise ToolException(
                    f"ERROR[INVALID_INPUT]: top_keywords must be between 1 and 20, got {top_keywords}. "
                    "Next step: retry with a value from 1 to 20."
                )
            data = await asyncio.to_thread(kb.stats, user_id)
            if data["documents"] == 0:
                res = "The knowledge base is empty."
            else:
                kw = ", ".join(data["keywords"][:top_keywords])
                res = f"{data['documents']} documents, {data['sections']} sections, {data['chunks']} chunks. Top keywords: {kw}."
            success = True
            return res
        finally:
            elapsed = time.perf_counter() - t0
            KBSTATS_CALLS.add(1, {"status": "ok" if success else "error"})
            log.info(
                "kb_stats_done",
                tool="kb_stats",
                status="ok" if success else "error",
                duration_ms=round(elapsed * 1000, 2),
            )

    @tool
    async def document_outline(doc_name: str, runtime: ToolRuntime[Ctx]) -> str:
        """Get the structural outline and section summaries of one document in reading order.
        Use when the user asks how a document is organised, what sections it contains, or which section
        covers a particular topic.

        Args:
            doc_name: The file name of the document (from the knowledge base list).
        """
        user_id = runtime.context.user_id or runtime.context.session_id
        t0 = time.perf_counter()
        success = False
        sec_count = 0
        try:
            exact = await asyncio.to_thread(kb.resolve_doc_name, user_id, doc_name)
            docs = await asyncio.to_thread(kb.documents, user_id)
            if not exact:
                names = ", ".join(f'"{d["filename"]}"' for d in docs) or "(none)"
                raise ToolException(
                    f"ERROR[UNKNOWN_DOCUMENT]: No document matches '{doc_name}'. Documents: {names}. "
                    "Next step: retry with one of these names."
                )
            doc = next((d for d in docs if d["filename"] == exact), None)
            if not doc:
                names = ", ".join(f'"{d["filename"]}"' for d in docs) or "(none)"
                raise ToolException(
                    f"ERROR[UNKNOWN_DOCUMENT]: No document matches '{doc_name}'. Documents: {names}. "
                    "Next step: retry with one of these names."
                )
            sections = await asyncio.to_thread(kb.outline, user_id, doc["doc_id"])
            sec_count = len(sections)
            lines = [f"Outline of '{exact}' ({sec_count} sections):"]
            for i, s in enumerate(sections, start=1):
                if s.get("page_start") is not None:
                    pages = (
                        f" (p.{s['page_start']})"
                        if s["page_start"] == s["page_end"]
                        else f" (p.{s['page_start']}-{s['page_end']})"
                    )
                else:
                    pages = ""
                lines.append(f"{i}. [L{s.get('level', 1)}] {s['heading']}{pages}: {s.get('summary', '')}")
            success = True
            return "\n".join(lines)
        finally:
            elapsed = time.perf_counter() - t0
            OUTLINE_CALLS.add(1, {"status": "ok" if success else "error"})
            log.info(
                "document_outline_done",
                tool="document_outline",
                status="ok" if success else "error",
                duration_ms=round(elapsed * 1000, 2),
                sections=sec_count if success else 0,
            )

    @tool
    async def delete_document(doc_name: str, runtime: ToolRuntime[Ctx]) -> str:
        """Remove a document from the knowledge base.
        Use when the user asks to delete, remove or forget a document.

        Args:
            doc_name: The file name of the document to delete.
        """
        user_id = runtime.context.user_id or runtime.context.session_id
        exact = await asyncio.to_thread(kb.resolve_doc_name, user_id, doc_name)
        docs = await asyncio.to_thread(kb.documents, user_id)
        if not exact:
            names = ", ".join(f'"{d["filename"]}"' for d in docs) or "(none)"
            raise ToolException(
                f"ERROR[UNKNOWN_DOCUMENT]: No document matches '{doc_name}'. Documents: {names}. "
                "Next step: retry with one of these names."
            )
        doc = next((d for d in docs if d["filename"] == exact), None)
        if not doc:
            names = ", ".join(f'"{d["filename"]}"' for d in docs) or "(none)"
            raise ToolException(
                f"ERROR[UNKNOWN_DOCUMENT]: No document matches '{doc_name}'. Documents: {names}. "
                "Next step: retry with one of these names."
            )
        await asyncio.to_thread(kb.delete_document, user_id, doc["doc_id"])
        left = await asyncio.to_thread(kb.documents, user_id)
        return f"Deleted '{exact}'. {len(left)} documents left."

    @tool
    async def update_document(doc_name: str, source: str, runtime: ToolRuntime[Ctx]) -> str:
        """Replace an existing document in the knowledge base with a new uploaded version under the same name.
        Use when the user uploads a new version of an existing document.

        Args:
            doc_name: The file name of the existing document to update.
            source: The file_id of the newly uploaded file (from the upload message).
        """
        user_id = runtime.context.user_id or runtime.context.session_id
        session_id = runtime.context.session_id
        exact = await asyncio.to_thread(kb.resolve_doc_name, user_id, doc_name)
        docs = await asyncio.to_thread(kb.documents, user_id)
        if not exact:
            names = ", ".join(f'"{d["filename"]}"' for d in docs) or "(none)"
            raise ToolException(
                f"ERROR[UNKNOWN_DOCUMENT]: No document matches '{doc_name}'. Documents: {names}. "
                "Next step: retry with one of these names."
            )
        old_doc = next((d for d in docs if d["filename"] == exact), None)
        if not old_doc:
            names = ", ".join(f'"{d["filename"]}"' for d in docs) or "(none)"
            raise ToolException(
                f"ERROR[UNKNOWN_DOCUMENT]: No document matches '{doc_name}'. Documents: {names}. "
                "Next step: retry with one of these names."
            )
        try:
            if source.startswith(("http://", "https://")):
                _, path = await files.download(session_id, source)
            else:
                path, _ = files.resolve(session_id, source.strip())
        except Exception as exc:
            raise to_tool_exception(exc) from exc

        try:
            result, existing = await ingest_file(kb, user_id, path, exact, runtime.config)
        except Exception as exc:
            raise to_tool_exception(exc) from exc

        if existing:
            return f"'{exact}' is already up to date."

        await asyncio.to_thread(kb.delete_document, user_id, old_doc["doc_id"])
        return f"Updated '{exact}': {len(result.sections)} sections, {result.n_chunks} chunks."

    for t in (kb_stats, document_outline, delete_document, update_document):
        t.handle_tool_error = True

    return [kb_stats, document_outline, delete_document, update_document]
