import subprocess
import unittest
from unittest.mock import call, patch

import wifi_share


class ProcessExecutionTests(unittest.TestCase):
    def test_execute_sets_timeout_and_returns_stdout(self):
        completed = subprocess.CompletedProcess(
            args=["tool"],
            returncode=0,
            stdout="result\n",
            stderr="",
        )

        with patch.object(wifi_share.subprocess, "run", return_value=completed) as run:
            self.assertEqual(wifi_share.execute(["tool", "argument"]), "result\n")

        self.assertEqual(run.call_args.kwargs["timeout"], wifi_share.COMMAND_TIMEOUT_SECONDS)
        self.assertEqual(run.call_args.args[0], ["tool", "argument"])

    def test_execute_reports_missing_command(self):
        with patch.object(
            wifi_share.subprocess,
            "run",
            side_effect=FileNotFoundError,
        ):
            with self.assertRaisesRegex(
                wifi_share.ProcessError,
                "Required command not found: nmcli",
            ):
                wifi_share.execute(["nmcli", "connection", "show"])

    def test_execute_reports_timeout(self):
        timeout = subprocess.TimeoutExpired(cmd=["slow-tool"], timeout=30)

        with patch.object(wifi_share.subprocess, "run", side_effect=timeout):
            with self.assertRaisesRegex(
                wifi_share.ProcessError,
                "Command timed out after 30 seconds: slow-tool",
            ):
                wifi_share.execute(["slow-tool"])

    def test_execute_reports_other_os_errors(self):
        with patch.object(
            wifi_share.subprocess,
            "run",
            side_effect=PermissionError("denied"),
        ):
            with self.assertRaisesRegex(
                wifi_share.ProcessError,
                "Could not run protected-tool: denied",
            ):
                wifi_share.execute(["protected-tool"])


class QrPayloadTests(unittest.TestCase):
    def test_secured_network_payload_escapes_reserved_characters(self):
        payload = wifi_share.create_QR_string(
            ssid='Cafe: guest; "5G"',
            password=r'pass\word,one',
        )

        self.assertEqual(
            payload,
            r'WIFI:T:WPA;S:Cafe\: guest\; \"5G\";P:pass\\word\,one;;',
        )

    def test_open_network_payload_uses_nopass(self):
        self.assertEqual(
            wifi_share.create_QR_string(ssid="Public Wi-Fi"),
            "WIFI:T:nopass;S:Public Wi-Fi;;",
        )


class WindowsBackendTests(unittest.TestCase):
    def test_saved_networks_support_english_output(self):
        output = """\
Profiles on interface Wi-Fi:
    All User Profile     : Home Wi-Fi
    All User Profile     : Cafe:5G
"""

        with patch.object(wifi_share, "execute", return_value=output):
            self.assertEqual(
                wifi_share.windows_saved_networks(),
                ["Home Wi-Fi", "Cafe:5G"],
            )

    def test_saved_networks_support_italian_output(self):
        output = """\
Profili sull'interfaccia Wi-Fi:
    Tutti i profili utente     : Rete di casa
"""

        with patch.object(wifi_share, "execute", return_value=output):
            self.assertEqual(
                wifi_share.windows_saved_networks(),
                ["Rete di casa"],
            )

    def test_current_network_extracts_ssid(self):
        output = """\
    Name                   : Wi-Fi
    SSID                   : Home:5G
    BSSID                  : 00:11:22:33:44:55
"""

        with patch.object(wifi_share, "execute", return_value=output):
            self.assertEqual(wifi_share.windows_current_wifi_name(), "Home:5G")

    def test_password_supports_english_and_italian_output(self):
        samples = (
            ("    Key Content            : secret:one\n", "secret:one"),
            ("    Contenuto chiave       : segreta:due\n", "segreta:due"),
        )

        for output, expected in samples:
            with self.subTest(output=output):
                with patch.object(wifi_share, "execute", return_value=output):
                    self.assertEqual(
                        wifi_share.windows_password("Home Wi-Fi"),
                        expected,
                    )

    def test_missing_supported_label_raises_process_error(self):
        with patch.object(wifi_share, "execute", return_value="No profiles\n"):
            with self.assertRaises(wifi_share.ProcessError):
                wifi_share.windows_saved_networks()


class MacBackendTests(unittest.TestCase):
    def test_wifi_device_is_selected_from_hardware_ports(self):
        output = """\
Hardware Port: Ethernet
Device: en1
Ethernet Address: 00:11:22:33:44:55

Hardware Port: Wi-Fi
Device: en0
Ethernet Address: 66:77:88:99:aa:bb
"""

        with patch.object(wifi_share, "execute", return_value=output):
            self.assertEqual(wifi_share.mac_wifi_device(), "en0")

    def test_saved_networks_skip_command_heading(self):
        output = """\
Preferred networks on en0:
    Home Wi-Fi
    Cafe:5G
"""

        with (
            patch.object(wifi_share, "mac_wifi_device", return_value="en0"),
            patch.object(wifi_share, "execute", return_value=output),
        ):
            self.assertEqual(
                wifi_share.mac_saved_networks(),
                ["Home Wi-Fi", "Cafe:5G"],
            )

    def test_current_network_uses_next_resolver_after_failure(self):
        with (
            patch.object(wifi_share, "mac_wifi_device", return_value="en0"),
            patch.object(
                wifi_share,
                "mac_current_wifi_name_corewlan",
                side_effect=wifi_share.ProcessError("redacted"),
            ) as corewlan,
            patch.object(
                wifi_share,
                "mac_current_wifi_name_networksetup",
                return_value="Home Wi-Fi",
            ) as networksetup,
            patch.object(wifi_share, "mac_current_wifi_name_ipconfig") as ipconfig,
            patch.object(wifi_share, "mac_current_wifi_name_system_profiler") as profiler,
        ):
            self.assertEqual(wifi_share.mac_current_wifi_name(), "Home Wi-Fi")

        corewlan.assert_called_once_with()
        networksetup.assert_called_once_with("en0")
        ipconfig.assert_not_called()
        profiler.assert_not_called()

    def test_keychain_password_command_preserves_spaces(self):
        with patch.object(wifi_share, "execute", return_value="secret\n") as execute:
            self.assertEqual(wifi_share.mac_password("Home Wi-Fi"), "secret")

        execute.assert_called_once_with(
            [
                "security",
                "find-generic-password",
                "-D",
                "AirPort network password",
                "-a",
                "Home Wi-Fi",
                "-w",
            ]
        )


class LinuxBackendTests(unittest.TestCase):
    def test_connections_filter_wifi_and_unescape_names(self):
        output = """\
Home\\: primary:802-11-wireless
Wired connection:802-3-ethernet
Office\\\\guest:802-11-wireless
"""

        with patch.object(wifi_share, "execute", return_value=output):
            self.assertEqual(
                wifi_share.linux_wifi_connections(),
                ["Home: primary", r"Office\guest"],
            )

    def test_current_network_extracts_active_ssid(self):
        output = """\
no:Neighbour
yes:Home\\:5G
"""

        with patch.object(wifi_share, "execute", return_value=output):
            self.assertEqual(wifi_share.linux_current_wifi_name(), "Home:5G")

    def test_active_connection_is_read_directly_from_network_manager(self):
        output = "home-profile:802-11-wireless\n"

        with patch.object(wifi_share, "execute", return_value=output) as execute:
            self.assertEqual(
                wifi_share.linux_active_wifi_connection(),
                "home-profile",
            )

        execute.assert_called_once_with(
            [
                "nmcli",
                "-t",
                "-f",
                "NAME,TYPE",
                "connection",
                "show",
                "--active",
            ]
        )

    def test_multiple_active_wifi_connections_are_rejected(self):
        output = "first:802-11-wireless\nsecond:802-11-wireless\n"

        with patch.object(wifi_share, "execute", return_value=output):
            with self.assertRaisesRegex(
                wifi_share.ProcessError,
                "Multiple active Wi-Fi connections found",
            ):
                wifi_share.linux_active_wifi_connection()

    def test_saved_networks_keep_connection_mapping(self):
        with (
            patch.object(
                wifi_share,
                "linux_wifi_connections",
                return_value=["home-profile", "office-profile"],
            ),
            patch.object(
                wifi_share,
                "linux_wifi_name_for_connection",
                side_effect=["Home", "Office"],
            ) as wifi_name,
        ):
            self.assertEqual(
                wifi_share.linux_saved_networks(),
                (["Home", "Office"], ["home-profile", "office-profile"]),
            )

        self.assertEqual(
            wifi_name.call_args_list,
            [call("home-profile"), call("office-profile")],
        )

    def test_password_uses_show_secrets_for_connection_id(self):
        output = r"802-11-wireless-security.psk:secret\:with\\slashes" + "\n"

        with patch.object(wifi_share, "execute", return_value=output) as execute:
            self.assertEqual(
                wifi_share.linux_password("home-profile"),
                r"secret:with\slashes",
            )

        execute.assert_called_once_with(
            [
                "nmcli",
                "-t",
                "-f",
                "802-11-wireless-security.psk",
                "--show-secrets",
                "connection",
                "show",
                "id",
                "home-profile",
            ]
        )

    def test_current_wifi_uses_active_connection_without_ssid_search(self):
        with (
            patch.object(
                wifi_share,
                "linux_active_wifi_connection",
                return_value="active-profile",
            ),
            patch.object(
                wifi_share,
                "linux_wifi_name_for_connection",
                return_value="Home",
            ),
            patch.object(wifi_share, "linux_wifi_connections") as connections,
        ):
            self.assertEqual(
                wifi_share.get_current_wifi_name("Linux"),
                ("Home", "active-profile"),
            )

        connections.assert_not_called()

    def test_password_rejects_ambiguous_profiles_for_same_ssid(self):
        with (
            patch.object(
                wifi_share,
                "linux_wifi_connections",
                return_value=["first-profile", "second-profile"],
            ),
            patch.object(
                wifi_share,
                "linux_wifi_name_for_connection",
                side_effect=["Home", "Home"],
            ),
        ):
            with self.assertRaisesRegex(
                wifi_share.ProcessError,
                "Multiple saved Wi-Fi profiles match SSID: Home",
            ):
                wifi_share.get_password("Linux", "Home")

    def test_saved_network_picker_distinguishes_duplicate_ssids(self):
        with (
            patch.object(
                wifi_share,
                "get_saved_networks",
                return_value=(
                    ["Home", "Home"],
                    ["home-2g-profile", "home-5g-profile"],
                ),
            ),
            patch.object(
                wifi_share.questionary,
                "prompt",
                return_value={"network": 1},
            ) as prompt,
        ):
            self.assertEqual(
                wifi_share.choose_saved_wifi("Linux"),
                ("Home", "home-5g-profile"),
            )

        choices = prompt.call_args.args[0][0]["choices"]
        self.assertEqual(
            choices,
            [
                {"name": "Home (home-2g-profile)", "value": 0},
                {"name": "Home (home-5g-profile)", "value": 1},
            ],
        )


class BackendDispatchTests(unittest.TestCase):
    def test_saved_network_dispatches_to_each_supported_backend(self):
        with (
            patch.object(wifi_share, "windows_saved_networks", return_value=["Windows"]),
            patch.object(wifi_share, "mac_saved_networks", return_value=["macOS"]),
            patch.object(
                wifi_share,
                "linux_saved_networks",
                return_value=(["Linux"], ["linux-profile"]),
            ),
        ):
            self.assertEqual(
                wifi_share.get_saved_networks("Windows"),
                (["Windows"], []),
            )
            self.assertEqual(
                wifi_share.get_saved_networks("Darwin"),
                (["macOS"], []),
            )
            self.assertEqual(
                wifi_share.get_saved_networks("Linux"),
                (["Linux"], ["linux-profile"]),
            )

    def test_unknown_system_is_not_treated_as_linux(self):
        operations = (
            lambda: wifi_share.get_saved_networks("FreeBSD"),
            lambda: wifi_share.get_current_wifi_name("FreeBSD"),
            lambda: wifi_share.get_password("FreeBSD", "Home"),
        )

        for operation in operations:
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(
                    wifi_share.ProcessError,
                    "Unsupported operating system: FreeBSD",
                ):
                    operation()


if __name__ == "__main__":
    unittest.main()
