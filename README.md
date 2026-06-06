Gait Analysis — Seeed XIAO ESP32S3
=================================

This project reads two MPU-6050 IMUs and a force sensor to compute knee flexion and basic gait events.

Wiring
- MPU1 (thigh): SDA/SCL to board SDA/SCL, AD0 -> LOW (address 0x68)
- MPU2 (shank): SDA/SCL to board SDA/SCL, AD0 -> HIGH (address 0x69)
- Force sensor: connect analog output to ADC pin 34 (or change `FORCE_PIN` in `src/main.cpp`)
- Power: 3.3V / 5V as appropriate; ensure common GND.

Notes
- Knee angle is computed as the difference between the sagittal-plane pitch of the thigh and shank IMUs.
- Ankle angle cannot be directly computed with only two IMUs placed above the knee and above the ankle — an IMU on the foot is required for a direct ankle joint angle. This project provides an approximate shank-to-vertical angle (pitch) which can be used as a proxy during stance.
- Tuning: Thresholds and filter `alpha` should be tuned for your mounting and sampling rate.

Usage
- Build and upload with PlatformIO. Monitor serial at 115200 baud to see CSV lines:

```bash
platformio run --target upload
platformio device monitor --baud 115200
```

CSV: time_ms,thigh_pitch_deg,shank_pitch_deg,knee_flexion_deg,force_raw,stance

ROS 2 Integration
- The device outputs CSV lines over the serial port. A small ROS 2 node can read the serial stream and publish ROS topics for a 3D twin.
- I added a sample bridge at `ros/serial_bridge.py` that publishes:
	- `/imu/thigh` (sensor_msgs/Imu) — full IMU message with orientation quaternion, angular_velocity (rad/s), linear_acceleration (m/s^2)
	- `/imu/shank` (sensor_msgs/Imu)
	- `/knee_angle` (std_msgs/Float32) — knee flexion in degrees
	- `/force_raw` (std_msgs/Int32) — raw ADC force reading
	- `/stance` (std_msgs/Bool) — stance flag

Quick start (on the PC running ROS 2):

1. Install dependencies (ROS 2 and Python `pyserial`). Example for a Python environment:

```bash
pip install pyserial
```

2. Run the serial bridge (change `--port` to your serial device):

```bash
python3 ros/serial_bridge.py --port /dev/ttyUSB0 --baud 115200
```

On Windows use a COM port like `COM3`.

Note: The updated firmware runs a Madgwick filter on the ESP32 and outputs quaternions and raw gyro/accel. The bridge now forwards full `sensor_msgs/Imu` messages so you can directly visualize a 3D twin in RViz2 or other tools.

TF / RViz 3D twin
- If your Fusion360 model is exported as a URDF or you have a URDF with mesh links for `hip`, `thigh`, `shank`, you can use `tf_broadcaster.py` to drive the model.
- Start the bridge, then run the TF broadcaster:

```bash
# run bridge first to publish IMUs
python3 ros/serial_bridge.py --port <PORT> --baud 115200
# in another terminal run tf broadcaster (you can provide translation and rotation offsets)
python3 ros/tf_broadcaster.py --thigh-trans 0 -0.40 0 --shank-trans 0 -0.40 0 --thigh-rot-rpy 0 0 0 --shank-rot-rpy 0 0 0 --rate 50
```

- The TF broadcaster publishes frames `hip`, `thigh`, and `shank` and a `joint_states` topic with `knee_joint`. Adjust `--thigh-len` and `--shank-len` to fit your model's segment lengths and adjust translations/axes in `ros/tf_broadcaster.py` if needed.
