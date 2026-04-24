# Ergonomic aliases for common developer workflows.
# The real work lives in scripts/ and `python -m` entrypoints; this Makefile is
# a thin veneer so `make smoke` works the same as `./scripts/smoke.sh`.

.PHONY: smoke test mypy lint help

help:
	@echo "Targets:"
	@echo "  smoke  — run the IP-009 end-to-end smoke harness"
	@echo "  test   — run the pytest suite (needs TEST_MONGO_URI for live-DB tests)"
	@echo "  mypy   — mypy --strict on the production modules"
	@echo "  lint   — ruff check ."

smoke:
	./scripts/smoke.sh

test:
	python -m pytest

mypy:
	mypy --strict $$(find oss_profanity -name '*.py' -not -path '*/tests/*')

lint:
	ruff check .
