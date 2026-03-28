<p align="center">
    <img src="https://github.com/thanosgn/wifi-share/blob/master/logos/LOGOTYPE_H.svg" height="50%" width="50%">
    <p align="center">Instantly share your WIFI connection using a QR code. <br>
    Scan it with your phone and connect automatically.</p>
    <p align="center">
        <a href="/LICENSE"><img alt="Software License" src="https://img.shields.io/badge/license-MIT-brightgreen.svg"></a>
        <img alt="Python version" src="https://img.shields.io/badge/python-3.12%2B-blue.svg">
        <img alt="Platform support" src="https://img.shields.io/badge/platform-linux%20|%20windows%20|%20macos-lightgrey.svg">
    </p>
</p>


## Installation
### With `uv` (recommended)
```bash
uv sync
uv run wifi-share
```
`uv sync` reads `pyproject.toml`, creates a local environment automatically, and installs the project's locked dependencies.
`uv run wifi-share` uses the console entrypoint defined in the project, so you can start the tool without remembering the Python filename.

### With `make`
```
git clone https://github.com/thanosgn/wifi-share.git
cd wifi-share
sudo make install
```
You can uninstall at any time using `make uninstall`.
If you don't have `make`, you can always use `uv sync` or `pip install -e .` to install the necessary requirements.

Obviously `python3` and `pip3` are required.

The project targets modern Python 3 releases and is packaged so it can be installed with `uv`, `pip`, or the provided Makefile.

On Windows you can use `cmd` to install and use the script.

## Usage (default)
```
wifi-share
```

If you did not use the provided Makefile or `uv`, and you don't have `wifi-share` in your executable path, then using `python3 wifi-share.py` will do just fine.

If you want to understand what `uv` is doing under the hood:
* it reads dependencies from `pyproject.toml`
* it creates a local `.venv` folder in the project
* it installs the exact versions listed in the project metadata
* it exposes the `wifi-share` command from the `[project.scripts]` entrypoint

See also the [_Notes_](#notes) section below.

## Example
<p align="center">
  <img src="https://thanosgn.github.io/assets/wifi-share-example.png">
</p>

## Options
All the below arguments are optional.
The default behavior is to generate a QR code on the terminal for the network you are currently connected.
However, there are many options available if you want something besides the default scenario.
```
usage: wifi-share [-h] [-v] [-i [IMAGE]] [-s SSID] [-p PASSWORD] [-l]

 __          ___        ______ _      _____ _
 \ \        / (_)      |  ____(_)    / ____| |
  \ \  /\  / / _ ______| |__   _    | (___ | |__   __ _ _ __ ___
   \ \/  \/ / | |______|  __| | |    \___ \| '_ \ / _` | '__/ _ \
    \  /\  /  | |      | |    | |    ____) | | | | (_| | | |  __/
     \/  \/   |_|      |_|    |_|   |_____/|_| |_|\__,_|_|  \___|

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Enable verbose output.
  -i [IMAGE], --image [IMAGE]
                        Specify a filename for the generated QR code image.
                        (.png or .svg). Default: [WIFINAME].svg. If -i/--image
                        argument is not provided the QR code will be displayed
                        on the console.
  -s SSID, --ssid SSID  Specify the SSID you want the password of. Default:
                        the SSID of the network you are currently connected.
  -p PASSWORD, --password PASSWORD
                        Specify a desired password to be used instead of the
                        stored one.
  -l, --list            Display a list of stored Wi-Fi networks (SSIDs) to
                        choose from.

```

## Notes

On macOS the `airport` utility is used to access saved Wi-Fi information. You do not need `sudo` to run the script, but you will get a popup prompt asking for your username and password. This is required on macOS to read information from the keychain.
<p align="center">
  <img src="https://thanosgn.github.io/assets/macos-prompt.png">
</p>
