# Editing objects while agents are working

The Objects editor checks whether a .node.json file changed after you opened
it. If an agent or another editor saved a newer version, Save and Revert report
a conflict instead of replacing that version with your older copy.

Your local edits and undo history stay in the editor. Use **Copy local JSON** to
keep your work, then **Reload disk version** to load the current object. Reload
asks before discarding local edits. Reapply the changes you want to keep after
reviewing the current object. There is no automatic merge or force overwrite.

This applies to Objects editing, including Save and Revert. Assets manifest
editing is unchanged.

## Object API

GET /api/nodes/<relative-path> returns:

~~~json
{
  "path": "entities/hero.node.json",
  "data": {"name": "Hero"},
  "version": "<SHA-256 of the file bytes>"
}
~~~

Send that version back with PUT /api/nodes/<relative-path>:

~~~json
{
  "data": {"name": "Updated Hero"},
  "baseVersion": "<version returned by GET>",
  "action": "save"
}
~~~

A successful PUT returns ok, path, the actual changes, and the new version.
Use the new version for the next write. A stale version returns HTTP 409 with
code "edit_conflict", the current data and version, and an error message.
A conflict does not write the object or add a successful operation-log entry.

**Write compatibility:** PUT now requires baseVersion; missing versions return
HTTP 428. Invalid version or object-data types return HTTP 400. Older API clients
must read before writing and retain the version returned by each successful save.
Reload Dashboard pages after updating the server and editor together.

Versions cover the original bytes, so even external formatting-only edits
produce a conflict. GET parses and hashes the same byte snapshot. The client
does not generate its own hash or replace a stale version with one from a
conflict response.

## Concurrency and durability limits

The server serializes writes to the same object within one Dashboard process.
It writes a temporary file in the same directory and atomically replaces the
object, preserving its permission mode and cleaning up on failure.

The content hash also detects direct file changes made by agents before the
final check. It does not provide a transaction against arbitrary external
writers or a second Dashboard process writing between that check and replacement.
Strict exclusion would require all writers to share a write protocol. Atomic
replacement prevents partial files, but is not a promise of power-loss durability.

## Validation

Run the focused suite from the source checkout with its Python dependencies:

~~~sh
python -B -m pytest tests/base/web/test_object_versions.py -q
~~~

HTTP tests use temporary projects and the real Dashboard handler. Browser tests
mount the actual Objects editor and Dashboard styles against that handler using
Playwright Chromium. They skip if the browser is absent; install it with
python -m playwright install chromium --no-shell to run them. No agents or paid APIs are
needed. This suite does not exercise a complete agent-driven game build.
