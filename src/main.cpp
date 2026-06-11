#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>

// --- WiFi Configuration ---
const char* SSID       = "Tania";              // ← Your WiFi network name
const char* PASSWORD   = "tanidiot";                          // ← Your WiFi password
const char* SERVER_IP = "172.20.10.11";            // ← Your computer's IP (auto-detected)
const int   SERVER_PORT     = 5000;
const char* SERVER_ENDPOINT = "/log_data_csv";

// --- Leg length (metres, user-specific) ---
const float LEG_LENGTH = 0.90f;

// --- Gait state ---
float strideLength    = 0.0f;
float walkingVelocity = 0.0f;
float cadence         = 0.0f;
float strideTime      = 0.0f;
unsigned long lastHeelStrike = 0;

float maxSwingAngle = -999.0f;
float minSwingAngle =  999.0f;

float stanceTime  = 0.0f;
float swingTime   = 0.0f;
unsigned long stanceStart = 0;
bool prevStance = false;

// --- IMU I2C addresses ---
const uint8_t MPU1_ADDR = 0x68;  // thigh
const uint8_t MPU2_ADDR = 0x69;  // shank

// --- Force / piezo pin ---
const int FORCE_PIN = 4;

// --- Sampling ---
const float         sampleHz         = 100.0f;
const unsigned long sampleIntervalUs = (unsigned long)(1000000.0f / sampleHz);

// --- Gyro calibration offsets ---
float gyroOffset1X = 0, gyroOffset1Y = 0, gyroOffset1Z = 0;
float gyroOffset2X = 0, gyroOffset2Y = 0, gyroOffset2Z = 0;

// ============================================================
//  Madgwick AHRS filter
// ============================================================
class Madgwick {
public:
  float q0, q1, q2, q3;
  float beta;

  Madgwick(float beta_ = 0.1f)
    : q0(1), q1(0), q2(0), q3(0), beta(beta_) {}

  void update(float gx, float gy, float gz,
              float ax, float ay, float az, float dt) {
    float recipNorm;
    float s0, s1, s2, s3;

    float qDot0 = 0.5f * (-q1*gx - q2*gy - q3*gz);
    float qDot1 = 0.5f * ( q0*gx + q2*gz - q3*gy);
    float qDot2 = 0.5f * ( q0*gy - q1*gz + q3*gx);
    float qDot3 = 0.5f * ( q0*gz + q1*gy - q2*gx);

    recipNorm = sqrtf(ax*ax + ay*ay + az*az);
    if (recipNorm == 0.0f) return;
    recipNorm = 1.0f / recipNorm;
    ax *= recipNorm; ay *= recipNorm; az *= recipNorm;

    float _2q0=2*q0, _2q1=2*q1, _2q2=2*q2, _2q3=2*q3;
    float _4q0=4*q0, _4q1=4*q1, _4q2=4*q2;
    float _8q1=8*q1, _8q2=8*q2;
    float q0q0=q0*q0, q1q1=q1*q1, q2q2=q2*q2, q3q3=q3*q3;

    s0 = _4q0*q2q2 + _2q2*ax + _4q0*q1q1 - _2q1*ay;
    s1 = _4q1*q3q3 - _2q3*ax + 4*q0q0*q1 - _2q0*ay
         - _4q1 + _8q1*q1q1 + _8q1*q2q2 + _4q1*az;
    s2 = 4*q0q0*q2 + _2q0*ax + _4q2*q3q3 - _2q3*ay
         - _4q2 + _8q2*q1q1 + _8q2*q2q2 + _4q2*az;
    s3 = 4*q1q1*q3 - _2q1*ax + 4*q2q2*q3 - _2q2*ay;

    recipNorm = sqrtf(s0*s0 + s1*s1 + s2*s2 + s3*s3);
    if (recipNorm == 0.0f) return;
    recipNorm = 1.0f / recipNorm;
    s0 *= recipNorm; s1 *= recipNorm;
    s2 *= recipNorm; s3 *= recipNorm;

    qDot0 -= beta*s0; qDot1 -= beta*s1;
    qDot2 -= beta*s2; qDot3 -= beta*s3;

    q0 += qDot0*dt; q1 += qDot1*dt;
    q2 += qDot2*dt; q3 += qDot3*dt;

    recipNorm = sqrtf(q0*q0 + q1*q1 + q2*q2 + q3*q3);
    if (recipNorm != 0.0f) {
      recipNorm = 1.0f / recipNorm;
      q0 *= recipNorm; q1 *= recipNorm;
      q2 *= recipNorm; q3 *= recipNorm;
    }
  }
};

Madgwick filter1(0.12f), filter2(0.12f);

// ============================================================
//  I2C / MPU helpers
// ============================================================
void mpuWrite(uint8_t addr, uint8_t reg, uint8_t val) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

void mpuRead(uint8_t addr, uint8_t reg, uint8_t count, uint8_t* dest) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return;
  Wire.requestFrom((int)addr, (int)count);
  for (uint8_t i = 0; i < count; i++)
    dest[i] = Wire.available() ? Wire.read() : 0;
}

void initMPU(uint8_t addr) {
  mpuWrite(addr, 0x6B, 0x00); delay(10); // wake up
  mpuWrite(addr, 0x1B, 0x00);            // gyro  ±250 dps
  mpuWrite(addr, 0x1C, 0x00);            // accel ±2 g
}

void readMPURaw(uint8_t addr,
                int16_t& ax, int16_t& ay, int16_t& az,
                int16_t& gx, int16_t& gy, int16_t& gz) {
  uint8_t buf[14];
  mpuRead(addr, 0x3B, 14, buf);
  ax = ((int16_t)buf[0]  << 8) | buf[1];
  ay = ((int16_t)buf[2]  << 8) | buf[3];
  az = ((int16_t)buf[4]  << 8) | buf[5];
  gx = ((int16_t)buf[8]  << 8) | buf[9];
  gy = ((int16_t)buf[10] << 8) | buf[11];
  gz = ((int16_t)buf[12] << 8) | buf[13];
}

inline float accelToG(int16_t raw)  { return raw / 16384.0f; }
inline float gyroToDeg(int16_t raw) { return raw / 131.0f;   }

void calibrateGyros() {
  const int N = 200;
  long gx1=0,gy1=0,gz1=0,gx2=0,gy2=0,gz2=0;
  for (int i = 0; i < N; i++) {
    int16_t ax,ay,az,gx,gy,gz;
    readMPURaw(MPU1_ADDR, ax,ay,az,gx,gy,gz);
    gx1+=gx; gy1+=gy; gz1+=gz;
    readMPURaw(MPU2_ADDR, ax,ay,az,gx,gy,gz);
    gx2+=gx; gy2+=gy; gz2+=gz;
    delay(5);
  }
  gyroOffset1X = (float)gx1/N; gyroOffset1Y = (float)gy1/N; gyroOffset1Z = (float)gz1/N;
  gyroOffset2X = (float)gx2/N; gyroOffset2Y = (float)gy2/N; gyroOffset2Z = (float)gz2/N;
}

// ============================================================
//  Piezo baseline auto-calibration
//  Collects 100 resting samples so the envelope is anchored
//  to the actual resting ADC value (near 0, not 2048).
// ============================================================
int  baselineForce = 0;
bool baselineSet   = false;
int  calCount      = 0;
long calSum        = 0;

// Returns true once baseline is ready.
bool calibrateForceBaseline(int rawADC) {
  if (baselineSet) return true;
  calSum += rawADC;
  calCount++;
  if (calCount >= 100) {
    baselineForce = (int)(calSum / calCount);
    baselineSet   = true;
    Serial.print("Force baseline set: ");
    Serial.println(baselineForce);
  }
  return baselineSet;
}

// ============================================================
//  Non-blocking HTTP: buffer 50 rows, flush in one POST
// ============================================================
String httpBuffer      = "";
int    httpBufferCount = 0;
const int SEND_EVERY_N = 50;   // ~500 ms worth of data at 100 Hz

void flushBufferToServer() {
  if (httpBuffer.length() == 0) return;
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi down — buffer dropped");
    httpBuffer      = "";
    httpBufferCount = 0;
    return;
  }
  HTTPClient http;
  String url = "http://" + String(SERVER_IP) + ":" +
               String(SERVER_PORT) + String(SERVER_ENDPOINT);
  http.begin(url);
  http.setTimeout(500);                        // never block > 500 ms
  http.addHeader("Content-Type", "text/plain");
  int code = http.POST(httpBuffer);
  if (code == HTTP_CODE_OK || code == HTTP_CODE_CREATED) {
    Serial.print("✓ Sent "); Serial.print(httpBufferCount);
    Serial.println(" rows");
  } else {
    Serial.print("✗ HTTP "); Serial.println(code);
  }
  http.end();
  httpBuffer      = "";
  httpBufferCount = 0;
}

// ============================================================
//  Wi-Fi connect (called once at startup)
// ============================================================
void connectToWiFi() {
  Serial.print("Connecting to WiFi: "); Serial.println(SSID);
  WiFi.begin(SSID, PASSWORD);
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500); Serial.print("."); attempts++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("\nWiFi connected! IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("Sending to: http://");
    Serial.print(SERVER_IP); Serial.print(":");
    Serial.print(SERVER_PORT); Serial.println(SERVER_ENDPOINT);
  } else {
    Serial.println("\nWiFi failed — will retry every 10 s in loop");
  }
}

// ============================================================
//  setup
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println("\n>>> BOARD ALIVE <<<");

  connectToWiFi();

  Wire.begin();
  Wire.setClock(100000);
  delay(100);

  // I2C scan
  Serial.println("=== I2C Scan ===");
  for (byte i = 8; i < 120; i++) {
    Wire.beginTransmission(i);
    if (Wire.endTransmission() == 0) {
      Serial.print("Found 0x"); Serial.println(i, HEX);
    }
  }
  Serial.println("Expected: 0x68 (thigh MPU), 0x69 (shank MPU)");

  initMPU(MPU1_ADDR); delay(50);
  initMPU(MPU2_ADDR); delay(50);

  Serial.println("Calibrating gyros — keep device still...");
  calibrateGyros();
  Serial.println("Gyro calibration done.");
  Serial.println("Collecting force baseline — keep foot still...");

  // CSV header
  Serial.println(
    "time_ms,"
    "th_qw,th_qx,th_qy,th_qz,"
    "th_ax_g,th_ay_g,th_az_g,"
    "th_gx_dps,th_gy_dps,th_gz_dps,"
    "sh_qw,sh_qx,sh_qy,sh_qz,"
    "sh_ax_g,sh_ay_g,sh_az_g,"
    "sh_gx_dps,sh_gy_dps,sh_gz_dps,"
    "knee_deg,force_raw,stance,"
    "stride_length_m,velocity_mps,cadence_spm,"
    "stance_time_s,swing_time_s");
}

// ============================================================
//  loop
// ============================================================
void loop() {

  // ── 100 Hz timing gate ────────────────────────────────────
  static unsigned long lastMicros = micros();
  unsigned long now = micros();
  if (now - lastMicros < sampleIntervalUs) return;
  float dt = (now - lastMicros) / 1000000.0f;
  lastMicros = now;

  // ── Read both IMUs ────────────────────────────────────────
  int16_t ax1,ay1,az1,gx1r,gy1r,gz1r;
  int16_t ax2,ay2,az2,gx2r,gy2r,gz2r;
  readMPURaw(MPU1_ADDR, ax1,ay1,az1,gx1r,gy1r,gz1r);
  readMPURaw(MPU2_ADDR, ax2,ay2,az2,gx2r,gy2r,gz2r);

  float ax1g = accelToG(ax1), ay1g = accelToG(ay1), az1g = accelToG(az1);
  float ax2g = accelToG(ax2), ay2g = accelToG(ay2), az2g = accelToG(az2);

  float gx1dps = gyroToDeg((int16_t)(gx1r - (int)gyroOffset1X));
  float gy1dps = gyroToDeg((int16_t)(gy1r - (int)gyroOffset1Y));
  float gz1dps = gyroToDeg((int16_t)(gz1r - (int)gyroOffset1Z));
  float gx2dps = gyroToDeg((int16_t)(gx2r - (int)gyroOffset2X));
  float gy2dps = gyroToDeg((int16_t)(gy2r - (int)gyroOffset2Y));
  float gz2dps = gyroToDeg((int16_t)(gz2r - (int)gyroOffset2Z));

  const float d2r = PI / 180.0f;
  filter1.update(gx1dps*d2r, gy1dps*d2r, gz1dps*d2r, ax1g, ay1g, az1g, dt);
  filter2.update(gx2dps*d2r, gy2dps*d2r, gz2dps*d2r, ax2g, ay2g, az2g, dt);

  float kneeFlexion = (atan2f(ay1g, az1g) - atan2f(ay2g, az2g)) * 180.0f / PI;

  // ── Piezo / force reading ─────────────────────────────────
  int forceRaw = analogRead(FORCE_PIN);

  // Wait until baseline is collected (first 100 samples)
  if (!calibrateForceBaseline(forceRaw)) return;

  // Envelope: smoothed deviation above resting baseline
  static float envelope         = 0.0f;
  static unsigned long last_pulse_ms = 0;
  static bool prevDetected      = false;

  // PIEZO_THRESHOLD: raise if stance flickers on noise,
  // lower if real steps are missed. Watch env= in serial output.
  const float ALPHA_ENV       = 0.05f;
  const int PIEZO_THRESHOLD = 8;  // ADC counts above baseline
  const int   STANCE_HOLD_MS  = 150;  // ms to hold stance after last pulse

  int delta = abs(forceRaw - baselineForce);
  envelope  = (1.0f - ALPHA_ENV) * envelope + ALPHA_ENV * (float)delta;

  bool detected = (envelope > (float)PIEZO_THRESHOLD);
  if (detected) last_pulse_ms = millis();
  bool stance = (millis() - last_pulse_ms) < STANCE_HOLD_MS;

  // Rising edge → heel strike event
  bool heelStrike = detected && !prevDetected;
  prevDetected = detected;

  // Track ankle swing range for stride-length estimate
  float ankleAngle = atan2f(ay2g, az2g) * 180.0f / PI;
  if (ankleAngle > maxSwingAngle) maxSwingAngle = ankleAngle;
  if (ankleAngle < minSwingAngle) minSwingAngle = ankleAngle;

  // ── Gait calculations on heel strike ─────────────────────
  if (heelStrike) {
    unsigned long nowHS = millis();
    if (lastHeelStrike != 0) {
      strideTime      = (nowHS - lastHeelStrike) / 1000.0f;
      cadence         = 60.0f / strideTime;
      float swingRange = maxSwingAngle - minSwingAngle;
      float theta      = swingRange * d2r;
      strideLength     = 2.0f * LEG_LENGTH * sinf(theta / 2.0f);
      walkingVelocity  = strideLength / strideTime;
    }
    lastHeelStrike = nowHS;
    maxSwingAngle  = -999.0f;
    minSwingAngle  =  999.0f;
  }

  // ── Stance / swing time tracking ─────────────────────────
  if ( stance && !prevStance) stanceStart = millis();
  if (!stance &&  prevStance) stanceTime  = (millis() - stanceStart) / 1000.0f;
  prevStance = stance;
  if (strideTime > 0) swingTime = strideTime - stanceTime;

  unsigned long tms = millis();

  // ── Build CSV row ─────────────────────────────────────────
  String row = "";
  row += tms;                         row += ',';
  row += String(filter1.q0, 6);       row += ',';
  row += String(filter1.q1, 6);       row += ',';
  row += String(filter1.q2, 6);       row += ',';
  row += String(filter1.q3, 6);       row += ',';
  row += String(ax1g, 6);             row += ',';
  row += String(ay1g, 6);             row += ',';
  row += String(az1g, 6);             row += ',';
  row += String(gx1dps, 3);           row += ',';
  row += String(gy1dps, 3);           row += ',';
  row += String(gz1dps, 3);           row += ',';
  row += String(filter2.q0, 6);       row += ',';
  row += String(filter2.q1, 6);       row += ',';
  row += String(filter2.q2, 6);       row += ',';
  row += String(filter2.q3, 6);       row += ',';
  row += String(ax2g, 6);             row += ',';
  row += String(ay2g, 6);             row += ',';
  row += String(az2g, 6);             row += ',';
  row += String(gx2dps, 3);           row += ',';
  row += String(gy2dps, 3);           row += ',';
  row += String(gz2dps, 3);           row += ',';
  row += String(kneeFlexion, 3);      row += ',';
  row += forceRaw;                    row += ',';
  row += (stance ? 1 : 0);           row += ',';
  row += String(strideLength, 3);     row += ',';
  row += String(walkingVelocity, 3);  row += ',';
  row += String(cadence, 1);          row += ',';
  row += String(stanceTime, 3);       row += ',';
  row += String(swingTime, 3);

  // ── Serial output ─────────────────────────────────────────
  Serial.println(row);
  Serial.print("  [GAIT] knee=");   Serial.print(kneeFlexion, 2);
  Serial.print("° force=");          Serial.print(forceRaw);
  Serial.print(" env=");             Serial.print(envelope, 1);
  Serial.print(" base=");            Serial.print(baselineForce);
  Serial.print(" stance=");          Serial.print(stance ? "YES" : "NO ");
  Serial.print(" stride=");          Serial.print(strideLength, 3);
  Serial.print("m vel=");            Serial.print(walkingVelocity, 3);
  Serial.print("m/s cad=");          Serial.print(cadence, 1);
  Serial.print("spm st=");           Serial.print(stanceTime, 3);
  Serial.print("s sw=");             Serial.println(swingTime, 3);
  Serial.println("---");

  // ── Buffer rows; flush every 50 samples (~500 ms) ─────────
  httpBuffer += row + "\n";
  httpBufferCount++;
  if (httpBufferCount >= SEND_EVERY_N) {
    flushBufferToServer();
  }

  // ── Wi-Fi watchdog: retry every 10 s if disconnected ──────
  static unsigned long lastWifiCheck = 0;
  if (millis() - lastWifiCheck > 10000) {
    lastWifiCheck = millis();
    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("WiFi lost — reconnecting...");
      WiFi.disconnect();
      delay(100);
      WiFi.begin(SSID, PASSWORD);
    }
  }
}
