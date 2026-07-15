# Core documentation delivery policy

Markdown files under each `documentation/` directory are the versioned source
of truth. Generated `documentation/wiki/` trees are build artifacts and are
not tracked.

Brain Explorer is the normal documentation experience for the core. Its local
server reads the versioned Markdown sources and exposes them together with the
rest of the agent's mirrors, so core development does not run `wiki generate`
and does not keep compiled wiki output on disk.

The Documentation Utils `generate` command remains available as an explicit,
standalone export tool for consumers that need a static wiki. Its output must
stay outside version control. The utility's own `serve` command is retained for
serving one of those explicit exports; it is not the core documentation server.
