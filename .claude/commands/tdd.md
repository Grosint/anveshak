Enforce test-driven development workflow.

1. Write failing tests first (RED)
   - Define the interface/function signature
   - Write tests that describe expected behaviour
   - Run: uv run pytest {test_file} — confirm they FAIL

2. Write minimal implementation to pass (GREEN)
   - Implement only what is needed to pass the tests
   - No extra features, no gold-plating
   - Run: uv run pytest {test_file} — confirm they PASS

3. Wiring check (CONNECT)
   - For every new function: is it called somewhere?
   - For every new async loop/task: is it registered in lifespan/startup?
   - For every new UI component: is it imported and rendered in a route?
   - For every new API router: is it registered in main.py?
   - For every new button/action: does it trigger the correct API call?
   - Grep for each new public symbol and verify it has at least one caller
   - If using agents: explicitly verify agents modified EXISTING files, not just created new ones
   - Write tests for wiring (e.g., assert function name appears in lifespan source)

4. Refactor (IMPROVE)
   - Clean up code while keeping tests green
   - Run: uv run pytest {test_file} — confirm still PASS

5. Regression check
   - Run: uv run pytest tests/unit/ — confirm ALL existing tests still pass
   - Run: cd frontend && npx tsc --noEmit — confirm zero TS errors

6. Coverage check
   - Run: uv run pytest --cov=src --cov-report=term-missing
   - Assert >= 80% coverage on new code

Hardware rule: tests MUST pass on CPU with default medium/nano/cpu config.
Never assume GPU in test environment.
