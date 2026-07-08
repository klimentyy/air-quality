.PHONY: setup update clean test

setup:
	@echo "Creating conda environment from environment.yml..."
	conda env create -f environment.yml
	@echo "Setup complete! Run 'conda activate cz-air-pipeline' to start."

update:
	@echo "Updating conda environment..."
	conda env update -f environment.yml --prune

test:
	@echo "Running pytest suite..."
	conda run -n cz-air-pipeline pytest tests/

clean:
	@echo "Removing conda environment..."
	conda env remove -n cz-air-pipeline