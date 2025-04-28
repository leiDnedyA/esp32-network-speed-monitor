import os
import configparser
import serial
import time
import subprocess
from serial.tools import list_ports
import tkinter as tk
from tkinter import simpledialog, messagebox
import tempfile

CONNECTIONS_PATH = "/etc/NetworkManager/system-connections/"

def find_esp32_port():
    ports = list_ports.comports()
    for port in ports:
        if "USB" in port.device or "ttyACM" in port.device:
            return port.device
    return None

def ask_for_root_password():
    root = tk.Tk()
    root.withdraw()
    password = simpledialog.askstring("Root Password", "Enter root password:", show="*")
    root.destroy()
    return password

def get_available_wifi_ssids():
    try:
        result = subprocess.run(
            ["nmcli", "-f", "SSID", "dev", "wifi", "list"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        if result.returncode != 0:
            print(f"Error getting available SSIDs: {result.stderr}")
            return set()

        lines = result.stdout.strip().split("\n")[1:]  # Skip header
        ssids = set(line.strip() for line in lines if line.strip())
        print(f"Available SSIDs: {ssids}")
        return ssids
    except Exception as e:
        print(f"Exception while getting available SSIDs: {e}")
        return set()

def get_known_wifi_list():
    wifi_list = []
    password = ask_for_root_password()
    if not password:
        print("No password provided. Exiting.")
        return wifi_list

    available_ssids = get_available_wifi_ssids()

    try:
        files = sorted(os.listdir(CONNECTIONS_PATH))
        for fname in files:
            full_path = os.path.join(CONNECTIONS_PATH, fname)

            file_content = read_connection_file_as_root(password, full_path)
            if file_content is None:
                continue

            with tempfile.NamedTemporaryFile("w+", delete=False) as tmpfile:
                tmpfile.write(file_content)
                tmpfile_path = tmpfile.name

            config = configparser.ConfigParser()
            config.read(tmpfile_path)
            os.unlink(tmpfile_path)

            if "wifi" in config and "wifi-security" in config:
                ssid = config["wifi"].get("ssid")
                try:
                    if ssid and ';' in ssid:
                        ssid = ''.join([chr(int(n)) for n in ssid.split(';')[:-1]])
                except Exception as e:
                    print(f"Error decoding SSID: {e}")
                wifi_password = config["wifi-security"].get("psk")

                if ssid and wifi_password and ssid in available_ssids:
                    wifi_list.append((ssid, wifi_password))
    except Exception as e:
        print(f"Error reading Wi-Fi info: {e}")

    print(f"Filtered known wifi list: {wifi_list}")
    return wifi_list

def read_connection_file_as_root(password, filepath):
    if not password:
        print(f"Cannot read {filepath}: password is None.")
        return None
    try:
        result = subprocess.run(
            ["sudo", "-S", "cat", filepath],
            input=(password + "\n").encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        if result.returncode == 0:
            return result.stdout.decode()
        else:
            print(f"Failed to read {filepath}: {result.stderr.decode()}")
            return None
    except Exception as e:
        print(f"Exception while reading {filepath}: {e}")
        return None

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
            # Check the current SSID in case of change
            current_ssid = get_current_connection()
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
    time.sleep(2)

    send_all_wifi_credentials(ser, networks)
    listen_for_fastest_network(ser)

if __name__ == "__main__":
    main()
