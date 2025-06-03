# M0: Build Plan & DevOps - Dataset Distiller

This document outlines the build plan, development operations (DevOps), and CI/CD strategy for the Dataset Distiller project.

## 1. Development Environment

*   **Language:** Python 3.11+
*   **Package Management:** Poetry
    *   `pyproject.toml` will define dependencies, scripts, and tool configurations.
    *   `poetry.lock` will ensure reproducible builds.
*   **Version Control:** Git, hosted on GitHub.
*   **IDE:** VS Code recommended, with extensions for Python, Black, Ruff, MyPy.
*   **`.env` files:** For managing local environment variables (API keys, database URLs). `.env.example` will be committed.

## 2. Code Quality & Linting

*   **Formatter:** Black (enforced via pre-commit hooks and CI).
    ```toml
    # pyproject.toml
    [tool.black]
    line-length = 88
    target-version = ['py311']
    ```
*   **Linter:** Ruff (enforced via pre-commit hooks and CI). Replaces Flake8, isort, pydocstyle, etc.
    ```toml
    # pyproject.toml
    [tool.ruff]
    line-length = 88
    select = ["E", "F", "W", "I", "UP", "PL", "T20"] # sensible defaults + opinionated ones
    ignore = ["E501"] # Handled by black

    [tool.ruff.lint.isort]
    known-first-party = ["backend"] # Or your app's name
    ```
*   **Type Checking:** MyPy (enforced via pre-commit hooks and CI).
    ```toml
    # pyproject.toml
    [tool.mypy]
    python_version = "3.11"
    warn_return_any = true
    warn_unused_configs = true
    strict = true # Start strict, loosen if necessary for specific modules/files
    # exclude = ["frontend/"] # If frontend JS/TS is present and causes issues
    ```
*   **Pre-commit Hooks:** Managed by `pre-commit`.
    *   Configuration in `.pre-commit-config.yaml`.
    *   Hooks for Black, Ruff, MyPy, and potentially others (e.g., check-yaml, check-toml).
    ```yaml
    # .pre-commit-config.yaml
    repos:
    -   repo: https://github.com/psf/black
        rev: 24.4.0 # Check for latest stable
        hooks:
        -   id: black
            language_version: python3.11
    -   repo: https://github.com/astral-sh/ruff-pre-commit
        rev: v0.4.1 # Check for latest stable
        hooks:
        -   id: ruff
            args: [--fix, --exit-non-zero-on-fix] # Auto-fix and fail on unfixable
            language_version: python3.11
    # -   repo: https://github.com/pre-commit/mirrors-mypy # Or directly use mypy
    #     rev: v1.9.0 # Check for latest stable
    #     hooks:
    #     -   id: mypy
    #         args: [--strict] # Ensure consistency with pyproject.toml
    #         # additional_dependencies: [ "pydantic", "sqlmodel" ] # Add types for libraries if needed
    ```
    *Note: MyPy hook in pre-commit might need careful configuration of `additional_dependencies` to match the project's environment if it has complex type interactions with libraries.* A simpler CI-only MyPy check might be preferred if local pre-commit MyPy becomes too slow or complex to configure. For now, we assume MyPy will be run directly by poetry in CI.

## 3. Testing Strategy

*   **Framework:** Pytest.
*   **Test Types:**
    *   **Unit Tests:** Focus on individual functions and classes (modules). Mock external dependencies (database, APIs).
    *   **Integration Tests:** Test interactions between components (e.g., API endpoint to service layer, service to database). May require a test database instance.
    *   **E2E Tests (M2/Future):** Test the full pipeline flow, potentially using small sample data. For CLI in M1, these could be bash scripts asserting output. For UI in M2, Playwright or Selenium could be used.
*   **Test Coverage:** Aim for >70% initially, increasing for critical modules. Measured using `pytest-cov`.
*   **Test Data:** Small, representative sample files for different types and scenarios (e.g., file with PII, empty file, malformed file).
*   **Running Tests:**
    *   `poetry run pytest`
    *   CI will run tests on every push/PR.

## 4. CI/CD Pipeline (GitHub Actions)

*   **Trigger:** On push to `main` and `develop` (if used), and on Pull Requests targeting `main`.
*   **Workflow File:** `.github/workflows/ci.yml`
*   **Jobs:**
    1.  **Lint & Format Check:**
        *   Checkout code.
        *   Set up Python 3.11.
        *   Install Poetry.
        *   Install dependencies (`poetry install --with dev`).
        *   Run `poetry run ruff check .`
        *   Run `poetry run black --check .`
    2.  **Type Check:**
        *   (Steps similar to above)
        *   Run `poetry run mypy backend` (or your app's main package).
    3.  **Tests:**
        *   (Steps similar to above)
        *   Set up services (e.g., PostgreSQL for integration tests).
            ```yaml
            services:
              postgres:
                image: postgres:15
                env:
                  POSTGRES_USER: testuser
                  POSTGRES_PASSWORD: testpassword
                  POSTGRES_DB: testdb
                ports: ['5432:5432']
                options: >-
                  --health-cmd pg_isready
                  --health-interval 10s
                  --health-timeout 5s
                  --health-retries 5
            ```
        *   Run `poetry run pytest --cov=backend --cov-report=xml` (adjust `backend` to your app name).
        *   Upload coverage report to Codecov or similar (optional but recommended).
            ```yaml
            # - name: Upload coverage to Codecov
            #   uses: codecov/codecov-action@v4
            #   with:
            #     token: ${{ secrets.CODECOV_TOKEN }}
            #     fail_ci_if_error: true
            ```

**GitHub Actions Workflow Example (`.github/workflows/ci.yml`):**
```yaml
name: CI

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres: # For integration tests requiring a database
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres # Simplified for example, use secrets for real DBs if needed outside CI
        ports: [ "5432:5432" ] # Host port:Container port
        options: --health-cmd="pg_isready" --health-interval=10s --health-timeout=5s --health-retries=5

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install Poetry
        uses: abatilo/actions-poetry@v3
        # with:
        #   poetry-version: "1.8.2" # Specify version if needed

      - name: Install dependencies
        run: poetry install --no-root --with dev # --no-root if not building/publishing a package from this workflow

      - name: Run linters
        run: |
          poetry run ruff check .
          poetry run black --check .

      - name: Run type checking
        run: poetry run mypy backend # Adjust 'backend' to your source directory

      - name: Run tests
        env: # Environment variables for tests, e.g., database connection
          DATABASE_URL: "postgresql://postgres:postgres@localhost:5432/postgres" # Example
        run: poetry run pytest -q --cov=backend --cov-report=xml # Adjust 'backend'

      # Optional: Upload coverage report
      # - name: Upload coverage to Codecov
      #   uses: codecov/codecov-action@v4
      #   with:
      #     token: ${{ secrets.CODECOV_TOKEN }} # Create this secret in your repo settings
      #     # files: ./coverage.xml # Path to coverage report
      #     fail_ci_if_error: true
```

## 5. Database Migrations (M2 onwards)

*   **Tool:** Alembic will be used for managing database schema migrations.
*   **Workflow:**
    *   Initialize Alembic in the project: `poetry run alembic init alembic`
    *   Configure `alembic/env.py` to use the SQLModel metadata and database URL.
    *   Generate migration scripts: `poetry run alembic revision -m "create_initial_tables"`
    *   Edit generated scripts to define schema changes.
    *   Apply migrations: `poetry run alembic upgrade head`
    *   Downgrade migrations: `poetry run alembic downgrade -1` (or specific version)
*   Migrations should be run as part of deployment and can be run manually in development.

## 6. Dependency Management

*   **Poetry:** Used for all Python dependencies.
    *   `poetry add <package>` for new dependencies.
    *   `poetry add <package> --group dev` for development dependencies.
    *   `poetry update` to update dependencies according to version constraints in `pyproject.toml`.
    *   Regular review of `poetry show --outdated` to identify potential updates.
*   **Security:**
    *   Consider tools like `poetry-plugin-check-lock` or GitHub's Dependabot to scan for vulnerabilities in dependencies.

## 7. Release Management (Future)

*   **Versioning:** Semantic Versioning (SemVer - `MAJOR.MINOR.PATCH`).
*   **Tagging:** Git tags for releases (e.g., `v0.1.0`).
*   **Changelog:** Maintain a `CHANGELOG.md` (can be automated with tools like `Commitizen` or `Release Please` if desired).
*   **PyPI Publishing (If library):** If the project or parts of it are intended to be published as a library, Poetry's build and publish commands will be used.
    *   `poetry build`
    *   `poetry publish --username <pypi_username> --password <pypi_password_or_token>`

This plan provides a solid DevOps foundation. It will be reviewed and updated as the project evolves.
