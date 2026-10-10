# Growth Copilot

An AI growth assistant for Xiaohongshu creators.

Growth Copilot is built upon the open-source [Easel](https://github.com/ZJU-REAL/Easel) project.
Its Apache-2.0 [LICENSE](LICENSE), copyright notices and attribution are preserved.
Internal Easel packages and legacy capabilities remain intact.

Phase 3 implements persistent Account/Profile versions, structured AI Diagnosis,
human confirmation and a database-backed Dashboard. Research, Topics and Studio
are explicitly Coming Soon. Positioning is a hypothesis, not a performance guarantee.

See the [current setup guide](README.md), [data layer](docs/growth-data-layer.md)
and [Phase 3 details](docs/growth-phase3.md). Keep model credentials in the Git-ignored local `.env`; restart the backend after editing it.
An unconfigured model produces an explicit error, never fabricated fallback output.

The complete [upstream English README](docs/upstream-README.en.md) is archived for
technical reference and attribution; its original relative links assume the repository root.
