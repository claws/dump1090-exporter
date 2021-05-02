# This makefile has been created to help developers perform common actions.
# Most rules assumes it is operating in a virtual environment where the python
# command links to a Python3 executable.

# Define the specific version of Python you want Make to use when creating
# a virtual environment.
PYTHON := python3.8

# Do not remove this block. It is used by the 'help' rule when
# constructing the help output.
# help:
# help: dump1090exporter Makefile help
# help:


# help: help                  - display this makefile's help information
.PHONY: help
help:
	@grep "^# help\:" Makefile | grep -v grep | sed 's/\# help\: //' | sed 's/\# help\://'


# help: venv                  - create a virtual environment for development
.PHONY: venv
venv:
	@rm -Rf venv
	@$(PYTHON) -m venv venv --prompt d1090exp
	@/bin/bash -c "source venv/bin/activate && pip install pip --upgrade && pip install -r requirements.dev.txt"
	@/bin/bash -c "source venv/bin/activate && pip install -e ."
	@echo "Enter virtual environment using:\n\n\t$ source venv/bin/activate\n"


# help: clean                 - clean all files using .gitignore rules
.PHONY: clean
clean:
	@git clean -X -f -d


# help: scrub                 - clean all files, even untracked files
.PHONY: scrub
scrub:
	git clean -x -f -d


# help: check-style           - perform code format compliance check
.PHONY: check-style
check-style:
	@isort . --check-only --profile black
	@black --check src/dump1090exporter setup.py


# help: style                 - perform code style formatting
.PHONY: style
style:
	@isort . --profile black
	@black src/dump1090exporter setup.py


# help: check-types           - check type hint annotations
.PHONY: check-types
check-types:
	@cd src; mypy -p dump1090exporter --ignore-missing-imports


# help: check-lint            - run static analysis checks
.PHONY: check-lint
check-lint:
	@pylint --rcfile=.pylintrc dump1090exporter setup.py


# help: dist                  - create a wheel distribution package
.PHONY: dist
dist:
	@python setup.py bdist_wheel


# help: dist-upload           - upload a wheel distribution package
.PHONY: dist-upload
dist-upload: dist
	@twine upload dist/dump1090exporter-*-py3-none-any.whl


# Keep these lines at the end of the file to retain nice help
# output formatting.
# help:
