# Testing & Code Quality

Skillware maintains high standards for code quality and reliability. Before submitting a Pull Request, please ensure your code passes all linting and testing checks.

## Quick Setup

Install framework tests, lint tools, and optional SDK extras in one go (matches GitHub Actions CI):

```bash
pip install -e ".[dev,all]"
```

Or use the dev pointer file:

```bash
pip install -r requirements.txt
```

## 1. Code Formatting (Black)

We use **Black** as our uncompromising code formatter. It ensures that all code looks the same, regardless of who wrote it, eliminating discussions about style.

### Installation
```bash
pip install black
```

### Usage
Run Black on the entire repository to automatically fix formatting issues:
```bash
python -m black .
```

Run `python -m black --check .` to verify formatting without writing files. GitHub Actions runs the same check before flake8 and pytest.

## 2. Linting (Flake8)

We use **Flake8** to catch logic errors, unused imports, and other code quality issues that Black does not handle.

### Installation
```bash
pip install flake8
```

### Usage
Run Flake8 from the root of the repository:
```bash
python -m flake8 .
```

**Note:** We aim for zero warnings/errors. Do not suppress errors with `# noqa` unless absolutely necessary and justified.

## 3. Unit Tests (Pytest)

We use **pytest** for unit testing. All new features and bug fixes must be accompanied by relevant tests.

### Installation
```bash
pip install pytest
```

### Usage

**CI and framework tests** — GitHub Actions runs only the `tests/` tree:

```bash
python -m pytest tests/
```

This covers the loader, CLI, issuer rules, and integration tests under `tests/skills/`. New skill PRs do not need edits to `.github/workflows/ci.yml` when they add co-located skill tests.

### Testing individual skills (local / pre-PR)

Every skill ships with a `test_skill.py` boilerplate. Run it **locally** before opening a skill PR (not in CI):

```bash
python -m pytest skills/<category>/<skill_name>/test_skill.py
```

Install any packages listed in the skill's `manifest.yaml` `requirements` before running co-located tests (for example `pip install web3` for DeFi skills). Skill deps are declared in the manifest, not added to CI per skill.

### Writing Tests
- **Framework tests**: Place core and cross-skill integration tests in `tests/` (including `tests/skills/` when appropriate).
- **Skill bundle tests**: Place skill-specific logic in `skills/<category>/<name>/test_skill.py` and run locally.
- Use `conftest.py` for shared fixtures (e.g., mocking LLM clients).

## Pre-Commit Checklist

Before pushing your code, run the following commands to ensure your changes are ready for review:

1. `skillware list` (Verify install and path resolution are working)
2. `python -m black --check .` (Verify formatting; use `python -m black .` to fix)
3. `python -m flake8 .` (Check quality)
4. `python -m pytest tests/` (Verify framework functionality — same scope as CI)
5. `python -m pytest skills/<category>/<skill_name>/test_skill.py` when your PR touches that skill (local only)
