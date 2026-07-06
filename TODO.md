# TODO

## Immediate

- Build the remaining static-site sections and polish generated pages.
- Add a scheduler-level dry-run that exercises ingestion without publishing.
- Decide whether daily runs need a separate ingestion cap or deeper fetch pass.
- Add a live smoke test path for the seeded YouTube feeds when a backend is available.

## Next Project Slice

- Add any remaining AGY batch triage refinements for edge cases.
- Continue with scheduler behavior around failure handling and caps.

## Known Host Issue

- `.pytest_cache` on this machine is ACL-locked and cannot be deleted from the current shell session.
- The repo uses `.pytest-tmp/` and disables the cache provider through `pytest.ini` to avoid that issue.
