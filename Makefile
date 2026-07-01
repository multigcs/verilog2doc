
all: format check

format:
	ruff format verilog2doc.py

check:
	ruff check verilog2doc.py

fix:
	ruff check --fix verilog2doc.py
