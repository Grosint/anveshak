Enforce test-driven development workflow.

1. Write failing tests first (RED)
   - Define the interface/function signature
   - Write tests that describe expected behaviour
   - Run: uv run pytest {test_file} — confirm they FAIL

2. Write minimal implementation to pass (GREEN)
   - Implement only what is needed to pass the tests
   - No extra features, no gold-plating
   - Run: uv run pytest {test_file} — confirm they PASS

3. Refactor (IMPROVE)
   - Clean up code while keeping tests green
   - Run: uv run pytest {test_file} — confirm still PASS

4. Coverage check
   - Run: uv run pytest --cov=src --cov-report=term-missing
   - Assert >= 80% coverage on new code

Hardware rule: tests MUST pass on CPU with default medium/nano/cpu config.
Never assume GPU in test environment.
