import unittest
from unittest.mock import call, patch

import wifi_share


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
        output = "802-11-wireless-security.psk:secret\n"

        with patch.object(wifi_share, "execute", return_value=output) as execute:
            self.assertEqual(wifi_share.linux_password("home-profile"), "secret")

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


if __name__ == "__main__":
    unittest.main()
