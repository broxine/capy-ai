.PHONY: test smoke-recon

test:
	pytest

smoke-recon:
	python -m bughunter_hive.cli recon --target https://example.com --program demo --scope-domain example.com
