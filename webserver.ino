#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>

// WiFi credentials
const char *ssid = "Ushen";
const char *password = "00000000";

// WebSocket server details
const char *wsHost = "hci-pill-dispenser.onrender.com";
const int wsPort = 8765;  // WebSocket port
const char *wsPath = "/"; // WebSocket path

WebSocketsClient webSocket;

void setup()
{
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n=== ESP32 WebSocket Client Test ===");
    Serial.println("Starting WiFi connection attempt...");
    Serial.printf("WiFi SSID: %s\n", ssid);
    Serial.printf("WebSocket Server: %s:%d%s\n", wsHost, wsPort, wsPath);

    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);

    Serial.print("Connecting to WiFi");
    while (WiFi.status() != WL_CONNECTED)
    {
        delay(500);
        Serial.print(".");
    }

    Serial.println("\nWiFi Connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());

    // Initialize WebSocket connection with more debug info
    Serial.println("\nInitializing WebSocket connection...");
    webSocket.beginSSL(wsHost, wsPort, wsPath);
    webSocket.onEvent(webSocketEvent);
    webSocket.setReconnectInterval(5000);
    Serial.println("WebSocket initialization complete. Waiting for connection...");
}

void webSocketEvent(WStype_t type, uint8_t *payload, size_t length)
{
    switch (type)
    {
    case WStype_ERROR:
        Serial.printf("[WebSocket] Error: %u\n", length);
        break;

    case WStype_DISCONNECTED:
        Serial.printf("[WebSocket] Disconnected! Will try to reconnect in 5 seconds...\n");
        break;

    case WStype_CONNECTED:
        Serial.printf("[WebSocket] Connected to server: %s\n", payload);
        // Send a test message upon connection
        webSocket.sendTXT("{\"type\":\"hello\",\"message\":\"ESP32 Connected!\"}");
        break;

    case WStype_TEXT:
    {
        Serial.printf("[WebSocket] Received text: %s\n", payload);

        // Parse JSON
        StaticJsonDocument<1024> doc;
        DeserializationError error = deserializeJson(doc, payload);

        if (error)
        {
            Serial.print("JSON parsing failed! Error: ");
            Serial.println(error.c_str());
            return;
        }

        // Handle different message types
        const char *msgType = doc["type"];

        if (strcmp(msgType, "ping") == 0)
        {
            Serial.println("[WebSocket] Received ping, sending pong...");
            webSocket.sendTXT("{\"type\":\"pong\"}");
        }
        else if (strcmp(msgType, "dispense") == 0)
        {
            Serial.println("\n=== Received Dispense Event ===");
            Serial.print("Prescription ID: ");
            Serial.println((int)doc["prescription_id"]);
            Serial.print("Patient: ");
            Serial.println((const char *)doc["patient_name"]);
            Serial.print("Timestamp: ");
            Serial.println((const char *)doc["timestamp"]);

            JsonArray medications = doc["medications"];
            for (JsonVariant medication : medications)
            {
                Serial.println("\n--- Medication Details ---");
                Serial.print("Funnel ID: ");
                Serial.println((int)medication["funnel_id"]);
                Serial.print("Funnel Name: ");
                Serial.println((const char *)medication["funnel_name"]);
                Serial.print("Medication: ");
                Serial.println((const char *)medication["medication"]);
                Serial.print("Pills to dispense: ");
                Serial.println((int)medication["pills"]);
            }
            Serial.println("===========================\n");
        }
        break;
    }
    }
}

void loop()
{
    webSocket.loop();

    // Print connection status every 10 seconds
    static unsigned long lastStatusPrint = 0;
    if (millis() - lastStatusPrint > 10000)
    {
        if (WiFi.status() == WL_CONNECTED)
        {
            Serial.printf("[Status] WiFi Connected. RSSI: %d dBm\n", WiFi.RSSI());
        }
        else
        {
            Serial.println("[Status] WiFi Disconnected!");
        }
        lastStatusPrint = millis();
    }
}