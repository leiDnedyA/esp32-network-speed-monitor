import os
import configparser
import serial
import time
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
        for fname in files:
            full_path = os.path.join(CONNECTIONS_PATH, fname)
            config = configparser.ConfigParser()
            config.read(full_path)

            if "wifi" in config and "wifi-security" in config:
                ssid = config["wifi"].get("ssid")
                password = config["wifi-security"].get("psk")
                if ssid and password:
                    wifi_list.append((ssid, password))
    except Exception as e:
        print(f"Error reading Wi-Fi info: {e}")
    return wifi_list

def send_all_wifi_credentials(ser, networks):
    formatted = ",".join([f"{ssid}:{password}" for ssid, password in networks]) + "\n"
    ser.write(formatted.encode())
    print(f"📤 Sent network list to ESP32 ({len(networks)} networks).")

def listen_for_fastest_network(ser):
    print("📡 Listening for fastest network updates from ESP32...")
    while True:
        line = ser.readline().decode(errors='ignore').strip()
        if line.startswith("[NEW_FASTEST]"):
            fastest_ssid = line.split("]")[1].strip()
            print(f"\n🚀 New fastest network: {fastest_ssid}\n")
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
    time.sleep(2)  # Wait for ESP32 to reset

    send_all_wifi_credentials(ser, networks)
    listen_for_fastest_network(ser)

if __name__ == "__main__":
    main()
