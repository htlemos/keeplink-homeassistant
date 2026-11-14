# Keeplink Network Switch for Home Assistant

Custom component to integrate Keeplink / Horaco / Sodola 2.5G Web Managed Switches into Home Assistant.

*Co-piloted by Gemini AI 🤖*

## Supported Devices
* KP-9000-9XHPML-X-AC
* (Likely works with other Realtek-based Web Managed switches)

## ✨ Features

This integration transforms your web-managed switch into a fully controllable smart device in Home Assistant:

* **System Information:** Live sensors for Model, Firmware, Hardware Version, MAC, IP, Netmask, Gateway, and Firmware Date.
* **Physical Port Link Status:** Real-time binary sensors (`panel.cgi`) for every physical port (RJ45 Ports 1–8 and 10G SFP+ Port 9) showing Connected (Up) or Disconnected (Down)—even when ports are aggregated inside a Trunk Group.
* **Link Aggregation (Trunk / LACP) Support:**
  * Automatic detection and monitoring of **Trunk 1** and **Trunk 2** groups (`static` and `LACP`).
  * Dedicated `Keeplink Trunk 1 Link` and `Keeplink Trunk 2 Link` binary sensors with aggregated speed, flow control, and 64-bit Tx/Rx packet and error counters.
  * Read-only sensors in the main Sensors section for **Type** (`LACP`, `static`, `Inactive`), **Member Ports**, and **Aggregated Ports**.
  * Full Admin State, Flow Control, and Speed/Duplex controls for active Trunk interfaces.
* **Port Configuration:**
  * Toggle Admin State (Enable/Disable port or trunk).
  * Toggle Flow Control.
  * Dropdown Select to force Speed/Duplex (Auto, 10M, 100M, 1G, 2.5G, 10G for SFP+).
  * *Smart Availability:* Standalone L2 controls for physical ports assigned to an active Trunk Group automatically transition to `Unavailable` so L2 settings are safely governed by the parent Trunk.
* **Power over Ethernet (PoE) Management:**
  * Toggle PoE Power per physical port (remains 100% active even when the port is part of a Trunk Group).
  * Live sensor for Total PoE Power Consumption (W).
  * Individual sensors per port for Power (W), Voltage (V), and Current (mA) (Disabled by default to keep your entity list clean, and always exposed as attributes on each port's Link sensor).
* **Switch Actions & Statistics:**
  * Tx/Rx Packets and Tx/Rx Errors are tracked as attributes on each port and trunk Link sensor.
  * A **Clear Statistics** button entity to reset all traffic counters.
  * A **Reboot Device** button to safely restart the switch hardware directly from Home Assistant.
* **Dual-Polling & Cold-Boot Recovery Engine:**
  * Separate scan intervals for general switch data and rapid PoE power monitoring.
  * Built-in MD5 auto-login recovery that automatically unlocks the Realtek web server after power outages and waits for both the main CPU and PoE controller to initialize before loading entities.
* **Energy Dashboard Ready (Left Riemann Sum):** Automatically calculates accumulated energy (kWh) from PoE wattage, fully compatible with Home Assistant's Long-Term Statistics (LTS) and Energy Dashboard.
* **Built-in Utility Meters:** Optionally generate daily, monthly, and yearly cyclical energy sensors for both Total Switch PoE and Per-Port PoE consumption directly from the integration's options.
* **Clean Device UI:** Entities are smartly sorted into standard **Sensors**, **Controls**, **Configuration**, and **Diagnostic** sections to keep your device page organized.

## Installation via HACS
1. Go to HACS -> Integrations.
2. Click the 3 dots in the top right corner -> **Custom repositories**.
3. Paste the URL of this repository (`https://github.com/htlemos/keeplink-homeassistant`).
4. Select category **Integration**.
5. Click **Add**, then search for **Keeplink Switch** and install.
6. Restart Home Assistant.

## Configuration
1. Go to **Settings** -> **Devices & Services**.
2. Click **Add Integration**.
3. Search for **Keeplink**.
4. Enter your Switch IP (e.g., `192.168.1.168`).
5. Enter Username/Password (Default is `admin`/`admin`).
6. *Optional:* Click the **Configure** (Cogwheel) icon on the integration at any time to adjust polling intervals or enable Total/Per-Port Energy and Utility Meter sensors.

> **🎨 Note on Integration Branding:**
> Custom icons and logos for this integration automatically display in your UI on **Home Assistant 2026.3.0** or newer, utilizing the local Brands Proxy API!

---

## 🎨 Custom Dashboard Layouts

You can create a dynamic "Physical Switch" visualizer on your dashboard that displays Link States (Green/Red/Gray), live PoE Wattage, Trunk Group memberships, and hover statistics.

**Prerequisites:**
Install the **[Button Card](https://github.com/custom-cards/button-card)** by RomRider via HACS Frontend before using either layout below.

**Instructions:**
1. Edit your Home Assistant Dashboard.
2. Click **Add Card** -> **Manual**.
3. Paste one of the YAML layouts below:
   * **Option 1:** Standard setup (Standalone Ports, no Trunks).
   * **Option 2:** Advanced setup with **Trunk Groups (LACP / Static)** and member port badges.
*(Note: If your entity names end in `_2` or differ, update them in the YAML to match your system).*

---

### Option 1: Standard Layout (Non-Trunk Setup)

<details>
<summary><b>👉 Click to expand Option 1 YAML (Standalone Ports)</b></summary>

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
              if (entity && entity.attributes && entity.attributes.poe_power_w > 0) {
                return parseFloat(entity.attributes.poe_power_w).toFixed(1) + 'W';
              }
              var port = entity.entity_id.split('_')[3];
              var poe = states['sensor.keeplink_port_' + port + '_poe_power'];
              if (poe && poe.state && !isNaN(poe.state) && parseFloat(poe.state) > 0) {
                return parseFloat(poe.state).toFixed(1) + 'W';
              }
              return '&nbsp;';
            ]]]

      # --- PORTS 2 to 8 (Using Anchors) ---
      - type: custom:button-card
        entity: binary_sensor.keeplink_port_2_link
        name: P2
        icon: mdi:ethernet
        tooltip: *port_tooltip
        styles: *port_style
        custom_fields: *poe_field

      - type: custom:button-card
        entity: binary_sensor.keeplink_port_3_link
        name: P3
        icon: mdi:ethernet
        tooltip: *port_tooltip
        styles: *port_style
        custom_fields: *poe_field

      - type: custom:button-card
        entity: binary_sensor.keeplink_port_4_link
        name: P4
        icon: mdi:ethernet
        tooltip: *port_tooltip
        styles: *port_style
        custom_fields: *poe_field

      - type: custom:button-card
        entity: binary_sensor.keeplink_port_5_link
        name: P5
        icon: mdi:ethernet
        tooltip: *port_tooltip
        styles: *port_style
        custom_fields: *poe_field

      - type: custom:button-card
        entity: binary_sensor.keeplink_port_6_link
        name: P6
        icon: mdi:ethernet
        tooltip: *port_tooltip
        styles: *port_style
        custom_fields: *poe_field

      - type: custom:button-card
        entity: binary_sensor.keeplink_port_7_link
        name: P7
        icon: mdi:ethernet
        tooltip: *port_tooltip
        styles: *port_style
        custom_fields: *poe_field

      - type: custom:button-card
        entity: binary_sensor.keeplink_port_8_link
        name: P8
        icon: mdi:ethernet
        tooltip: *port_tooltip
        styles: *port_style
        custom_fields: *poe_field

      # --- PORT 9 (SFP+) ---
      - type: custom:button-card
        entity: binary_sensor.keeplink_port_9_link
        name: SFP+
        icon: mdi:expansion-card
        tooltip: *port_tooltip
        styles: *port_style
        custom_fields: *poe_field

  # --- 3. STATS & CONTROLS ---
  - type: horizontal-stack
    cards:
      - type: gauge
        entity: sensor.keeplink_poe_total_power
        name: Total PoE Load
        min: 0
        max: 120
        needle: true
        severity:
          green: 0
          yellow: 60
          red: 100
      - type: button
        entity: button.keeplink_clear_statistics
        name: Clear Port Stats
        icon: mdi:delete-sweep
        show_name: true
        show_state: false
```

</details>

---

### Option 2: Advanced Layout with Trunk Groups (LACP / Static)

This layout enhances the physical port grid with automatic **Trunk Badges (`T1` / `T2`)** on aggregated ports and adds a dedicated **Link Aggregation (LAG) Status Bar** displaying Trunk 1 and Trunk 2 health, LACP/Static mode, member/aggregated ports, and combined packet counters on hover.

<details>
<summary><b>👉 Click to expand Option 2 YAML (Trunk / LACP Aware)</b></summary>

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

  # --- 2. PHYSICAL PORT VISUALIZER (Trunk-Aware) ---
  - type: grid
    columns: 5
    square: false
    cards:
      # --- PORT 1 (Master Anchor Definitions) ---
      - type: custom:button-card
        entity: binary_sensor.keeplink_port_1_link
        name: P1
        icon: mdi:ethernet
        tooltip: &trunk_port_tooltip >
          [[[
            if (!entity || !entity.attributes) return 'No data';
            let a = entity.attributes;
            let text = '';
            if (a.trunk_group && a.trunk_group !== 'None') {
              text += `Member of: ${a.trunk_group}\n`;
              text += `Speed: ${a.speed || 'Unknown'}\nFlow: ${a.flow_control || 'Unknown'}\n`;
              text += `(Traffic counters tracked on ${a.trunk_group})`;
            } else {
              text += `Speed: ${a.speed || 'Unknown'}\nFlow: ${a.flow_control || 'Unknown'}\n`;
              text += `Tx Pkts: ${a.tx_packets || 0} | Rx Pkts: ${a.rx_packets || 0}\n`;
              text += `Tx Err: ${a.tx_errors || 0} | Rx Err: ${a.rx_errors || 0}`;
            }
            if (a.poe_power_w !== undefined) {
              text += `\nPoE: ${a.poe_power_w}W (${a.poe_current_ma}mA / ${a.poe_voltage_v}V)`;
            }
            return text;
          ]]]
        styles: &trunk_port_style
          card:
            - height: 85px
            - box-shadow: inset 0 0 15px rgba(0,0,0,0.6)
            - border: >
                [[[
                  let tg = entity.attributes ? entity.attributes.trunk_group : 'None';
                  if (tg === 'Trunk1') return '2px solid #3498db';
                  if (tg === 'Trunk2') return '2px solid #9b59b6';
                  return '2px solid #222';
                ]]]
            - border-radius: 6px
            - background-color: >
                [[[
                  var port = entity.entity_id.split('_')[3];
                  var tg = entity.attributes ? entity.attributes.trunk_group : 'None';
                  if (tg && tg !== 'None') {
                    var t_num = tg.replace('Trunk', '');
                    var t_admin = states['switch.keeplink_trunk_' + t_num + '_state'];
                    if (t_admin && t_admin.state === 'off') return '#555555';
                  } else {
                    var admin = states['switch.keeplink_port_' + port + '_state'];
                    if (admin && admin.state === 'off') return '#555555';
                  }
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
            trunk_badge:
              - position: absolute
              - top: 4px
              - right: 4px
              - font-size: 10px
              - font-weight: bold
              - color: white
              - background-color: >
                  [[[
                    let tg = entity.attributes ? entity.attributes.trunk_group : 'None';
                    if (tg === 'Trunk1') return '#2980b9';
                    if (tg === 'Trunk2') return '#8e44ad';
                    return 'transparent';
                  ]]]
              - padding: 1px 4px
              - border-radius: 4px
            poe:
              - font-size: 12px
              - font-weight: bold
              - color: '#f1c40f'
        custom_fields: &trunk_poe_field
          trunk_badge: >
            [[[
              let tg = entity.attributes ? entity.attributes.trunk_group : 'None';
              if (tg === 'Trunk1') return 'T1';
              if (tg === 'Trunk2') return 'T2';
              return '';
            ]]]
          poe: >
            [[[
              if (entity && entity.attributes && entity.attributes.poe_power_w > 0) {
                return parseFloat(entity.attributes.poe_power_w).toFixed(1) + 'W';
              }
              var port = entity.entity_id.split('_')[3];
              var poe = states['sensor.keeplink_port_' + port + '_poe_power'];
              if (poe && poe.state && !isNaN(poe.state) && parseFloat(poe.state) > 0) {
                return parseFloat(poe.state).toFixed(1) + 'W';
              }
              return '&nbsp;';
            ]]]

      # --- PORTS 2 to 8 (Using Anchors) ---
      - type: custom:button-card
        entity: binary_sensor.keeplink_port_2_link
        name: P2
        icon: mdi:ethernet
        tooltip: *trunk_port_tooltip
        styles: *trunk_port_style
        custom_fields: *trunk_poe_field

      - type: custom:button-card
        entity: binary_sensor.keeplink_port_3_link
        name: P3
        icon: mdi:ethernet
        tooltip: *trunk_port_tooltip
        styles: *trunk_port_style
        custom_fields: *trunk_poe_field

      - type: custom:button-card
        entity: binary_sensor.keeplink_port_4_link
        name: P4
        icon: mdi:ethernet
        tooltip: *trunk_port_tooltip
        styles: *trunk_port_style
        custom_fields: *trunk_poe_field

      - type: custom:button-card
        entity: binary_sensor.keeplink_port_5_link
        name: P5
        icon: mdi:ethernet
        tooltip: *trunk_port_tooltip
        styles: *trunk_port_style
        custom_fields: *trunk_poe_field

      - type: custom:button-card
        entity: binary_sensor.keeplink_port_6_link
        name: P6
        icon: mdi:ethernet
        tooltip: *trunk_port_tooltip
        styles: *trunk_port_style
        custom_fields: *trunk_poe_field

      - type: custom:button-card
        entity: binary_sensor.keeplink_port_7_link
        name: P7
        icon: mdi:ethernet
        tooltip: *trunk_port_tooltip
        styles: *trunk_port_style
        custom_fields: *trunk_poe_field

      - type: custom:button-card
        entity: binary_sensor.keeplink_port_8_link
        name: P8
        icon: mdi:ethernet
        tooltip: *trunk_port_tooltip
        styles: *trunk_port_style
        custom_fields: *trunk_poe_field

      # --- PORT 9 (SFP+) ---
      - type: custom:button-card
        entity: binary_sensor.keeplink_port_9_link
        name: SFP+
        icon: mdi:expansion-card
        tooltip: *trunk_port_tooltip
        styles: *trunk_port_style
        custom_fields: *trunk_poe_field

  # --- 3. LINK AGGREGATION (TRUNK GROUPS) BAR ---
  - type: grid
    columns: 2
    square: false
    cards:
      # --- TRUNK 1 ---
      - type: custom:button-card
        entity: binary_sensor.keeplink_trunk_1_link
        name: TRUNK 1
        icon: mdi:lan
        tooltip: &trunk_group_tooltip >
          [[[
            if (!entity || entity.state === 'unavailable') return 'Trunk Inactive';
            let a = entity.attributes;
            let text = `Type: ${a.trunk_type || 'Unknown'}\n`;
            text += `Member Ports: ${a.member_ports || 'None'}\n`;
            text += `Aggregated Ports: ${a.aggregated_ports || 'None'}\n`;
            text += `Speed: ${a.speed || 'Unknown'} | Flow: ${a.flow_control || 'Unknown'}\n`;
            text += `Tx Pkts: ${a.tx_packets || 0} | Rx Pkts: ${a.rx_packets || 0}\n`;
            text += `Tx Err: ${a.tx_errors || 0} | Rx Err: ${a.rx_errors || 0}`;
            return text;
          ]]]
        styles: &trunk_group_style
          card:
            - height: 75px
            - box-shadow: inset 0 0 12px rgba(0,0,0,0.5)
            - border: 2px solid #2980b9
            - border-radius: 6px
            - background-color: >
                [[[
                  if (!entity || entity.state === 'unavailable') return '#34495e';
                  var t_num = entity.entity_id.split('_')[3];
                  var admin = states['switch.keeplink_trunk_' + t_num + '_state'];
                  if (admin && admin.state === 'off') return '#555555';
                  if (entity.state === 'on') return '#1f618d';
                  return '#922b21';
                ]]]
          icon:
            - color: white
            - width: 24px
          name:
            - color: white
            - font-size: 13px
            - font-weight: bold
          custom_fields:
            info:
              - font-size: 11px
              - color: '#ecf0f1'
        custom_fields: &trunk_group_info
          info: >
            [[[
              if (!entity || entity.state === 'unavailable' || !entity.attributes) {
                return 'Inactive';
              }
              let a = entity.attributes;
              return `${a.trunk_type}: P${a.aggregated_ports} (${a.speed})`;
            ]]]

      # --- TRUNK 2 ---
      - type: custom:button-card
        entity: binary_sensor.keeplink_trunk_2_link
        name: TRUNK 2
        icon: mdi:lan
        tooltip: *trunk_group_tooltip
        styles:
          card:
            - height: 75px
            - box-shadow: inset 0 0 12px rgba(0,0,0,0.5)
            - border: 2px solid #8e44ad
            - border-radius: 6px
            - background-color: >
                [[[
                  if (!entity || entity.state === 'unavailable') return '#34495e';
                  var t_num = entity.entity_id.split('_')[3];
                  var admin = states['switch.keeplink_trunk_' + t_num + '_state'];
                  if (admin && admin.state === 'off') return '#555555';
                  if (entity.state === 'on') return '#6c3483';
                  return '#922b21';
                ]]]
          icon:
            - color: white
            - width: 24px
          name:
            - color: white
            - font-size: 13px
            - font-weight: bold
          custom_fields:
            info:
              - font-size: 11px
              - color: '#ecf0f1'
        custom_fields: *trunk_group_info

  # --- 4. STATS & CONTROLS ---
  - type: horizontal-stack
    cards:
      - type: gauge
        entity: sensor.keeplink_poe_total_power
        name: Total PoE Load
        min: 0
        max: 120
        needle: true
        severity:
          green: 0
          yellow: 60
          red: 100
      - type: button
        entity: button.keeplink_clear_statistics
        name: Clear Port Stats
        icon: mdi:delete-sweep
        show_name: true
        show_state: false
```

</details>