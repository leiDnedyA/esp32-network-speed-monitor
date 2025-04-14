#include <WiFi.h>
#include <HTTPClient.h>
#include <map>

struct Network {
  String ssid;
  String password;
};

std::vector<Network> knownNetworks;
std::map<String, float> networkSpeeds;
String currentFastest = "";
float fastestSpeed = -1;

void testNetworkSpeed(const Network& net) {
  Serial.println("Scanning for network: " + net.ssid);
  int n = WiFi.scanNetworks();
  bool found = false;
  for (int i = 0; i < n; i++) {
    if (WiFi.SSID(i) == net.ssid) {
      found = true;
      break;
    }
  }

  if (!found) {
    networkSpeeds[net.ssid] = -1;
    Serial.println("⚠️ " + net.ssid + " not found.");
    return;
  }

  WiFi.begin(net.ssid.c_str(), net.password.c_str());

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    const char* testUrl = "http://speed.hetzner.de/100KB.bin";
    http.begin(testUrl);

    unsigned long startTime = millis();
    int httpCode = http.GET();
    unsigned long endTime = millis();

    if (httpCode > 0) {
      String payload = http.getString();
      size_t bytes = payload.length();
      float seconds = (endTime - startTime) / 1000.0;
      float speed_kbps = (bytes / 1024.0) / seconds;

      networkSpeeds[net.ssid] = speed_kbps;

      Serial.printf("✅ [%s] Speed: %.2f KB/s\n", net.ssid.c_str(), speed_kbps);

      if (speed_kbps > fastestSpeed) {
        fastestSpeed = speed_kbps;
        currentFastest = net.ssid;
        Serial.println("[NEW_FASTEST] " + currentFastest);
      }
    } else {
      Serial.println("Speed test failed for " + net.ssid);
      networkSpeeds[net.ssid] = -1;
    }

    http.end();
  } else {
    Serial.println("Failed to connect to " + net.ssid);
    networkSpeeds[net.ssid] = -1;
  }

  WiFi.disconnect(true);
  delay(1000);
}

void setup() {
  Serial.begin(115200);
  Serial.println("ESP32 ready. Waiting for network list...");
}

void loop() {
  if (Serial.available()) {
    String data = Serial.readStringUntil('\n');
    data.trim();
    knownNetworks.clear();
    networkSpeeds.clear();
    currentFastest = "";
    fastestSpeed = -1;

    int start = 0;
    while (start < data.length()) {
      int commaIdx = data.indexOf(',', start);
      String pair = commaIdx == -1 ? data.substring(start) : data.substring(start, commaIdx);
      int colonIdx = pair.indexOf(':');
      if (colonIdx != -1) {
        String ssid = pair.substring(0, colonIdx);
        String password = pair.substring(colonIdx + 1);
        knownNetworks.push_back({ ssid, password });
      }
      if (commaIdx == -1) break;
      start = commaIdx + 1;
    }

    Serial.printf("📥 Received %d networks. Starting loop...\n", knownNetworks.size());
  }

  for (auto& net : knownNetworks) {
    testNetworkSpeed(net);
  }

  Serial.println("🔁 Restarting test loop in 30 seconds...");
  delay(30000);
}
