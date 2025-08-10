# Repository Guidelines

This guide helps contributors work effectively in trend-momentum-x. Keep changes small, type-safe, and well-tested.

## Project Structure & Modules
- `main.py`: Strategy entrypoint and runtime loop.
- `strategy/`: Core logic (`trend_analysis.py`, `signals.py`, `orderbook.py`, `risk_manager.py`, `exits.py`).
- `utils/`: Shared helpers (`config.py`, `logger.py`).
- `tests/`: Pytest suite (`test_*.py`, classes `Test*`, functions `test_*`).
- `pyproject.toml`: Tooling (ruff, mypy, pytest, coverage) and deps.

## Build, Test, and Development
- Install deps: `uv sync`
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`
- Type check: `uv run mypy .`
- Run tests: `uv run pytest -v`
- Coverage: `uv run pytest --cov --cov-report=term-missing`
- Run strategy (paper): `uv run python main.py`
- Run strategy (live): `TRADING_MODE=live uv run python main.py`

## Coding Style & Naming
- Python 3.12, 4-space indent, max line length 100.
- Prefer explicit types and clear, small functions.
- Naming: snake_case for files/functions; PascalCase for classes; constants UPPER_CASE.
- Tools: ruff (rules: E,W,F,I,N,UP,B,SIM,ASYNC) and mypy (strict-ish per config).

## Testing Guidelines
- Framework: pytest with asyncio (`pytest-asyncio` auto mode).
- Markers: `unit`, `integration`, `slow` (select via `-m "unit and not slow"`).
- Put tests under `tests/` with `test_*.py`; mirror module names when possible.
- Aim for meaningful coverage on `strategy/`, `utils/`, and `main.py`.

## Commit & Pull Requests
- Use Conventional Commits seen in history: `feat:`, `fix:`, `docs:`, `test:`.
- Commit example: `fix(risk): correct stop calculation for shorts`.
- Before opening a PR, ensure: ruff, mypy, and tests pass; add/adjust tests; update README/CLAUDE.md if behavior changes.
- PR description: problem, approach, trade-offs, and test evidence; link related issues.

## Security & Configuration
- Never commit secrets. Use `.env` for `PROJECT_X_*` and trading params.
- Validate config locally before live trading; start with paper mode.
- Keep logging sensible; avoid sensitive data in logs.

## Agent Notes
- For agent-specific guidance, see `CLAUDE.md`, `GEMINI.md`, and `GROK.md`.
