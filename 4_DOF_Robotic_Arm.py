import time
import pygame
import serial

# ---------------- CONFIGURATION ----------------
PORT = "COM10"         # Change to your Arduino COM port if needed
BAUD = 115200

# Controller Axis Mappings (Change these if the diagnostic screen shows numbers elsewhere)
LEFT_STICK_X = 0
RIGHT_STICK_Y = 3
LT_AXIS = 2            # Usually 2 or 4
RT_AXIS = 5            # Usually 5

MIN_ANGLE = 10
MAX_ANGLE = 170

# Gripper / Jaw Settings for Motor 4 (Pin 12)
JAW_OPEN_ANGLE = 170    # Angle when RT is released
JAW_CLOSED_ANGLE = 10   # Angle when RT is fully pressed
REVERSE_JAW = False     # Flip to True if your servo moves the wrong way

# Initial positions for Motors 1, 2, 3, and 4
DEFAULT_ANGLES = [10, 90, 10, 170]

DEADZONE = 0.08
SMOOTHING = 0.20
SEND_INTERVAL = 0.04
RECONNECT_INTERVAL = 2.0

REVERSE_RIGHT_STICK = True

arduino = None
last_angles_sent = [None] * 4
last_send_times = [0.0] * 4


# ---------------- ARDUINO CONNECTION ----------------

def connect_arduino():
    global arduino, last_angles_sent
    try:
        device = serial.Serial(PORT, BAUD, timeout=0, write_timeout=1)
        time.sleep(2)
        device.reset_input_buffer()
        arduino = device
        last_angles_sent = [None] * 4
        print(f"Arduino connected successfully on {PORT}")
        return True
    except (serial.SerialException, OSError) as error:
        arduino = None
        print("Arduino connection failed:", error)
        return False


def disconnect_arduino():
    global arduino, last_angles_sent
    device = arduino
    arduino = None
    last_angles_sent = [None] * 4
    if device is not None:
        try:
            device.close()
        except (serial.SerialException, OSError):
            pass


# ---------------- SEND ANGLES ----------------

def send_angle(motor, angle):
    global last_angles_sent, last_send_times
    if arduino is None:
        return

    index = motor - 1
    now = time.monotonic()

    if angle == last_angles_sent[index]:
        return

    if now - last_send_times[index] < SEND_INTERVAL:
        return

    try:
        command = f"{motor},{angle}\n"
        arduino.write(command.encode("ascii"))
        last_angles_sent[index] = angle
        last_send_times[index] = now
    except (serial.SerialException, OSError) as error:
        print("Serial write failed:", error)
        disconnect_arduino()


# ---------------- CONTROLLER MAPPINGS ----------------

def stick_to_angle(value, reverse=False):
    if reverse:
        value = -value
    value = max(-1.0, min(1.0, value))
    if abs(value) < DEADZONE:
        value = 0.0
    else:
        sign = 1 if value > 0 else -1
        value = sign * ((abs(value) - DEADZONE) / (1.0 - DEADZONE))

    return round(MIN_ANGLE + ((value + 1.0) / 2.0) * (MAX_ANGLE - MIN_ANGLE))


def jaw_control(controller, axis_number, reverse=False):
    """
    Safely reads RT trigger. Automatically handles both 
    -1 to 1 triggers (XInput) and 0 to 1 triggers.
    """
    if axis_number >= controller.get_numaxes():
        return JAW_OPEN_ANGLE

    raw_val = controller.get_axis(axis_number)
    
    # Normalize: if raw_val is between -1 and 1, convert to 0 to 1.
    # If your controller natively outputs 0 to 1, this handles it smoothly too.
    val = (raw_val + 1.0) / 2.0 if raw_val < 0.5 and raw_val > -1.1 else raw_val
    val = max(0.0, min(1.0, val))

    if reverse:
        val = 1.0 - val

    angle = JAW_OPEN_ANGLE + val * (JAW_CLOSED_ANGLE - JAW_OPEN_ANGLE)
    return round(angle), raw_val


# ---------------- DISPLAY & DIAGNOSTICS ----------------

def draw_status(screen, font, clock, angles, connected, controller):
    screen.fill((24, 28, 40))

    # Collect all axes for live diagnostic view
    axis_texts = []
    for i in range(min(controller.get_numaxes(), 6)):
        axis_texts.append(f"A{i}:{controller.get_axis(i):+.2f}")
    axes_str = " | ".join(axis_texts)

    lines = [
        "ROBOTIC ARM DIAGNOSTIC & CONTROL",
        "Arduino: " + ("CONNECTED" if connected else "DISCONNECTED (Retrying...)"),
        f"Motor 1 (Pin 9)  [Left X]    -> {angles[0]} deg",
        f"Motor 2 (Pin 10) [Right Y]   -> {angles[1]} deg",
        f"Motor 3 (Pin 11) [LT Trigger]-> {angles[2]} deg",
        f"Motor 4 (Pin 12) [RT Jaw]    -> {angles[3]} deg",
        f"Live Axes: {axes_str}",
        "ESC = Exit Program",
    ]

    for i, line in enumerate(lines):
        color = (230, 235, 245)
        if "DISCONNECTED" in line:
            color = (255, 100, 100)
        screen.blit(font.render(line, True, color), (18, 12 + i * 30))

    pygame.display.flip()
    clock.tick(60)


# ---------------- MAIN PROGRAM ----------------

pygame.init()
pygame.joystick.init()

try:
    if pygame.joystick.get_count() == 0:
        raise RuntimeError("No Xbox/Gamepad controller detected. Plug it in and restart.")

    controller = pygame.joystick.Joystick(0)
    controller.init()

    print(f"Controller found: {controller.get_name()}")
    print(f"Total axes available: {controller.get_numaxes()}")

    screen = pygame.display.set_mode((720, 270))
    pygame.display.set_caption("Robotic Arm Control Panel")

    font = pygame.font.Font(None, 24)
    clock = pygame.time.Clock()

    angles = DEFAULT_ANGLES.copy()
    smoothed_angles = [float(a) for a in DEFAULT_ANGLES]

    connect_arduino()
    last_connect_attempt = time.monotonic()

    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        pygame.event.pump()

        # Auto-reconnect loop if Arduino is unplugged
        if arduino is None:
            now = time.monotonic()
            if now - last_connect_attempt >= RECONNECT_INTERVAL:
                last_connect_attempt = now
                connect_arduino()

        # Read axes safely
        left_x = controller.get_axis(LEFT_STICK_X) if LEFT_STICK_X < controller.get_numaxes() else 0.0
        right_y = controller.get_axis(RIGHT_STICK_Y) if RIGHT_STICK_Y < controller.get_numaxes() else 0.0
        lt_value = controller.get_axis(LT_AXIS) if LT_AXIS < controller.get_numaxes() else -1.0

        motor1_target = stick_to_angle(left_x)
        motor2_target = stick_to_angle(right_y, REVERSE_RIGHT_STICK)
        motor3_target = stick_to_angle(lt_value)
        
        # Motor 4 Jaw control via RT
        motor4_target, rt_raw = jaw_control(controller, RT_AXIS, REVERSE_JAW)

        targets = [motor1_target, motor2_target, motor3_target, motor4_target]

        # Smooth movement interpolation
        for i in range(4):
            smoothed_angles[i] += SMOOTHING * (targets[i] - smoothed_angles[i])
            angles[i] = round(smoothed_angles[i])

        # Transmit to Arduino
        for motor, angle in enumerate(angles, start=1):
            send_angle(motor, angle)

        # Refresh interface screen
        draw_status(screen, font, clock, angles, arduino is not None, controller)

finally:
    disconnect_arduino()
    pygame.quit()
    print("Program closed safely.")