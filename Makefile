# Makefile — Alexander Group (Odoo 19). Fase 0.
# Ningún objetivo despliega, se conecta a servidores ni toca producción.

PYTHON ?= python3

.DEFAULT_GOAL := help

.PHONY: help validate test lint format-check security-check structure stack-compare

help: ## Muestra esta ayuda
	@echo "Alexander Group — Odoo 19 (Fase 0)"
	@echo ""
	@echo "Objetivos disponibles:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

validate: ## Ejecuta los validadores de repositorio y de módulos
	$(PYTHON) tools/validate_repository.py
	$(PYTHON) tools/validate_modules.py

test: ## Ejecuta la batería de pruebas con pytest
	$(PYTHON) -m pytest

lint: ## Verifica formato de código Python (black --check)
	$(PYTHON) -m black --check .

format-check: ## Alias de lint (verificación de formato sin modificar)
	$(PYTHON) -m black --check .

security-check: ## Ejecuta solo la validación de seguridad del repositorio
	$(PYTHON) tools/validate_repository.py

structure: ## Muestra la estructura del repositorio
	@find . -not -path './.git/*' -not -path '*/__pycache__/*' \
		-not -path './.pytest_cache/*' | sort

stack-compare: ## Compara manifiestos Justgroup vs Doralex (sin escribir en PROD)
	$(PYTHON) tools/justgroup_doralex_stack_compare.py || test $$? -eq 1
