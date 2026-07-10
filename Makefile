.PHONY: setup update clean test lint build compile

setup:
	@echo "Syncing uv virtual environment..."
	uv sync
	@echo "Setup complete! Run 'source .venv/bin/activate' to start."

update:
	@echo "Updating uv virtual environment..."
	uv sync

test:
	@echo "Running pytest suite..."
	uv run pytest -o pythonpath=src tests/

lint:
	@echo "Running Ruff linter..."
	uv run ruff check src/

clean:
	@echo "Removing virtual environments..."
	rm -rf .venv
	rm -rf .conda

build:
	@echo "Cleaning up old builds..."
	rm -rf dist python code_function.zip python_layer.zip
	
	@echo "Preparing Code package..."
	mkdir -p dist
	cp -r src/air_quality/ dist/
	cd dist && zip -r ../code_function.zip .
	rm -rf dist

	@echo "Installing production dependencies layer ..."
	mkdir python
	uv export --no-dev --no-hashes --format requirements-txt -o temp-requirements.txt
	uv pip install --no-deps --no-cache-dir -r temp-requirements.txt -t python/
	rm temp-requirements.txt
	
	find python/ -type d -name "__pycache__" -exec rm -rf {} +
	find python/ -type d -name "*.dist-info" -exec rm -rf {} +
	find python/ -type d -name "*.egg-info" -exec rm -rf {} +

	zip -9 -r python_layer.zip python
	rm -rf python

	@echo "Build complete: code_function.zip and python_layer.zip are ready."

compile:
	@echo "Updating lockfile..."
	uv lock