#!/usr/bin/env python3
from __future__ import print_function

import argparse
import locale
import os
import platform
import re
import subprocess
import sys
from collections import OrderedDict

import qrcode
import qrcode.image.svg
import questionary
from huepy import *

verbose = True

ascii_art = r'''
 __          ___        ______ _      _____ _
 \ \        / (_)      |  ____(_)    / ____| |
  \ \  /\  / / _ ______| |__   _    | (___ | |__   __ _ _ __ ___
   \ \/  \/ / | |______|  __| | |    \___ \| '_ \ / _` | '__/ _ \\
    \  /\  /  | |      | |    | |    ____) | | | | (_| | | |  __/
     \/  \/   |_|      |_|    |_|   |_____/|_| |_|\__,_|_|  \___|
'''

WINDOWS_PROFILE_LABELS = ("All User Profile", "Tutti i profili utente")
WINDOWS_PASSWORD_LABELS = ("Key Content", "Contenuto chiave")
MAC_WIFI_PORTS = {"Wi-Fi", "AirPort"}
LINUX_WIFI_TYPE = "802-11-wireless"


def log(message):
    if verbose:
        print(message, file=sys.stderr)


class ProcessError(Exception):
    def __init__(self, message=''):
        self.message = message

    def __str__(self):
        return self.message


# Execute a command and return its stdout.
def execute(command):
    log(run(bold('Running: ') + ' '.join(command)))
    completed = subprocess.run(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding=locale.getpreferredencoding(False),
        errors='replace',
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip()
        raise ProcessError(message)
    return completed.stdout


def escape(input_string):
    translations = OrderedDict([('\\', '\\\\'),
                                (':', '\\:'),
                                (';', '\\;'),
                                (',', '\\,'),
                                ('"', '\\"')])
    escaped = input_string
    for k, v in translations.items():
        escaped = escaped.replace(k, v)
    return escaped


def nmcli_unescape(value):
    return re.sub(r'\\(.)', r'\1', value)


def fix_ownership(path):  # Change the owner of the file to SUDO_UID
    uid = os.environ.get('SUDO_UID')
    gid = os.environ.get('SUDO_GID')
    if uid is not None and gid is not None:
        os.chown(path, int(uid), int(gid))


def create_QR_string(ssid=None, security='WPA', password=None):
    if ssid is not None:
        if password is not None:
            return 'WIFI:T:' + security + ';S:' + escape(ssid) + ';P:' + escape(password) + ';;'
        return 'WIFI:T:nopass;S:' + escape(ssid) + ';;'
    return ''


def create_QR_object(data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    return qr


def windows_saved_networks():
    output = execute(['netsh', 'wlan', 'show', 'profiles'])
    available_networks = []
    labels = '|'.join(re.escape(label) for label in WINDOWS_PROFILE_LABELS)
    pattern = re.compile(r'^\s*(?:' + labels + r')\s*:\s*(.+?)\s*$')
    for line in output.splitlines():
        match = pattern.match(line)
        if match:
            available_networks.append(match.group(1))
    if not available_networks:
        raise ProcessError
    return available_networks


def windows_current_wifi_name():
    output = execute(['netsh', 'wlan', 'show', 'interfaces'])
    pattern = re.compile(r'^\s*SSID\s*:\s*(.+?)\s*$')
    for line in output.splitlines():
        match = pattern.match(line)
        if match:
            return match.group(1)
    raise ProcessError


def windows_password(wifi_name):
    output = execute(['netsh', 'wlan', 'show', 'profile', wifi_name, 'key=clear'])
    labels = '|'.join(re.escape(label) for label in WINDOWS_PASSWORD_LABELS)
    pattern = re.compile(r'^\s*(?:' + labels + r')\s*:\s*(.+?)\s*$')
    for line in output.splitlines():
        match = pattern.match(line)
        if match:
            return match.group(1)
    raise ProcessError


def mac_wifi_device():
    output = execute(['networksetup', '-listallhardwareports'])
    port = None
    device = None
    for line in output.splitlines():
        if line.startswith('Hardware Port:'):
            port = line.split(':', 1)[1].strip()
        elif line.startswith('Device:') and port in MAC_WIFI_PORTS:
            device = line.split(':', 1)[1].strip()
            break
    if device is None:
        raise ProcessError
    return device


def mac_current_wifi_name_corewlan():
    output = execute([
        'swift',
        '-e',
        'import CoreWLAN; '
        'let client = CWWiFiClient.sharedWiFiClient(); '
        'if let iface = client.interface(), let ssid = iface.ssid() { print(ssid) }',
    ]).strip()
    if output and output not in {'Wi-Fi', 'WLAN', '<redacted>'}:
        return output
    raise ProcessError


def mac_current_wifi_name_networksetup(device):
    output = execute(['networksetup', '-getairportnetwork', device]).strip()
    pattern = re.compile(r'^(?:Current Wi-Fi Network|Current AirPort Network):\s*(.+?)\s*$')
    for line in output.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        wifi_name = match.group(1).strip()
        if wifi_name and wifi_name not in {'Wi-Fi', 'WLAN', '<redacted>'}:
            return wifi_name
    raise ProcessError


def mac_current_wifi_name_ipconfig(device):
    output = execute(['ipconfig', 'getsummary', device])
    pattern = re.compile(r'^\s*SSID\s*:\s*(.+?)\s*$')
    for line in output.splitlines():
        match = pattern.match(line)
        if not match:
            continue
        wifi_name = match.group(1).strip()
        if wifi_name and wifi_name not in {'Wi-Fi', 'WLAN', '<redacted>'}:
            return wifi_name
    raise ProcessError


def mac_current_wifi_name_system_profiler():
    output = execute(['system_profiler', 'SPAirPortDataType'])
    in_current_block = False
    for line in output.splitlines():
        stripped = line.strip()
        if stripped == 'Current Network Information:':
            in_current_block = True
            continue
        if not in_current_block:
            continue
        if stripped == '' or not line.startswith('            '):
            break
        if not stripped.endswith(':'):
            continue
        wifi_name = stripped[:-1].strip()
        if wifi_name and wifi_name not in {'Wi-Fi', 'WLAN', '<redacted>'}:
            return wifi_name
    raise ProcessError


def mac_saved_networks():
    device = mac_wifi_device()
    output = execute(['networksetup', '-listpreferredwirelessnetworks', device])
    available_networks = []
    for line in output.splitlines()[1:]:
        network = line.strip()
        if network:
            available_networks.append(network)
    if not available_networks:
        raise ProcessError
    return available_networks


def mac_current_wifi_name():
    device = mac_wifi_device()
    for resolver in (
        mac_current_wifi_name_corewlan,
        lambda: mac_current_wifi_name_networksetup(device),
        lambda: mac_current_wifi_name_ipconfig(device),
        mac_current_wifi_name_system_profiler,
    ):
        try:
            return resolver()
        except ProcessError:
            continue
    raise ProcessError


def mac_password(wifi_name):
    return execute([
        'security',
        'find-generic-password',
        '-D', 'AirPort network password',
        '-a', wifi_name,
        '-w',
    ]).rstrip('\r\n')


def linux_wifi_connections():
    output = execute(['nmcli', '-t', '-f', 'NAME,TYPE', 'connection', 'show'])
    connections = []
    for line in output.splitlines():
        if not line:
            continue
        connection_name, connection_type = line.split(':', 1)
        if connection_type == LINUX_WIFI_TYPE:
            connections.append(nmcli_unescape(connection_name))
    if not connections:
        raise ProcessError
    return connections


def linux_wifi_name_for_connection(connection_name):
    output = execute(['nmcli', '-t', '-f', '802-11-wireless.ssid', 'connection', 'show', connection_name])
    for line in output.splitlines():
        if line.startswith('802-11-wireless.ssid:'):
            ssid = nmcli_unescape(line.split(':', 1)[1])
            if ssid:
                return ssid
    raise ProcessError


def linux_saved_networks():
    connections = linux_wifi_connections()
    available_networks = [linux_wifi_name_for_connection(connection) for connection in connections]
    return available_networks, connections


def linux_current_wifi_name():
    output = execute(['nmcli', '-t', '-f', 'ACTIVE,SSID', 'device', 'wifi'])
    for line in output.splitlines():
        if not line:
            continue
        active, ssid = line.split(':', 1)
        if active == 'yes':
            wifi_name = nmcli_unescape(ssid)
            if wifi_name:
                return wifi_name
    raise ProcessError


def linux_password(connection_name):
    output = execute([
        'nmcli',
        '-t',
        '-f', '802-11-wireless-security.psk',
        '--show-secrets',
        'connection',
        'show',
        'id',
        connection_name,
    ])
    for line in output.splitlines():
        if line.startswith('802-11-wireless-security.psk:'):
            return line.split(':', 1)[1]
    return ''


def get_saved_networks(system):
    if system == 'Windows':
        return windows_saved_networks(), []
    if system == 'Darwin':
        return mac_saved_networks(), []
    return linux_saved_networks()


def choose_saved_wifi(system):
    available_networks, connections = get_saved_networks(system)
    choices = [{"name": network, "value": network} for network in available_networks]
    questions = [
        {
            'type': 'list',
            'name': 'network',
            'message': 'SSID:',
            'choices': choices,
        }
    ]
    answer = questionary.prompt(questions)
    if not answer:
        raise KeyboardInterrupt
    wifi_name = answer['network']
    connection_name = ''
    if system == 'Linux':
        connection_name = connections[available_networks.index(wifi_name)]
    return wifi_name, connection_name


def get_current_wifi_name(system):
    if system == 'Windows':
        return windows_current_wifi_name(), ''
    if system == 'Darwin':
        return mac_current_wifi_name(), ''
    wifi_name = linux_current_wifi_name()
    connections = linux_wifi_connections()
    connection_name = ''
    for connection in connections:
        if linux_wifi_name_for_connection(connection) == wifi_name:
            connection_name = connection
            break
    if connection_name == '':
        raise ProcessError
    return wifi_name, connection_name


def get_password(system, wifi_name, connection_name=''):
    if system == 'Windows':
        return windows_password(wifi_name)
    if system == 'Darwin':
        return mac_password(wifi_name)
    if connection_name == '':
        connections = linux_wifi_connections()
        for connection in connections:
            if linux_wifi_name_for_connection(connection) == wifi_name:
                connection_name = connection
                break
    if connection_name == '':
        raise ProcessError
    return linux_password(connection_name)


def main():
    global verbose
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, description=ascii_art)
    parser.add_argument('-v', '--verbose', help='Enable verbose output.', action='store_true')
    parser.add_argument(
        '-i',
        '--image',
        help='Specify a filename for the generated QR code image. (.png or .svg).\
                                                  Default: [WIFINAME].svg.\
                                                  If -i/--image argument is not provided the QR code will be displayed\
                                                  on the console.',
        nargs='?',
        default='no-image',
    )
    parser.add_argument(
        '-s',
        '--ssid',
        help='Specify the SSID you want the password of.\
                                                Default: the SSID of the network you are currently connected.',
    )
    parser.add_argument('-p', '--password', help='Specify a desired password to be used instead of the stored one.')
    parser.add_argument('-l', '--list', help='Display a list of stored Wi-Fi networks (SSIDs) to choose from.', action='store_true')
    args = parser.parse_args()

    if args.list and args.ssid:
        print(bad('The -s/--ssid SSID and -l/--list are mutually exclusive arguments.'))
        sys.exit(1)

    verbose = args.verbose
    wifi_name = args.ssid
    connection_name = ''
    current_wifi_known = False

    system = platform.system()

    if args.list:
        try:
            wifi_name, connection_name = choose_saved_wifi(system)
        except ProcessError as e:
            log(bad(e))
            print(bad('Error getting Wi-Fi connections'))
            sys.exit(1)
        log(run('Retrieving the password for ' + green(wifi_name) + ' Wi-Fi'))
    elif args.ssid is None:
        try:
            wifi_name, connection_name = get_current_wifi_name(system)
            current_wifi_known = True
        except ProcessError as e:
            if system == 'Darwin':
                log(info('Could not determine the current Wi-Fi name; showing saved networks instead.'))
                try:
                    wifi_name, connection_name = choose_saved_wifi(system)
                except ProcessError as inner_error:
                    log(bad(inner_error))
                    print(bad('Error getting Wi-Fi connections'))
                    sys.exit(1)
                except KeyboardInterrupt:
                    log('\nk bye')
                    sys.exit(1)
                log(run('Retrieving the password for ' + green(wifi_name) + ' Wi-Fi'))
            else:
                log(bad(e))
                print(bad('Error getting Wi-Fi name'))
                print(que('Are you sure you are connected to a Wi-Fi network?'))
                sys.exit(1)
        if current_wifi_known:
            log(good('You are connected to ' + green(wifi_name) + ' Wi-Fi'))
    else:
        log(run('Retrieving the password for ' + green(wifi_name) + ' Wi-Fi'))

    if args.password is not None:
        wifi_password = args.password
    else:
        try:
            wifi_password = get_password(system, wifi_name, connection_name)
        except (ProcessError, IOError) as e:
            log(bad(e))
            print(bad('Error getting Wi-Fi password'))
            if e.__class__ == IOError:
                if e.errno == 13:
                    print(que('Are you root?'))
                elif e.errno == 2 and args.ssid is not None:
                    print(que('Are you sure SSID is correct?'))
            sys.exit(1)

    if wifi_password != '':
        log(good('The password is ' + green(wifi_password)))
        data = create_QR_string(ssid=wifi_name, password=wifi_password)
    else:
        log(info('No password needed for this network.'))
        data = create_QR_string(ssid=wifi_name, security='nopass')

    qr = create_QR_object(data)

    if args.image == 'no-image':  # If user did not enter the -i/--image argument
        qr.print_tty()
    else:
        img = qrcode.make(data)
        if args.image is None:  # If user selected the -i/--image argument, but did not give any filename
            img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathFillImage)
            filename = wifi_name + '.svg'
        else:  # If user specified a filename with the -i/--image argument
            if args.image.endswith('.svg'):
                img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathFillImage)
                filename = args.image
            elif args.image.endswith('.png'):
                filename = args.image
                img = qr.make_image(fill_color="black", back_color="white")
            else:
                img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathFillImage)
                filename = args.image + '.svg'
        img.save(filename)
        if system == 'Linux':
            fix_ownership(filename)
        print(good('Qr code drawn in ' + filename))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log('\nk bye')
        sys.exit(1)
