#include <Arduino.h>
#include <Wire.h>

// --- Configuration ---
const uint8_t MPU1_ADDR = 0x68; // above knee (thigh)
const uint8_t MPU2_ADDR = 0x69; // above ankle (shank)
// Piezo wiring: Piezo Negative -> GND
// Piezo Positive -> series resistor (10k-100k) -> ADC GPIO (e.g., GPIO4)
// ADC GPIO -> 1M pull-down -> GND (bias to read spikes)
const int FORCE_PIN = 4; // update to the GPIO you're using for the piezo

const float sampleHz = 100.0;
const unsigned long sampleIntervalUs = (unsigned long)(1000000.0 / sampleHz);

// Gyro calibration offsets
float gyroOffset1X = 0, gyroOffset1Y = 0, gyroOffset1Z = 0;
float gyroOffset2X = 0, gyroOffset2Y = 0, gyroOffset2Z = 0;

// Madgwick filter implementation (simplified)
class Madgwick {
public:
  float q0, q1, q2, q3;
  float beta; // algorithm gain
  Madgwick(float beta_ = 0.1f) : q0(1), q1(0), q2(0), q3(0), beta(beta_) {}

  // gx,gy,gz in rad/s, ax,ay,az in g, dt in seconds
  void update(float gx, float gy, float gz, float ax, float ay, float az, float dt) {
    float recipNorm;
    float s0, s1, s2, s3;
    float qDot0, qDot1, qDot2, qDot3;

    // Rate of change of quaternion from gyroscope
    qDot0 = 0.5f * (-q1 * gx - q2 * gy - q3 * gz);
    qDot1 = 0.5f * (q0 * gx + q2 * gz - q3 * gy);
    qDot2 = 0.5f * (q0 * gy - q1 * gz + q3 * gx);
    qDot3 = 0.5f * (q0 * gz + q1 * gy - q2 * gx);

    // Normalise accelerometer measurement
    recipNorm = sqrtf(ax * ax + ay * ay + az * az);
    if (recipNorm == 0.0f) return;
    recipNorm = 1.0f / recipNorm;
    ax *= recipNorm; ay *= recipNorm; az *= recipNorm;

    // Auxiliary variables to avoid repeated arithmetic
    float _2q0 = 2.0f * q0;
    float _2q1 = 2.0f * q1;
    float _2q2 = 2.0f * q2;
    float _2q3 = 2.0f * q3;
    float _4q0 = 4.0f * q0;
    float _4q1 = 4.0f * q1;
    float _4q2 = 4.0f * q2;
    float _8q1 = 8.0f * q1;
    float _8q2 = 8.0f * q2;
    float q0q0 = q0 * q0;
    float q1q1 = q1 * q1;
    float q2q2 = q2 * q2;
    float q3q3 = q3 * q3;

    // Gradient decent algorithm corrective step
    s0 = _4q0 * q2q2 + _2q2 * ax + _4q0 * q1q1 - _2q1 * ay;
    s1 = _4q1 * q3q3 - _2q3 * ax + 4.0f * q0q0 * q1 - _2q0 * ay - _4q1 + _8q1 * q1q1 + _8q1 * q2q2 + _4q1 * az;
    s2 = 4.0f * q0q0 * q2 + _2q0 * ax + _4q2 * q3q3 - _2q3 * ay - _4q2 + _8q2 * q1q1 + _8q2 * q2q2 + _4q2 * az;
    s3 = 4.0f * q1q1 * q3 - _2q1 * ax + 4.0f * q2q2 * q3 - _2q2 * ay;

    recipNorm = sqrtf(s0 * s0 + s1 * s1 + s2 * s2 + s3 * s3);
    if (recipNorm == 0.0f) return;
    recipNorm = 1.0f / recipNorm;
    s0 *= recipNorm; s1 *= recipNorm; s2 *= recipNorm; s3 *= recipNorm;

    // Apply feedback step
    qDot0 -= beta * s0;
    qDot1 -= beta * s1;
    qDot2 -= beta * s2;
    qDot3 -= beta * s3;

    // Integrate to yield quaternion
    q0 += qDot0 * dt;
    q1 += qDot1 * dt;
    q2 += qDot2 * dt;
    q3 += qDot3 * dt;

    // Normalise quaternion
    recipNorm = sqrtf(q0 * q0 + q1 * q1 + q2 * q2 + q3 * q3);
    if (recipNorm != 0.0f) {
      recipNorm = 1.0f / recipNorm;
      q0 *= recipNorm; q1 *= recipNorm; q2 *= recipNorm; q3 *= recipNorm;
    }
  }
};

Madgwick filter1(0.12f), filter2(0.12f);

// I2C helpers
void mpuWrite(uint8_t addr, uint8_t reg, uint8_t val) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

void mpuRead(uint8_t addr, uint8_t reg, uint8_t count, uint8_t* dest) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom((int)addr, (int)count);
  for (uint8_t i = 0; i < count; i++) dest[i] = Wire.read();
}

void initMPU(uint8_t addr) {
  mpuWrite(addr, 0x6B, 0x00); // wake
  delay(10);
  mpuWrite(addr, 0x1B, 0x00); // gyro ±250
  mpuWrite(addr, 0x1C, 0x00); // accel ±2g
}

void readMPURaw(uint8_t addr, int16_t& ax, int16_t& ay, int16_t& az, int16_t& gx, int16_t& gy, int16_t& gz) {
  uint8_t buf[14];
  mpuRead(addr, 0x3B, 14, buf);
  ax = ((int16_t)buf[0] << 8) | buf[1];
  ay = ((int16_t)buf[2] << 8) | buf[3];
  az = ((int16_t)buf[4] << 8) | buf[5];
  gx = ((int16_t)buf[8] << 8) | buf[9];
  gy = ((int16_t)buf[10] << 8) | buf[11];
  gz = ((int16_t)buf[12] << 8) | buf[13];
}

inline float accelToG(int16_t raw) { return raw / 16384.0f; }
inline float gyroToDeg(int16_t raw) { return raw / 131.0f; }

void calibrateGyros() {
  const int samples = 200;
  long gx1 = 0, gy1 = 0, gz1 = 0;
  long gx2 = 0, gy2 = 0, gz2 = 0;
  for (int i = 0; i < samples; ++i) {
    int16_t ax, ay, az, gx, gy, gz;
    readMPURaw(MPU1_ADDR, ax, ay, az, gx, gy, gz);
    gx1 += gx; gy1 += gy; gz1 += gz;
    readMPURaw(MPU2_ADDR, ax, ay, az, gx, gy, gz);
    gx2 += gx; gy2 += gy; gz2 += gz;
    delay(5);
  }
  gyroOffset1X = (float)gx1 / samples;
  gyroOffset1Y = (float)gy1 / samples;
  gyroOffset1Z = (float)gz1 / samples;
  gyroOffset2X = (float)gx2 / samples;
  gyroOffset2Y = (float)gy2 / samples;
  gyroOffset2Z = (float)gz2 / samples;
}

void setup() {
  Serial.begin(115200);
  delay(50);
  Wire.begin();

  initMPU(MPU1_ADDR);
  initMPU(MPU2_ADDR);

  Serial.println("MPUs initialized. Calibrating gyros, keep device still...");
  calibrateGyros();
  Serial.println("Calibration done.");

  // New CSV header with full IMU data
  Serial.println("time_ms,th_qw,th_qx,th_qy,th_qz,th_ax_g,th_ay_g,th_az_g,th_gx_dps,th_gy_dps,th_gz_dps,sh_qw,sh_qx,sh_qy,sh_qz,sh_ax_g,sh_ay_g,sh_az_g,sh_gx_dps,sh_gy_dps,sh_gz_dps,knee_deg,force_raw,stance");
}

void loop() {
  static unsigned long lastMicros = micros();
  unsigned long now = micros();
  unsigned long elapsed = now - lastMicros;
  if (elapsed < sampleIntervalUs) return;
  float dt = elapsed / 1000000.0f;
  lastMicros = now;

  int16_t ax1, ay1, az1, gx1Raw, gy1Raw, gz1;
  int16_t ax2, ay2, az2, gx2Raw, gy2Raw, gz2;
  readMPURaw(MPU1_ADDR, ax1, ay1, az1, gx1Raw, gy1Raw, gz1);
  readMPURaw(MPU2_ADDR, ax2, ay2, az2, gx2Raw, gy2Raw, gz2);

  // Convert
  float ax1g = accelToG(ax1), ay1g = accelToG(ay1), az1g = accelToG(az1);
  float ax2g = accelToG(ax2), ay2g = accelToG(ay2), az2g = accelToG(az2);
  float gx1dps = gyroToDeg((int16_t)(gx1Raw - (int)gyroOffset1X));
  float gy1dps = gyroToDeg((int16_t)(gy1Raw - (int)gyroOffset1Y));
  float gz1dps = gyroToDeg((int16_t)(gz1 - (int)gyroOffset1Z));
  float gx2dps = gyroToDeg((int16_t)(gx2Raw - (int)gyroOffset2X));
  float gy2dps = gyroToDeg((int16_t)(gy2Raw - (int)gyroOffset2Y));
  float gz2dps = gyroToDeg((int16_t)(gz2 - (int)gyroOffset2Z));

  // Convert gyro to rad/s for filter
  const float d2r = PI / 180.0f;
  float gx1 = gx1dps * d2r, gy1 = gy1dps * d2r, gz1f = gz1dps * d2r;
  float gx2 = gx2dps * d2r, gy2 = gy2dps * d2r, gz2f = gz2dps * d2r;

  filter1.update(gx1, gy1, gz1f, ax1g, ay1g, az1g, dt);
  filter2.update(gx2, gy2, gz2f, ax2g, ay2g, az2g, dt);

  float kneeFlexion = (atan2(ay1g, az1g) - atan2(ay2g, az2g)) * 180.0f / PI; // difference in accel-based pitch as quick estimate

  // Piezo envelope-based detection
  // ADC mid for ESP32 12-bit: ~2048. Envelope smooths impact magnitude.
  static float envelope = 0.0f;
  const float alpha_env = 0.05f; // smoothing factor (tune)
  const int ADC_MID = 2048;
  const int PIEZO_THRESHOLD = 30; // tune this threshold for your mounting
  const int STANCE_HOLD_MS = 150; // hold time after a detected pulse
  static unsigned long last_pulse_ms = 0;

  int forceRaw = analogRead(FORCE_PIN);
  int delta = abs(forceRaw - ADC_MID);
  envelope = (1.0f - alpha_env) * envelope + alpha_env * (float)delta;
  bool detected = envelope > (float)PIEZO_THRESHOLD;
  if (detected) last_pulse_ms = millis();
  bool stance = (millis() - last_pulse_ms) < STANCE_HOLD_MS;

  unsigned long tms = millis();
  // Output CSV with quaternions, raw accel (g), raw gyro (dps), knee, force, stance
  Serial.print(tms); Serial.print(',');
  Serial.print(filter1.q0, 6); Serial.print(',');
  Serial.print(filter1.q1, 6); Serial.print(',');
  Serial.print(filter1.q2, 6); Serial.print(',');
  Serial.print(filter1.q3, 6); Serial.print(',');
  Serial.print(ax1g, 6); Serial.print(',');
  Serial.print(ay1g, 6); Serial.print(',');
  Serial.print(az1g, 6); Serial.print(',');
  Serial.print(gx1dps, 3); Serial.print(',');
  Serial.print(gy1dps, 3); Serial.print(',');
  Serial.print(gz1dps, 3); Serial.print(',');

  Serial.print(filter2.q0, 6); Serial.print(',');
  Serial.print(filter2.q1, 6); Serial.print(',');
  Serial.print(filter2.q2, 6); Serial.print(',');
  Serial.print(filter2.q3, 6); Serial.print(',');
  Serial.print(ax2g, 6); Serial.print(',');
  Serial.print(ay2g, 6); Serial.print(',');
  Serial.print(az2g, 6); Serial.print(',');
  Serial.print(gx2dps, 3); Serial.print(',');
  Serial.print(gy2dps, 3); Serial.print(',');
  Serial.print(gz2dps, 3); Serial.print(',');

  Serial.print(kneeFlexion, 3); Serial.print(',');
  // Output raw ADC value and computed stance (1/0)
  Serial.print(forceRaw); Serial.print(',');
  Serial.println(stance ? 1 : 0);
}
