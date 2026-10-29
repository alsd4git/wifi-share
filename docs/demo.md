# Reproduce the Wi-Fi Share preview

From a source checkout:

```sh
uv sync --locked --dev
uv run python scripts/render_demo.py
```

The script invokes the actual image-export CLI with an explicit fictitious SSID
and password. It captures the command's output and embeds its generated QR SVG in
`docs/demo.svg`. It uses a temporary working directory, blocks system command
execution and saved-password/network lookup helpers, and never contacts a real
network. The Linux ownership adjustment is bypassed for this temporary demo.

The QR encodes `Demo Guest` / `example-only-123`. It does not provide access to
any real network. No real Wi-Fi credential or personal device output belongs in
this directory.

This preview demonstrates image export only. It does not validate saved-profile
discovery, Keychain access or Wi-Fi hardware on any operating system.

The project logo remains the original upstream artwork under `logos/`.

The README uses absolute GitHub URLs so its images and documentation links also
work when rendered as package metadata. The demo image and reproduction guide
are pinned to their committed revision. After regenerating and committing an
updated preview, update those README URLs to the new revision.
