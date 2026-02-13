# Keeplink Network Switch for Home Assistant

Custom component to integrate Keeplink / Horaco / Sodola 2.5G Web Managed Switches into Home Assistant.

## Supported Devices
* KP-9000-9XHPML-X-AC
* (Likely works with other Realtek-based Web Managed switches)

## Installation via HACS
1. Go to HACS -> Integrations.
2. Click the 3 dots in the top right corner -> **Custom repositories**.
3. Paste the URL of this repository.
4. Select category **Integration**.
5. Click **Add**, then search for "Keeplink Switch" and install.

## Configuration
1. Go to Settings -> Devices & Services.
2. Click **Add Integration**.
3. Search for **Keeplink**.
4. Enter your Switch IP (e.g., `192.168.1.168`).
5. Enter Username/Password (Default is `admin`/`admin`).
