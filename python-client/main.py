import os
import configparser
import serial
import time
import subprocess
from serial.tools import list_ports

CONNECTIONS_PATH = "/etc/NetworkManager/system-connections/"

def find_esp32_port():
    ports = list_ports.comports()
    for port in ports:
        if "USB" in port.device or "ttyACM" in port.device:
            return port.device
    return None

def get_known_wifi_list():
    wifi_list = []
    try:
        files = sorted(os.listdir(CONNECTIONS_PATH))
        print(os.listdir(CONNECTIONS_PATH))
        for fname in files:
            full_path = os.path.join(CONNECTIONS_PATH, fname)
            config = configparser.ConfigParser()
            config.read(full_path)

            if "wifi" in config and "wifi-security" in config:
                ssid = config["wifi"].get("ssid")
                try:
                    if ';' in ssid:
                        # Decode ssid of format cc;cc;cc;cc; where cc is an ascii code
                        print(ssid)
                        # ssid = [chr(int(n)) for n in ssid.split(';')[:-1]].join('')
                        print([chr(int(n)) for n in ssid.split(';')[:-1]])
                        print(ssid)
                except:
                    print('err')
                    pass
                password = config["wifi-security"].get("psk")
                if ssid and password:
                    wifi_list.append((ssid, password))
    except Exception as e:
        print(f"Error reading Wi-Fi info: {e}")
    print(wifi_list)
    return wifi_list

def send_all_wifi_credentials(ser, networks):
    formatted = ",".join([f"{ssid}:{password}" for ssid, password in networks]) + "\n"
    ser.write(formatted.encode())
    print(f"📤 Sent network list to ESP32 ({len(networks)} networks).")

def get_current_connection():
    result = subprocess.run(
        ["/usr/bin/nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
        stdout=subprocess.PIPE,
        universal_newlines=True
    )
    for line in result.stdout.strip().splitlines():
        if line.startswith("yes:"):
            return line.split(":")[1]
    return None

def switch_to_network(ssid):
    print(f"🔄 Switching to {ssid}...")
    subprocess.run(["/usr/bin/nmcli", "device", "wifi", "connect", ssid])

def listen_for_fastest_network(ser):
    current_ssid = get_current_connection()
    print(f"📡 Listening for fastest network updates... Currently connected to: {current_ssid or 'None'}")

    while True:
        line = ser.readline().decode(errors='ignore').strip()
        if line.startswith("[NEW_FASTEST]"):
            fastest_ssid = line.split("]")[1].strip()
            print(f"\n🚀 New fastest network detected: {fastest_ssid}")
            if fastest_ssid and fastest_ssid != current_ssid:
                print(f"🔍 Currently on: {current_ssid}, switching to: {fastest_ssid}")
                switch_to_network(fastest_ssid)
                current_ssid = fastest_ssid
        elif line:
            print(f"[ESP32] {line}")

def main():
    port = find_esp32_port()
    if not port:
        print("ESP32 not found.")
        return

    networks = get_known_wifi_list()
    if not networks:
        print("No known networks found.")
        return

    ser = serial.Serial(port, 115200, timeout=8)
    time.sleep(2)  # Wait for ESP32 reset

    send_all_wifi_credentials(ser, networks)
    listen_for_fastest_network(ser)

if __name__ == "__main__":
    main()
