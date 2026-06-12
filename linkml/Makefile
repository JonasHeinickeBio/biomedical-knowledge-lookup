# LinkML Makefile for biomedical knowledge lookup

.PHONY: all generate-python generate-json generate-owl validate clean help

# Default target
all: generate-python

# Generate Python Pydantic models from schema
generate-python:
	cd .. && poetry run linkml generate pydantic linkml/biomedical_knowledge_schema.yaml > src/knowledge_lookup/generated_models/biomedical_knowledge_models.py

# Generate JSON Schema from LinkML
generate-json:
	poetry run linkml generate json \
		--input linkml/biomedical_knowledge_schema.yaml \
		--output linkml/biomedical_knowledge_schema.json

# Generate OWL RDF from LinkML
generate-owl:
	poetry run linkml generate owl \
		--input linkml/biomedical_knowledge_schema.yaml \
		--output linkml/biomedical_knowledge_schema.ttl

# Validate the schema
validate:
	poetry run linkml validate linkml/biomedical_knowledge_schema.yaml

# Generate documentation
generate-docs:
	poetry run linkml generate html \
		--input linkml/biomedical_knowledge_schema.yaml \
		--output linkml/docs/index.html

# Clean generated files
clean:
	rm -f src/knowledge_lookup/generated_models/biomedical_knowledge_models.py
	rm -f linkml/*.json linkml/*.ttl
	rm -f linkml/docs/*.html

# Show help
help:
	@echo "LinkML Makefile for biomedical knowledge lookup"
	@echo ""
	@echo "Available targets:"
	@echo "  generate-python  - Generate Pydantic models from schema"
	@echo "  generate-json    - Generate JSON Schema"
	@echo "  generate-owl     - Generate OWL RDF"
	@echo "  validate         - Validate the schema"
	@echo "  generate-docs    - Generate HTML documentation"
	@echo "  clean            - Remove generated files"
	@echo "  help             - Show this help message"
