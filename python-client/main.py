#!/usr/bin/env python3
import os
import configparser
import serial
import time
import subprocess
from serial.tools import list_ports
import threading
import tkinter as tk
from tkinter import simpledialog, messagebox
import tempfile

CONNECTIONS_PATH = "/etc/NetworkManager/system-connections/"

def find_esp32_port():
    for port in list_ports.comports():
        if "USB" in port.device or "ttyACM" in port.device:
            return port.device
    return None

def ask_for_root_password():
    root = tk.Tk()
    root.withdraw()
    pw = simpledialog.askstring("Root Password", "Enter root password:", show="*")
    root.destroy()
    return pw

def get_available_wifi_ssids():
    try:
        result = subprocess.run(
            ["nmcli", "-f", "SSID", "dev", "wifi", "list"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode != 0:
            print(f"Error listing SSIDs: {result.stderr.strip()}")
            return set()
        lines = result.stdout.strip().splitlines()[1:]
        return {line.strip() for line in lines if line.strip()}
    except Exception as e:
        print(f"Exception in get_available_wifi_ssids: {e}")
        return set()

def read_connection_file_as_root(password, filepath):
    try:
        proc = subprocess.run(
            ["sudo", "-S", "cat", filepath],
            input=(password + "\n").encode(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if proc.returncode == 0:
            return proc.stdout.decode()
        else:
            print(f"sudo cat {filepath} failed: {proc.stderr.decode().strip()}")
            return None
    except Exception as e:
        print(f"Exception reading {filepath}: {e}")
        return None

def get_known_wifi_list(password):
    """Return list of (ssid, psk) for known networks currently in range."""
    available = get_available_wifi_ssids()
    wifi_list = []
    for fname in sorted(os.listdir(CONNECTIONS_PATH)):
        path = os.path.join(CONNECTIONS_PATH, fname)
        content = read_connection_file_as_root(password, path)
        if not content:
            continue
        # parse
        cfg = configparser.ConfigParser()
        with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
            tmp.write(content)
            tmp.flush()
            tmp_path = tmp.name
        cfg.read(tmp_path)
        os.unlink(tmp_path)
        if "wifi" in cfg and "wifi-security" in cfg:
            ssid = cfg["wifi"].get("ssid")
            psk = cfg["wifi-security"].get("psk")
            if ssid and psk and ssid in available:
                wifi_list.append((ssid, psk))
    print(f"🏷️  Known in-range networks: {[s for s,_ in wifi_list]}")
    return wifi_list

def send_all_wifi_credentials(ser, networks):
    payload = ",".join(f"{s}:{p}" for s,p in networks) + "\n"
    ser.write(payload.encode())
    print(f"Sent {len(networks)} networks to ESP32")

def poll_for_changes(ser, password, interval=5):
    prev_ssids = set()
    while True:
        time.sleep(interval)
        new_list = get_known_wifi_list(password)
        new_ssids = {s for s,_ in new_list}
        if new_ssids != prev_ssids:
            print("Wi-Fi list changed, updating ESP32…")
            send_all_wifi_credentials(ser, new_list)
            prev_ssids = new_ssids

def get_current_connection():
    res = subprocess.run(
        ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
        stdout=subprocess.PIPE, text=True
    )
    for line in res.stdout.splitlines():
        if line.startswith("yes:"):
            return line.split(":",1)[1]
    return None

def switch_to_network(ssid):
    print(f"Switching to {ssid} …")
    subprocess.run(["nmcli", "device", "wifi", "connect", ssid])

def listen_for_fastest_network(ser):
    current = get_current_connection()
    print(f"Listening for new-fastest (now on: {current})")
    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue
        if line.startswith("[NEW_FASTEST]"):
            best = line.split("]",1)[1].strip()
            print(f"New fastest: {best}")
            if best != current:
                switch_to_network(best)
                current = best
        else:
            print(f"[ESP32] {line}")

def main():
    port = find_esp32_port()
    if not port:
        print("❌ ESP32 serial port not found.")
        return

    password = ask_for_root_password()
    if not password:
        print("❌ No root password provided.")
        return

    ser = serial.Serial(port, 115200, timeout=1)
    time.sleep(2)  # allow ESP32 to reset
    initial = get_known_wifi_list(password)
    if not initial:
        print("⚠️  No known networks in range. Exiting.")
        return

    send_all_wifi_credentials(ser, initial)
    # start background poller
    poll_thread = threading.Thread(
        target=poll_for_changes, args=(ser, password), daemon=True
    )
    poll_thread.start()

    # now block on listening for fastest
    listen_for_fastest_network(ser)

if __name__ == "__main__":
    main()
