UV_INSTALLED := $(shell command -v uv 2> /dev/null)
GOOD := \033[1;32m[+]\033[1;m

install:
ifndef UV_INSTALLED
	@echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/"
	@exit 1
endif
	@uv tool install --force .
	@echo
	@echo "${GOOD} Wi-Fi Share is setup! Enter 'wifi-share [options]' in a terminal to use it"

uninstall:
	@uv tool uninstall wifi-share
	@echo
	@echo "${GOOD} Wi-Fi Share has been removed"
