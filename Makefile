PYTHON_INSTALLED := $(shell command -v python3 2> /dev/null)
GOOD := \033[1;32m[+]\033[1;m

install:
ifndef PYTHON_INSTALLED
	@echo "python3 not installed, but can be installed with:"
	@echo
	@echo "\tsudo apt install python3"
	@echo
	@echo "or using your favorite package manager."
	@echo
	@exit 1
endif
	@sudo python3 -m pip install -e .
	@echo
	@echo "${GOOD} Wi-Fi Share is setup! Enter 'wifi-share [options]' in a terminal to use it"

uninstall:
	@sudo python3 -m pip uninstall -y wifi-share
	@echo
	@echo "${GOOD} Wi-Fi Share has been removed"
