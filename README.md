<p align="center">
  <img src="https://github.com/thanosgn/wifi-share/blob/master/logos/LOGOTYPE_H.svg" height="50%" width="50%" alt="Wi-Fi Share">
  <br>
  Instantly share a Wi-Fi connection using a QR code.<br>
  Scan it with a phone to connect automatically.
</p>

<p align="center">
  <a href="/LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-brightgreen.svg"></a>
  <img alt="Python 3.10 or newer" src="https://img.shields.io/badge/python-3.10%2B-blue.svg">
  <img alt="Linux, Windows and macOS" src="https://img.shields.io/badge/platform-linux%20%7C%20windows%20%7C%20macos-lightgrey.svg">
</p>

## Requirements

- Python 3.10 or newer.
- Linux: NetworkManager with `nmcli` available on `PATH`.
- macOS: the built-in `networksetup`, `ipconfig`, `system_profiler`, and `security` tools. Swift is used only as a final SSID-detection fallback when available.
- Windows: `netsh`; English and Italian system output are supported.

Linux installations using only iwd, wpa_supplicant, or systemd-networkd are not currently supported.

## Installation

[`uv`](https://docs.astral.sh/uv/) is the recommended installer on all three platforms.

### macOS and Linux

```bash
git clone https://github.com/alsd4git/wifi-share.git
cd wifi-share
uv tool install .
wifi-share
```

### Windows PowerShell

```powershell
git clone https://github.com/alsd4git/wifi-share.git
Set-Location wifi-share
uv tool install .
wifi-share
```

The optional Makefile is a convenience wrapper around the same `uv tool` commands:

```bash
make install
make uninstall
```

It does not require `sudo` and is not needed on Windows.

For development, create the repository-local environment and run the entrypoint with:

```bash
uv sync --locked
uv run wifi-share
```

`pyproject.toml` is the canonical dependency declaration; `uv.lock` provides reproducible development and CI installations.

## Usage

Running without arguments reads the active Wi-Fi connection and prints a QR code in the terminal:

```bash
wifi-share
```

Common examples:

```bash
# Select a saved network interactively
wifi-share --list

# Supply the SSID and password without reading system credentials
wifi-share --ssid "Guest Wi-Fi" --password "secret"

# Write an SVG using a safe filename derived from the SSID
wifi-share --image

# Write to an explicit PNG path
wifi-share --image guest.png
```

Use `wifi-share --help` for the complete option list.

`--verbose` includes the retrieved Wi-Fi password in terminal output. Use it only when exposing that credential in the current terminal is acceptable.

## Platform notes

### macOS

macOS may hide the current SSID unless Location Services access is available. Wi-Fi Share tries the built-in network tools first, uses CoreWLAN through Swift only as a final fallback, and then offers the saved-network picker.

Saved credentials are read from Keychain with `security`. macOS may show an authorization prompt the first time a password is requested.

### Windows

Profiles and credentials are read using `netsh`. English and Italian output, including open networks, are covered by automated tests. Other Windows display languages are not guaranteed.

### Linux

Wi-Fi Share reads the active NetworkManager connection directly and uses its profile to retrieve the SSID and saved PSK. If multiple saved profiles share an SSID, `--list` displays the associated profile name so the intended one can be selected.

## Testing

```bash
uv run python -m unittest discover -s tests -v
uv run python -m compileall -q wifi_share.py tests
uv build
```

GitHub Actions runs these checks on Ubuntu, macOS, and Windows with every supported Python minor version. The hosted runners validate parsing, CLI behavior, and packaging with mocked system output; they cannot access real Wi-Fi hardware or saved credentials.

Before a release, manually smoke-test each platform with an active network, `--list`, an open network, a saved password, SVG output, and PNG output.

## Example

<p align="center">
  <img src="https://thanosgn.github.io/assets/wifi-share-example.png" alt="Wi-Fi Share terminal QR code example">
</p>
