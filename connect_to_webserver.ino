#include <WiFi.h>
#include <HTTPClient.h>

// WiFi credentials
const char* ssid = "Ushen";
const char* password = "00000000";

// Your Flask server address
const char* serverAddress = "http://10.54.146.73:5000";

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\nStarting WiFi connection attempt...");
  Serial.printf("Attempting to connect to: %s\n", ssid);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  
  int attempt = 0;
  while (WiFi.status() != WL_CONNECTED && attempt < 20) {
    delay(500);
    Serial.print(".");
    attempt++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nConnected to WiFi!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    Serial.printf("Will try to connect to server at: %s\n", serverAddress);
  } else {
    Serial.println("\nFailed to connect! Status code: ");
    switch(WiFi.status()) {
      case WL_IDLE_STATUS:
        Serial.println("Idle");
        break;
      case WL_NO_SSID_AVAIL:
        Serial.println("No SSID Available");
        break;
      case WL_CONNECT_FAILED:
        Serial.println("Connection Failed");
        break;
      case WL_DISCONNECTED:
        Serial.println("Disconnected");
        break;
      default:
        Serial.println(WiFi.status());
        break;
    }
  }
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    
    // First try the root endpoint
    String url = String(serverAddress) + "/";
    Serial.print("Connecting to: ");
    Serial.println(url);
    
    http.begin(url);
    
    // Send GET request
    int httpResponseCode = http.GET();
    
    if (httpResponseCode > 0) {
      Serial.print("HTTP Response code: ");
      Serial.println(httpResponseCode);
      String payload = http.getString();
      Serial.println("Response received!");
      // Print first 100 characters of response to avoid flooding serial
      Serial.println(payload.substring(0, 100) + "...");
    } else {
      Serial.print("Error code: ");
      Serial.println(httpResponseCode);
    }
    
    // Free resources
    http.end();
    
    delay(5000);  // Wait 5 seconds before next request
  } else {
    Serial.println("WiFi not connected");
    delay(5000);
  }
}