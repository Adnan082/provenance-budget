.PHONY: trace traces-live oracle budget labellers baselines headline test-final test typecheck

trace:
	uv run python -m pb.cli trace

traces-live:
	uv run python -m pb.cli traces-live

oracle:
	uv run python -m pb.cli oracle

budget:
	uv run python -m pb.cli budget

labellers:
	uv run python -m pb.cli labellers

baselines:
	uv run python -m pb.cli baselines

headline:
	uv run python -m pb.cli headline

test-final:
	uv run python -m pb.cli test-final

test:
	uv run pytest

typecheck:
	uv run mypy --strict src/pb/enforce
