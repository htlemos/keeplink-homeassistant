"""DataUpdateCoordinator for Keeplink Switch."""
import logging
import hashlib
import aiohttp
import async_timeout
from bs4 import BeautifulSoup
from datetime import timedelta

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    DOMAIN, 
    ENDPOINT_INFO, 
    ENDPOINT_PSE_SYSTEM, 
    ENDPOINT_PSE_PORT,
    ENDPOINT_PORT_SETTINGS,
    ENDPOINT_PORT_STATS
)

_LOGGER = logging.getLogger(__name__)

class KeeplinkCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the switch."""

    def __init__(self, hass, session, host, username, password, scan_interval):
        """Initialize."""
        self.host = host
        self.username = username
        self.password = password
        self.session = session
        self.mac_address = None
        self.device_info = {}

        # Auth Hash Calculation
        auth_str = f"{username}{password}"
        self.auth_cookie = hashlib.md5(auth_str.encode()).hexdigest()

        super().__init__(
            hass,
            _LOGGER,
            name=f"Keeplink Switch ({host})",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self):
        """Fetch data from API endpoints."""
        data = {"ports": {}} # Inicializa estrutura de portas
        headers = {
            "Referer": f"http://{self.host}/login.cgi",
            "User-Agent": "HomeAssistant/1.0"
        }
        cookies = {"admin": self.auth_cookie}

        try:
            async with async_timeout.timeout(20):
                # 1. Info e PoE (Mantemos o que já tínhamos)
                data.update(await self._fetch_page(ENDPOINT_INFO, headers, cookies, self._parse_info))
                
                # PoE System e Port já parseiam para dentro de data["ports"] se a estrutura existir
                # Mas as funções antigas assumiam que data["ports"] era criado lá.
                # Vamos garantir que as funções de parse atualizam o dicionário existente.
                
                # Fetch PoE System
                poe_sys_data = await self._fetch_page(ENDPOINT_PSE_SYSTEM, headers, cookies, self._parse_pse_system)
                data.update(poe_sys_data)

                # Fetch PoE Port (Esta função precisa de cuidado para fazer merge)
                poe_port_data = await self._fetch_page(ENDPOINT_PSE_PORT, headers, cookies, self._parse_pse_port)
                self._deep_merge_ports(data, poe_port_data)

                # 2. Fetch Port Settings (Velocidade/Duplex)
                settings_data = await self._fetch_page(ENDPOINT_PORT_SETTINGS, headers, cookies, self._parse_port_settings)
                self._deep_merge_ports(data, settings_data)

                # 3. Fetch Port Stats (Link Status e Pacotes)
                stats_data = await self._fetch_page(ENDPOINT_PORT_STATS, headers, cookies, self._parse_port_stats)
                self._deep_merge_ports(data, stats_data)

                # Update Device Info
                if "mac" in data:
                    self.mac_address = data["mac"]
                    self.device_info = {
                        "manufacturer": "Keeplink",
                        "model": data.get("model", "Unknown Model"),
                        "sw_version": data.get("firmware", "Unknown"),
                        "hw_version": data.get("hardware", "Unknown"),
                    }
            
            return data

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    def _deep_merge_ports(self, main_data, new_data):
        """Helper para juntar dados de portas sem apagar o que já lá estava."""
        if "ports" not in main_data:
            main_data["ports"] = {}
            
        if "ports" in new_data:
            for port, info in new_data["ports"].items():
                if port not in main_data["ports"]:
                    main_data["ports"][port] = {}
                main_data["ports"][port].update(info)

    async def _fetch_page(self, endpoint, headers, cookies, parser_func):
        """Helper to fetch and parse a single page."""
        url = f"http://{self.host}/{endpoint}"
        response = await self.session.get(url, headers=headers, cookies=cookies)
        if "login.cgi" in str(response.url): raise ConfigEntryAuthFailed("Authentication failed.")
        html = await response.text()
        return parser_func(html)

    # --- PARSERS EXISTENTES (Info, PoE System, PoE Port) MANTÊM-SE IGUAIS ---
    # (Copie as funções _parse_info, _parse_pse_system e _parse_pse_port do código anterior)
    # Apenas garanta que _parse_pse_port retorna {"ports": {1: {dados...}}}
    
    def _parse_info(self, html):
        # (O mesmo código de antes)
        soup = BeautifulSoup(html, 'html.parser')
        data = {}
        rows = soup.find_all('tr')
        for row in rows:
            cols = row.find_all(['th', 'td'])
            if len(cols) == 2:
                key = cols[0].get_text(strip=True)
                value = cols[1].get_text(strip=True)
                if "Device Model" in key: data["model"] = value
                elif "Firmware Version" in key: data["firmware"] = value
                elif "MAC Address" in key: data["mac"] = value
                elif "Hardware Version" in key: data["hardware"] = value
                elif "IP Address" in key: data["ip_address"] = value
                elif "Netmask" in key: data["netmask"] = value
                elif "Gateway" in key: data["gateway"] = value
                elif "Firmware Date" in key: data["firmware_date"] = value
        return data

    def _parse_pse_system(self, html):
        # (O mesmo código de antes)
        soup = BeautifulSoup(html, 'html.parser')
        data = {}
        input_tag = soup.find('input', {'name': 'pse_con_pwr'})
        if input_tag and input_tag.get('value'):
            try:
                data["poe_total_power"] = float(input_tag['value'])
            except ValueError:
                pass
        return data
        
    def _parse_pse_port(self, html):
        # (O mesmo código de antes)
        soup = BeautifulSoup(html, 'html.parser')
        data = {"ports": {}} 
        tables = soup.find_all('table')
        if len(tables) < 2: return data
        data_table = tables[1]
        rows = data_table.find_all('tr')
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) >= 7:
                port_name = cols[0].get_text(strip=True)
                try:
                    port_num = int(port_name.replace("Port ", ""))
                except ValueError:
                    continue
                def parse_val(text): return float(text) if text != "-" else 0.0
                data["ports"][port_num] = {
                    "poe_power": parse_val(cols[4].get_text(strip=True)),
                    "poe_voltage": parse_val(cols[5].get_text(strip=True)),
                    "poe_current": parse_val(cols[6].get_text(strip=True)),
                    "poe_enabled": "Enable" in cols[1].get_text(strip=True)
                }
        return data

    # --- NOVOS PARSERS ---

    def _parse_port_settings(self, html):
        """Parse port.cgi (Settings) para obter Velocidade Negociada."""
        soup = BeautifulSoup(html, 'html.parser')
        data = {"ports": {}}
        
        # Procuramos a tabela no fundo que tem "Config" e "Actual"
        # Esta tabela tem headers complexos (rowspan/colspan), então procuramos pelo conteúdo
        tables = soup.find_all('table')
        # Geralmente é a última tabela
        target_table = tables[-1]
        
        rows = target_table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            # Estrutura: [Port X, State, Config, Actual(SPEED), Config, Actual(FLOW)]
            # Exemplo Port 1: [Port 1, Enable, Auto, 1000Full, On, On]
            if len(cols) >= 6:
                port_text = cols[0].get_text(strip=True)
                if "Port" not in port_text: continue
                
                try:
                    port_num = int(port_text.replace("Port ", ""))
                except ValueError: continue

                actual_speed = cols[3].get_text(strip=True)
                flow_control = cols[5].get_text(strip=True)
                
                data["ports"][port_num] = {
                    "speed": actual_speed,
                    "flow_control": flow_control
                }
        return data

    def _parse_port_stats(self, html):
        """Parse port.cgi?page=stats para Link Status e Tráfego."""
        soup = BeautifulSoup(html, 'html.parser')
        data = {"ports": {}}
        
        # A tabela de stats é simples
        tables = soup.find_all('table')
        if not tables: return data
        
        # Assumindo que é a primeira tabela dentro do fieldset
        target_table = tables[0]
        rows = target_table.find_all('tr')
        
        for row in rows:
            cols = row.find_all(['td'])
            # Estrutura: [Port 1, Enable, Link Up, TxGood, TxBad, RxGood, RxBad]
            if len(cols) >= 7:
                port_text = cols[0].get_text(strip=True)
                if "Port" not in port_text: continue
                
                try:
                    port_num = int(port_text.replace("Port ", ""))
                except ValueError: continue

                link_status = cols[2].get_text(strip=True) # "Link Up" ou "Link Down"
                
                # Função para calcular o BigInt do JS: High * 4294967296 + Low
                def parse_bigint(text_content):
                    if "-" in text_content:
                        parts = text_content.split("-")
                        try:
                            high = int(parts[0])
                            low = int(parts[1])
                            return (high * 4294967296) + low
                        except ValueError:
                            return 0
                    return 0

                tx_good = parse_bigint(cols[3].get_text(strip=True))
                tx_bad = int(cols[4].get_text(strip=True))
                rx_good = parse_bigint(cols[5].get_text(strip=True))
                rx_bad = int(cols[6].get_text(strip=True))

                data["ports"][port_num] = {
                    "link_status": link_status,
                    "is_link_up": "Link Up" in link_status,
                    "tx_packets": tx_good,
                    "rx_packets": rx_good,
                    "tx_errors": tx_bad,
                    "rx_errors": rx_bad
                }
        return data
    
    async def async_set_poe_state(self, port_num, state):
        """Send POST request to enable/disable PoE."""
        # Port 1 is ID 0, Port 2 is ID 1, etc.
        port_id = port_num - 1 
        state_val = "1" if state else "0"
        
        url = f"http://{self.host}/{ENDPOINT_PSE_PORT}"
        headers = {
            "Referer": f"http://{self.host}/{ENDPOINT_PSE_PORT}", # Important!
            "User-Agent": "HomeAssistant/1.0"
        }
        cookies = {"admin": self.auth_cookie}
        
        # Payload: portid=3&state=0&submit=Apply&cmd=poe
        payload = {
            "portid": port_id,
            "state": state_val,
            "submit": "Apply",
            "cmd": "poe"
        }
        
        try:
            await self.session.post(url, headers=headers, cookies=cookies, data=payload)
            # Force immediate refresh after change
            await self.async_request_refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set PoE state for port {port_num}: {err}")