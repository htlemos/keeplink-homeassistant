# Keeplink Network Switch for Home Assistant

Custom component to integrate Keeplink / Horaco / Sodola 2.5G Web Managed Switches into Home Assistant.

## Supported Devices
* KP-9000-9XHPML-X-AC
* (Likely works with other Realtek-based Web Managed switches)

## ✨ Features

This integration transforms your web-managed switch into a fully controllable smart device in Home Assistant:

* **System Information:** Live sensors for Model, Firmware, Hardware Version, MAC, IP, Netmask, Gateway, and Firmware Date.
* **Port Link Status:** Binary sensors for every port showing Connected (Up) or Disconnected (Down).
* **Port Configuration:** * Toggle Admin State (Enable/Disable port).
  * Toggle Flow Control.
  * Dropdown Select to force Speed/Duplex (Auto, 10M, 100M, 1G, 2.5G, 10G for SFP+).
* **Power over Ethernet (PoE) Management:**
  * Toggle PoE Power per port.
  * Live sensors for Total PoE Power Consumption (W).
  * Individual sensors per port for Power (W), Voltage (V), and Current (mA) (Disabled by default to keep your entity list clean).
* **Port Statistics:** * Tx/Rx Packets and Tx/Rx Errors are tracked as attributes on each port's Link sensor.
  * A **Clear Statistics** button entity to reset all counters directly from Home Assistant.
* **Dynamic Polling:** Configurable Scan Interval via the integration options (Cogwheel).

## Installation via HACS
1. Go to HACS -> Integrations.
2. Click the 3 dots in the top right corner -> **Custom repositories**.
3. Paste the URL of this repository.
4. Select category **Integration**.
5. Click **Add**, then search for "Keeplink Switch" and install.
6. Restart Home Assistant.

## Configuration
1. Go to **Settings** -> **Devices & Services**.
2. Click **Add Integration**.
3. Search for **Keeplink**.
4. Enter your Switch IP (e.g., `192.168.1.168`).
5. Enter Username/Password (Default is `admin`/`admin`).
6. *Optional:* Click the **Configure** (Cogwheel) icon on the integration later to change your credentials or adjust the polling Scan Interval.

---

## 🎨 Custom Dashboard layout

You can create a beautiful, dynamic "Physical Switch" visualizer on your dashboard that shows Link States (Green/Red/Gray), live PoE Wattage, and hovering statistics.

**Prerequisites:**
You must install the **[Button Card](https://github.com/custom-cards/button-card)** by RomRider via HACS frontend before using this code.

**Instructions:**
1. Edit your Home Assistant Dashboard.
2. Click **Add Card** -> **Manual**.
3. Paste the following YAML code. 
*(Note: If your entity names end in `_2` or differ, update them in the YAML to match your system).*

```yaml
type: vertical-stack
cards:
  # --- 1. TITLE BAR ---
  - type: custom:button-card
    name: KEEPLINK 2.5G MANAGED SWITCH
    color_type: label-card
    styles:
      card:
        - background-color: '#2c3e50'
        - border-radius: 8px 8px 0 0
        - padding: 10px
      name:
        - color: '#ecf0f1'
        - font-weight: bold
        - letter-spacing: 2px

  # --- 2. PORT VISUALIZER ---
  - type: grid
    columns: 5
    square: false
    cards:
      # --- PORT 1 (Master Anchor Definitions) ---
      - type: custom:button-card
        entity: binary_sensor.keeplink_port_1_link
        name: P1
        icon: mdi:ethernet
        tooltip: &port_tooltip >
          [[[
            if (!entity || !entity.attributes) return 'No data';
            let a = entity.attributes;
            let text = `Speed: ${a.speed || 'Unknown'}\nFlow: ${a.flow_control || 'Unknown'}\n`;
            text += `Tx Pkts: ${a.tx_packets || 0} | Rx Pkts: ${a.rx_packets || 0}\n`;
            text += `Tx Err: ${a.tx_errors || 0} | Rx Err: ${a.rx_errors || 0}`;
            if (a.poe_power_w !== undefined) {
               text += `\nPoE: ${a.poe_power_w}W (${a.poe_current_ma}mA / ${a.poe_voltage_v}V)`;
            }
            return text;
          ]]]
        styles: &port_style
          card:
            - height: 85px
            - box-shadow: inset 0 0 15px rgba(0,0,0,0.6)
            - border: 2px solid #222
            - border-radius: 6px
            - background-color: >
                [[[
                  var port = entity.entity_id.split('_')[3];
                  var admin = states['switch.keeplink_port_' + port + '_state'];
                  if (admin && admin.state === 'off') return '#555555'; 
                  if (entity && entity.state === 'on') return '#27ae60'; 
                  return '#c0392b';
                ]]]
          icon:
            - color: white
            - width: 28px
          name:
            - color: white
            - font-size: 13px
            - font-weight: bold
            - padding-top: 5px
          custom_fields:
            poe:
              - font-size: 12px
              - font-weight: bold
              - color: '#f1c40f'
        custom_fields: &poe_field
          poe: >
            [[[
              var port = entity.entity_id.split('_')[3];
              var poe = states['sensor.keeplink_port_' + port + '_poe_power'];
              if (poe && poe.state && !isNaN(poe.state) && parseFloat(poe.state) > 0) {
                return parseFloat(poe.state).toFixed(1) + 'W';
              }
              return '&nbsp;';
            ]]]

      # --- PORTS 2 to 8 (Using Anchors) ---
      - type
