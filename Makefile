.PHONY: setup update clean test lint build 

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
	zip -r python_layer.zip python
	rm -rf python

	@echo "Build complete: code_function.zip and python_layer.zip are ready."
