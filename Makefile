.PHONY: test generate doctor start stop

test:
	python -m compileall services/ollama-gateway/app tools
	python -m pytest services/ollama-gateway/tests

generate:
	python tools/generate_litellm_config.py --env .env

doctor:
	./scripts/doctor.sh

start:
	./scripts/start.sh

stop:
	./scripts/stop.sh
