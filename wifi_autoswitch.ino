#include <WiFi.h>
#include <HTTPClient.h>
#include <vector>
#include <string.h>
#include "esp_wpa2.h"


struct Network {
   String ssid, password, username;
   bool isEnterprise;
};

std::vector<Network> knownNetworks;

String currentFastest = "";
float prevFastestSpeed = 0.0;

// Parses a comma-separated list of networks in the format:
// "" | "ssid:password" | "ssid:username:password"
void parseNetworkList(const String &data) {
  knownNetworks.clear();
  int start = 0;

  while (start < data.length()) {
    int comma = data.indexOf(',', start);
    String segment = (comma == -1)
      ? data.substring(start)
      : data.substring(start, comma);

    // Split segment by colons
    int firstColon = segment.indexOf(':');
    int secondColon = segment.indexOf(':', firstColon + 1);

    if (firstColon != -1 && secondColon == -1) {
      // Format: ssid:password
      String ssid = segment.substring(0, firstColon);
      String password = segment.substring(firstColon + 1);
      knownNetworks.push_back({ssid, password, "", false});
    } else if (firstColon != -1 && secondColon != -1) {
      // Format: ssid:username:password
      String ssid = segment.substring(0, firstColon);
      String username = segment.substring(firstColon + 1, secondColon);
      String password = segment.substring(secondColon + 1);
      knownNetworks.push_back({ssid, password, username, true});
    }

    if (comma == -1) break;
    start = comma + 1;
  }

  Serial.printf("Got %d networks\n", knownNetworks.size());
}


// Check Serial, read a full line if available, and re-parse networks
bool processSerial() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length()) {
      parseNetworkList(line);
      return true;
    }
  }
  return false;
}

void testNetworkSpeed(const Network &net, float &fastestSpeed, String &currentFastest) {
  Serial.printf("Testing network speed for %s.\n", net.ssid.c_str());
  bool wifiConnected = false;
  if (!net.isEnterprise) {
    Serial.printf("-- Connecting via WPA Personal.\n");
    WiFi.begin(net.ssid.c_str(), net.password.c_str());
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts++ < 20) {
      delay(500);
    }
    wifiConnected = (WiFi.status() == WL_CONNECTED);
  } else {
    Serial.printf("-- Connecting via WPA2 Enterprise.\n");
    WiFi.disconnect(true);
    WiFi.mode(WIFI_STA);
    const char* user = net.username.c_str();
    const char* pass = net.password.c_str();
    esp_wifi_sta_wpa2_ent_set_identity((uint8_t*)user, strlen(user));
    esp_wifi_sta_wpa2_ent_set_username((uint8_t*)user, strlen(user));
    esp_wifi_sta_wpa2_ent_set_password((uint8_t*)pass, strlen(pass));
    esp_wifi_sta_wpa2_ent_set_disable_time_check(true);
    esp_wifi_sta_wpa2_ent_set_ca_cert(nullptr, 0);
    esp_wifi_sta_wpa2_ent_enable();
    WiFi.begin(net.ssid.c_str());
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts++ < 20) {
      delay(500);
    }
    wifiConnected = (WiFi.status() == WL_CONNECTED);
  }

  if (wifiConnected) {
    Serial.printf("-- Connection successful, testing internet speed.\n");
    HTTPClient http;
    http.begin("https://nyc.download.datapacket.com/100mb.bin");
    http.setConnectTimeout(5000);
    http.setTimeout(5000);

    int httpCode = http.GET();
    if (httpCode == HTTP_CODE_OK) {
      WiFiClient *stream = http.getStreamPtr();
      const size_t bufSize = 512;
      uint8_t buffer[bufSize];
      size_t totalBytes = 0;
      unsigned long t0 = millis();
      const unsigned long maxDurationMs = 5000;


      // Read until server closes connection
      while (http.connected() && millis() - t0 < maxDurationMs) {
        size_t avail = stream->available();
        if (avail == 0) {
          delay(1);
          continue;
        }
        size_t toRead = (avail < bufSize) ? avail : bufSize;
        int    readBytes = stream->readBytes(buffer, toRead);
        if (readBytes <= 0) break;
        totalBytes += readBytes;
      }

      unsigned long t1 = millis();
      float seconds = (t1 - t0) / 1000.0;
      // totalBytes is in bytes; convert to KB
      float speedKBs = (totalBytes / 1024.0) / seconds;

      Serial.printf("✅ [%s] %.2f KB/s (%u bytes in %.2fs)\n",
                    net.ssid.c_str(),
                    speedKBs,
                    (unsigned)totalBytes,
                    seconds);

      if (speedKBs > fastestSpeed) {
        fastestSpeed = speedKBs;
        currentFastest = net.ssid;
      }
    } else {
      Serial.printf("❌ HTTP error %d for %s\n", httpCode, net.ssid.c_str());
      // If check fails, use previous speed measurement
      if (net.ssid == currentFastest) {
        fastestSpeed = prevFastestSpeed;
      }
    }
    http.end();
  } else {
    Serial.printf("❌ WiFi connect failed for %s\n", net.ssid.c_str());
    // If check fails, use previous speed measurement
    if (net.ssid == currentFastest) {
      fastestSpeed = prevFastestSpeed;
    }
  }

  WiFi.disconnect(true);
  delay(500);
}

void setup() {
  Serial.begin(115200);
  Serial.println("ESP32 ready");
}

void loop() {
  static float fastestSpeed = -1;
  static String previousFastest = currentFastest;

  processSerial();

  Serial.printf("sweeping...\n");
  for (auto &net : knownNetworks) {
    processSerial();
    testNetworkSpeed(net, fastestSpeed, currentFastest);
  }

  if (currentFastest != previousFastest && currentFastest != "") {
    prevFastestSpeed = fastestSpeed;
    Serial.println("[NEW_FASTEST] " + currentFastest);
  }

  int delaySeconds = 5;
  Serial.printf("Sleeping %d s before next sweep\n", delaySeconds);
  delay(delaySeconds * 1000);
}
