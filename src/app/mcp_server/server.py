"""Task 9: the notes and tasks MCP server. Run by docker compose / CI as:  python src/app/mcp_server/server.py --http  (port 9000, path /mcp)

The storage is PROVIDED (taskstore.py: TaskStore), the user lookup is PROVIDED (app/users.py: UserStore.user_for_token).
You write the integration: register the eight tools below on `mcp`, and make every call run AS THE CALLING USER.

How the server knows the user (task 9)
  The agent forwards the logged-in user's token on every MCP call as the HTTP header  Authorization: Bearer <token>  (you write that
  half in agent.py, task 9). A tool declares a `ctx: Context` parameter; FastMCP injects it and the HTTP request is
  ctx.request_context.request (Starlette: .headers). Write ONE helper `current_user_id(ctx) -> str` that
    - reads the bearer token, looks it up with UserStore().user_for_token(token)
    - raises ToolError("ERROR[UNAUTHENTICATED]: <what>. Next step: log in and retry.") when the header is missing, malformed or unknown
  and call it first in every tool. Never take a user id from a tool argument: the model must not be able to name another user.

The eight tools (names and arguments are fixed; each returns json.dumps(<what the TaskStore method returned>), a string)
  add_note(title: str, body: str)               list_notes()                          delete_note(note_id: int)
  add_task(title: str, details: str = "")       list_tasks(status: str = "")          set_task_status(task_id: int, status: str)
  delete_task(task_id: int)                     task_summary()
  status is "todo" | "in_progress" | "done". TaskStore raises TaskError for bad input: re-raise it as ToolError(str(error)).
  The docstring of each tool is its prompt for the model: say WHEN to use it and describe the arguments.
"""
import json
import os
import sys

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from app.mcp_server.taskstore import TaskError, TaskStore
from app.users import UserStore

mcp = FastMCP("tasks", host="0.0.0.0", port=int(os.getenv("MCP_PORT", "9000")))
store = TaskStore()
user_store = UserStore()


def current_user_id(ctx: Context) -> str:
    """Helper to extract user_id from the Authorization header of the request."""
    req = getattr(getattr(ctx, "request_context", None), "request", None)
    headers = getattr(req, "headers", {}) if req else {}
    auth = headers.get("authorization") or headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise ToolError("ERROR[UNAUTHENTICATED]: Missing or invalid Authorization header. Next step: log in and retry.")
    token = auth[7:].strip()
    user = user_store.user_for_token(token)
    if not user:
        raise ToolError("ERROR[UNAUTHENTICATED]: Invalid or expired token. Next step: log in and retry.")
    return user["user_id"]


@mcp.tool()
def add_note(title: str, body: str, ctx: Context) -> str:
    """Add a new note for the current user.

    Args:
        title: Short title for the note.
        body: Content body of the note.
    """
    user_id = current_user_id(ctx)
    try:
        return json.dumps(store.add_note(user_id, title, body))
    except TaskError as err:
        raise ToolError(str(err))


@mcp.tool()
def list_notes(ctx: Context) -> str:
    """List all notes belonging to the current user."""
    user_id = current_user_id(ctx)
    try:
        return json.dumps(store.list_notes(user_id))
    except TaskError as err:
        raise ToolError(str(err))


@mcp.tool()
def delete_note(note_id: int, ctx: Context) -> str:
    """Delete a note by its note_id.

    Args:
        note_id: The ID of the note to delete.
    """
    user_id = current_user_id(ctx)
    try:
        return json.dumps(store.delete_note(user_id, note_id))
    except TaskError as err:
        raise ToolError(str(err))


@mcp.tool()
def add_task(title: str, details: str = "", ctx: Context = None) -> str:
    """Add a new task for the current user.

    Args:
        title: Title of the task.
        details: Optional additional details for the task.
    """
    user_id = current_user_id(ctx)
    try:
        return json.dumps(store.add_task(user_id, title, details))
    except TaskError as err:
        raise ToolError(str(err))


@mcp.tool()
def list_tasks(status: str = "", ctx: Context = None) -> str:
    """List tasks belonging to the current user, optionally filtered by status.

    Args:
        status: Optional status to filter by ('todo', 'in_progress', 'done'). Leave empty for all tasks.
    """
    user_id = current_user_id(ctx)
    try:
        return json.dumps(store.list_tasks(user_id, status))
    except TaskError as err:
        raise ToolError(str(err))


@mcp.tool()
def set_task_status(task_id: int, status: str, ctx: Context = None) -> str:
    """Update the status of an existing task.

    Args:
        task_id: The ID of the task to update.
        status: The new status ('todo', 'in_progress', 'done').
    """
    user_id = current_user_id(ctx)
    try:
        return json.dumps(store.set_task_status(user_id, task_id, status))
    except TaskError as err:
        raise ToolError(str(err))


@mcp.tool()
def delete_task(task_id: int, ctx: Context = None) -> str:
    """Delete a task by its task_id.

    Args:
        task_id: The ID of the task to delete.
    """
    user_id = current_user_id(ctx)
    try:
        return json.dumps(store.delete_task(user_id, task_id))
    except TaskError as err:
        raise ToolError(str(err))


@mcp.tool()
def task_summary(ctx: Context) -> str:
    """Get a count summary of tasks grouped by status for the current user."""
    user_id = current_user_id(ctx)
    try:
        return json.dumps(store.summary(user_id))
    except TaskError as err:
        raise ToolError(str(err))


if __name__ == "__main__":
    # stdio cannot carry the Authorization header: the agent talks to this server over HTTP (MCP_URL)
    mcp.run(transport="streamable-http" if "--http" in sys.argv else "stdio")
