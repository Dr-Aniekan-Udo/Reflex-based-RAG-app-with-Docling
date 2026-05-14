# Troubleshooting

## Common Errors

### `TypeError: bad operand type for unary ~: 'list'`
**Cause**: Bitwise `~` used on a list in a component prop.
**Fix**: Replace `~State.my_list` with `State.my_list.length() == 0`.

### `TypeError: unsupported operand type(s) for &: 'list' and 'int'`
**Cause**: Bitwise `&` between a list and an integer in a component prop.
**Fix**: Use `rx.cond` with explicit boolean conditions.

### `PicklingError` or `TypeError` during state sync
**Cause**: A non-serializable object (Docling Document, PIL Image, Chroma instance) was stored in `rx.State`.
**Fix**: Move the object to `core/session_registry.py`. Only store plain dicts/lists in state.

### Background task sees empty upload data
**Cause**: Data was stored in a private `_variable` and accessed from `@rx.event(background=True)`.
**Fix**: Use public state variables or a module-level/session-scoped store.

### Agent responds with "Please upload and process documents first"
**Cause**: The agent was not created, or the session registry does not have an entry for the current `session_id`.
**Fix**: Ensure `BaseState.on_load` ran and generated a `session_id`. Check that vectorization completed successfully.

### Cross-user data contamination
**Cause**: Global singletons for vectorstore/agent were used without session isolation.
**Fix**: Use `session_registry` keyed by `session_id`.

### Chroma `OperationalError: database is locked`
**Cause**: Multiple async tasks accessed the same in-memory Chroma/SQLite instance concurrently.
**Fix**: Each session must have its own Chroma instance. Do not share instances across sessions.

## Performance Tips

- **PDF Batching**: Large PDFs are automatically batched in 50-page chunks to manage memory.
- **CPU PyTorch**: The project pins CPU-only PyTorch wheels to avoid GPU bloat.
- **Session Cleanup**: Call `Clear All` to free memory, or wait for the tab to close.
