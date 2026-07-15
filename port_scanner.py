import socket
import re
from common_ports import ports_and_services


def is_valid_ip(target):
    """Vérifie si la chaîne a le format d'une adresse IP (x.x.x.x)"""
    pattern = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
    return re.match(pattern, target) is not None


def get_open_ports(target, port_range, verbose=False):
    if is_valid_ip(target):
        try:
            socket.inet_aton(target)
        except socket.error:
            return "Error: Invalid IP address"
        ip = target
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except socket.herror:
            hostname = ip
    else:
        try:
            ip = socket.gethostbyname(target)
            hostname = target
        except socket.gaierror:
            return "Error: Invalid hostname"

    open_ports = []
    for port in range(port_range[0], port_range[-1] + 1):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((ip, port))
        if result == 0:
            open_ports.append(port)
        sock.close()

    if not verbose:
        return open_ports

    if hostname == ip:
        output = f'Open ports for {ip}\n'
    else:
        output = f'Open ports for {hostname} ({ip})\n'

    output += 'PORT     SERVICE\n'
    for port in open_ports:
        service = ports_and_services.get(port, 'unknown')
        output += f'{port:<9}{service}\n'

    return output.rstrip('\n')