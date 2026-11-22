# Public-source privacy rules

Real deployment configuration and operational evidence belong in ignored local
files, not this repository. Use `deployment.example.json` and environment-variable
placeholders in documentation and tests.

Do not commit account IDs, concrete resource ARNs/IDs, personal profile names,
private repository/site destinations, credentials, local user paths or CLI state.
Use generated dummy identifiers in unit tests. Keep private migration evidence
under `.private/` and never publish backup refs or bundles containing old history.

Before pushing, run the public-configuration checks. If sensitive information was
already published, deleting the current file does not remove older Git objects.
History cleanup requires explicit approval and coordination with collaborators.
Existing clones, forks and provider caches may require separate cleanup.
