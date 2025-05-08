#include <WiFi.h>
#include <HTTPClient.h>
#include <vector>

struct Network { String ssid, password; };

std::vector<Network> knownNetworks;

// Parses a comma-separated "ssid:pass,ssid2:pass2,..." line
void parseNetworkList(const String &data) {
  knownNetworks.clear();
  int start = 0;
  while (start < data.length()) {
    int comma = data.indexOf(',', start);
    String pair = (comma == -1)
      ? data.substring(start)
      : data.substring(start, comma);
    int colon = pair.indexOf(':');
    if (colon > 0) {
      String ssid = pair.substring(0, colon);
      String pass = pair.substring(colon + 1);
      knownNetworks.push_back({ssid, pass});
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
  // scan, connect, HTTP GET, measure KB/s … (unchanged from before)
  Serial.println("Scanning for " + net.ssid);
  int n = WiFi.scanNetworks();
  bool found = false;
  for (int i = 0; i < n; i++) {
    if (WiFi.SSID(i) == net.ssid) { found = true; break; }
  }
  if (!found) {
    Serial.println("⚠️  Not found: " + net.ssid);
    return;
  }
  WiFi.begin(net.ssid.c_str(), net.password.c_str());
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts++ < 20) {
    delay(500);
  }
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin("https://nyc.download.datapacket.com/100mb.bin");
    unsigned long t0 = millis();
    int code = http.GET();
    unsigned long t1 = millis();
    if (code > 0) {
      String payload = http.getString();
      float kb = payload.length() / 1024.0 / 1024.0;
      float secs = (t1 - t0) / 1000.0;
      float speed = kb / secs;
      Serial.printf("✅ [%s] %.2f KB/s\n", net.ssid.c_str(), speed);
      if (speed > fastestSpeed) {
        fastestSpeed = speed;
        currentFastest = net.ssid;
        Serial.println("[NEW_FASTEST] " + currentFastest);
      }
    } else {
      Serial.println("❌ HTTP failed for " + net.ssid);
    }
    http.end();
  } else {
    Serial.println("❌ Connect failed: " + net.ssid);
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
  static String currentFastest = "";

  // 1) Immediately handle any incoming list updates
  if (processSerial()) {
    // reset tracking so that first sweep re-initializes
    fastestSpeed = -1;
    currentFastest = "";
  }

  // 2) Sweep through current list
  for (auto &net : knownNetworks) {
    // allow an in-flight update to interrupt
    if (processSerial()) {
      fastestSpeed = -1;
      currentFastest = "";
      break;
    }
    testNetworkSpeed(net, fastestSpeed, currentFastest);
  }

  int delaySeconds = 5;
  Serial.printf("Sleeping %d s before next sweep\n", delaySeconds);
  delay(delaySeconds * 1000);
}
