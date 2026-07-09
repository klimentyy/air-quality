.PHONY: setup update clean test lint build compile

setup:
	@echo "Creating conda environment from environment.yml..."
	conda env create -f environment.yml
	@echo "Setup complete! Run 'conda activate air-quality' to start."

update:
	@echo "Updating conda environment..."
	conda env update -f environment.yml --prune

test:
	@echo "Running pytest suite..."
	conda run -n air-quality pytest tests/

lint:
	@echo "Running Ruff linter..."
	conda run -n air-quality ruff check src/

clean:
	@echo "Removing conda environment..."
	conda env remove -n air-quality

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
	pip install --no-dependencies --no-cache-dir -r src/requirements.txt -t python/
	
	find python/ -type d -name "__pycache__" -exec rm -rf {} +
	find python/ -type d -name "*.dist-info" -exec rm -rf {} +
	find python/ -type d -name "*.egg-info" -exec rm -rf {} +

	zip -9 -r python_layer.zip python
	rm -rf python

	@echo "Build complete: code_function.zip and python_layer.zip are ready."

compile:
	@echo "Compiling minimal production/test dependencies..."
	conda run -n air-quality pip-compile src/requirements.in --output-file=src/requirements.txt
	conda run -n air-quality pip-compile src/requirements-test.in --output-file=src/requirements-test.txt