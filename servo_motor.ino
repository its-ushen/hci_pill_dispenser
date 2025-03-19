#include <ESP32Servo.h>

Servo myServo1;
Servo myServo2;
int servoPin1 = 18;
int servoPin2 = 19;

void setup()
{
    // put your setup code here, to run once:
    myServo1.attach(servoPin1);
    // myServo2.attach(servoPin2);
    Serial.begin(115200);
}

void loop()
{
    // put your main code here, to run repeatedly:
    if (Serial.available())
    {
        int angle = Serial.parseInt();
        // Move to position at normal speed
        myServo1.write(angle);
        // delay(500); // Wait for servo to reach position

        // Return to 0 quickly using writeMicroseconds
        // 544 is typically the minimum pulse width (0 degrees)
        myServo1.writeMicroseconds(544);
        // myServo2.writeMicroseconds(544);  // Uncomment if using second servo
    }

}
