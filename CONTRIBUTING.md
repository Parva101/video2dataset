# Contributing

Thanks for contributing to `@parva101/video2dataset`.

## Development setup

1. Fork and clone the repository
2. Create and activate a virtual environment
3. Install dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Local checks

Run these before opening a PR:

```bash
ruff check .
pytest
python -m py_compile __init__.py
```

## Branch and commit guidelines

- Create a feature branch from `main`
- Use focused commits with clear messages
- Keep PRs scoped to one logical change

## Pull request checklist

- [ ] Code is formatted and linted
- [ ] Tests added/updated where needed
- [ ] README and changelog updated if behavior changed
- [ ] No secrets or credentials committed

## Reporting bugs

Use the Bug Report issue template and include:

- FiftyOne version
- Python version
- OS
- Reproducible steps
- Relevant logs/tracebacks

## Feature requests

Use the Feature Request template with:

- Problem statement
- Proposed behavior
- Alternatives considered

