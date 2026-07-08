.PHONY: setup update clean test build

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

clean:
	@echo "Removing conda environment..."
	conda env remove -n air-quality

build:
	@echo "Cleaning up old builds..."
	rm -rf dist lambda_function.zip
	mkdir -p dist
	@echo "Installing production dependencies into dist folder..."
	pip install --no-dependencies --no-cache-dir -r src/requirements.txt -t dist/
	@echo "Copying source code..."
	cp -r src/air_quality dist/
	@echo "Creating deployment package..."
	cd dist && zip -r ../lambda_function.zip .
	@echo "Build complete: lambda_function.zip is ready for AWS."
