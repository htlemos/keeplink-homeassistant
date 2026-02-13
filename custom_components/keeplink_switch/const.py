"""Constants for the Keeplink Switch integration."""

DOMAIN = "keeplink_switch"
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

# Default update interval (1 minute)
DEFAULT_SCAN_INTERVAL = 60

# Add new endpoints
ENDPOINT_INFO = "info.cgi"
ENDPOINT_PSE_SYSTEM = "pse_system.cgi"
ENDPOINT_PSE_PORT = "pse_port.cgi"
# NOVOS
ENDPOINT_PORT_SETTINGS = "port.cgi"
ENDPOINT_PORT_STATS = "port.cgi?page=stats"