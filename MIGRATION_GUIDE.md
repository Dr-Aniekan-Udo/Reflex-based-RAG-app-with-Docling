# Streamlit to Reflex Migration Guide

This guide summarizes the key differences when porting a Streamlit RAG app to Reflex, and the pitfalls to avoid.

## State Management

| Streamlit | Reflex |
|-----------|--------|
| `st.session_state` — plain Python dict, no serialization | `rx.State` — must be JSON serializable |
| Can store any object (PIL, DB connections, custom classes) | Can only store `str`, `int`, `float`, `bool`, `list`, `dict` |
| Single-threaded script rerun model | Async event loop with background tasks |

**Fix**: Keep all non-serializable objects in a pure Python session registry (`core/session_registry.py`).

## File Uploads

| Streamlit | Reflex |
|-----------|--------|
| `st.file_uploader` returns `UploadedFile` objects | `rx.upload` + `rx.UploadFile` |
| Files can be stored in `st.session_state` directly | File bytes are NOT serializable — do not store in `rx.State` |

**Fix**: Store uploaded bytes in a module-level buffer keyed by `session_id`, or pass them directly as arguments to event handlers.

## Concurrency

| Streamlit | Reflex |
|-----------|--------|
| Sequential script execution | `@rx.event(background=True)` for async tasks |
| No need for locks | Must use `async with self:` to lock state updates |

**Fix**: Use `async with self:` around all state mutations inside background tasks.

## Component Props & Logic

| Streamlit | Reflex |
|-----------|--------|
| Python logic runs server-side only | Component props are transpiled to JavaScript |
| Bitwise operators work on any type | Bitwise `~`, `&` on lists/objects crash or produce invalid JS |

**Fix**: Use explicit boolean comparisons: `disabled=(State.list.length() == 0)`.

## Chat Streaming

| Streamlit | Reflex |
|-----------|--------|
| `st.write_stream(generator)` | Manual state updates in a background task with `async with self:` |
| Generator yields directly to UI | Tokens are accumulated and assigned to state vars incrementally |

**Fix**: Accumulate tokens in a local variable, then assign to state inside `async with self:` blocks.

## Multi-User Isolation

| Streamlit | Reflex |
|-----------|--------|
| Each browser tab is a separate process/session | All users share the same backend process |
| Global variables are safe per user | Global variables are shared across ALL users |

**Fix**: Use a `session_id` stored in `BaseState` and a `session_registry` to isolate per-user objects.
