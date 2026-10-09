
"""Sentinel-X : detection de personnes ESP32-CAM et alertes MQTT."""

import json
import os
import time

import cv2
import paho.mqtt.client as mqtt
from ultralytics import YOLO


# =========================
# CONFIGURATION CAMERA
# =========================

USE_WEBCAM = False
WEBCAM_INDEX = 1
STREAM_URL = "http://10.246.140.66:81/stream"

WINDOW_NAME = "Sentinel-X - ESP32-CAM (Q pour quitter)"


# =========================
# CONFIGURATION YOLO
# =========================

MODEL_PATH = "yolo11n.pt"
CONFIDENCE_THRESHOLD = 0.5
IMAGE_SIZE = 320
PERSON_CLASS_ID = 0

# Intervalle minimum entre deux analyses YOLO.
DETECTION_INTERVAL = 0.15


# =========================
# CONFIGURATION MQTT
# =========================

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "api")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_CA_CERT = os.getenv("MQTT_CA_CERT")

MQTT_TOPIC = "sentinel/alerts"

MQTT_ALERT = {
    "code": "HUMAN_DETECTED",
    "source": "yolo",
    "severity": "critical",
    "message": "Personne detectee",
}


def on_mqtt_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("MQTT : connexion reussie.")
    else:
        print(f"MQTT : connexion refusee ({reason_code}).")


def on_mqtt_connect_fail(client, userdata):
    print("MQTT : broker indisponible, nouvelle tentative.")


def on_mqtt_publish(client, userdata, mid, reason_code, properties):
    if reason_code.is_failure:
        print(f"MQTT : publication refusee ({reason_code}).")
    else:
        print(f"MQTT : alerte publiee sur {MQTT_TOPIC}.")


def start_mqtt():
    client = None

    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

        # Authentification facultative pour le broker local.
        if MQTT_PASSWORD:
            client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

        # TLS pour le broker securise.
        if MQTT_PORT == 8883:
            client.tls_set(ca_certs=MQTT_CA_CERT)

        client.on_connect = on_mqtt_connect
        client.on_connect_fail = on_mqtt_connect_fail
        client.on_publish = on_mqtt_publish

        client.reconnect_delay_set(min_delay=1, max_delay=30)
        client.max_queued_messages_set(10)

        client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
        client.loop_start()

        print(f"MQTT : connexion vers {MQTT_HOST}:{MQTT_PORT}...")

        return client

    except Exception as error:
        print(f"MQTT indisponible : {error}")

        if client is not None:
            try:
                client.loop_stop()
            except Exception:
                pass

        return None


def publish_intrusion(client):
    if client is None or not client.is_connected():
        print("ALERTE INTRUSION : MQTT non connecte.")
        return

    try:
        result = client.publish(
            MQTT_TOPIC,
            json.dumps(MQTT_ALERT),
            qos=1,
            retain=False,
        )

        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"MQTT : erreur publication ({result.rc}).")

    except Exception as error:
        print(f"MQTT : erreur {error}")


def detect_people(model, frame):
    """Detecte les personnes et annote l'image."""

    results = model.predict(
        source=frame,
        classes=[PERSON_CLASS_ID],
        conf=CONFIDENCE_THRESHOLD,
        imgsz=IMAGE_SIZE,
        verbose=False,
    )

    detected = False

    for result in results:
        if result.boxes is None:
            continue

        for detected_box in result.boxes:
            detected = True

            x1, y1, x2, y2 = map(
                int, detected_box.xyxy[0].tolist()
            )
            confidence = float(detected_box.conf[0])

            cv2.rectangle(
                frame,
                (x1, y1),
                (x2, y2),
                (0, 255, 0),
                2,
            )

            cv2.putText(
                frame,
                f"Personne {confidence:.0%}",
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 255, 0),
                2,
            )

    if detected:
        cv2.putText(
            frame,
            "ALERTE INTRUSION",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2,
        )

    return detected, frame


def open_camera():
    """Ouvre la webcam ou le flux ESP32-CAM."""

    if USE_WEBCAM:
        return cv2.VideoCapture(WEBCAM_INDEX, cv2.CAP_DSHOW)

    return cv2.VideoCapture(
        STREAM_URL,
        cv2.CAP_FFMPEG,
        [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000,
        ],
    )


def main():
    print("Demarrage Sentinel-X...")
    print(f"Chargement YOLO : {MODEL_PATH}")

    model = YOLO(MODEL_PATH)

    source = WEBCAM_INDEX if USE_WEBCAM else STREAM_URL
    print(f"Connexion camera : {source}")

    capture = open_camera()

    if not capture.isOpened():
        raise RuntimeError(
            "Impossible d'ouvrir la camera. "
            "Verifier Wi-Fi et STREAM_URL."
        )

    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    mqtt_client = None

    try:
        mqtt_client = start_mqtt()

        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, 800, 600)

        previous_detection = False
        last_detection_time = 0.0
        last_annotated_frame = None

        print("Camera connectee. Appuyer sur Q pour quitter.")

        while True:
            success, frame = capture.read()

            if not success:
                print("Flux interrompu, tentative de reconnexion...")
                capture.release()
                time.sleep(2)

                capture = open_camera()

                if not capture.isOpened():
                    print("Camera toujours indisponible.")
                    break

                previous_detection = False
                last_annotated_frame = None
                continue

            now = time.monotonic()

            if now - last_detection_time >= DETECTION_INTERVAL:
                detected, annotated_frame = detect_people(
                    model, frame.copy()
                )

                if detected and not previous_detection:
                    print("ALERTE : personne detectee !")
                    publish_intrusion(mqtt_client)

                previous_detection = detected
                last_detection_time = now
                last_annotated_frame = annotated_frame

            # Affiche l'image avec les annotations les plus recentes.
            display_frame = frame

            if last_annotated_frame is not None:
                if now - last_detection_time < 0.1:
                    display_frame = last_annotated_frame

            cv2.imshow(WINDOW_NAME, display_frame)

            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                break

            if cv2.getWindowProperty(
                WINDOW_NAME, cv2.WND_PROP_VISIBLE
            ) < 1:
                break

    finally:
        capture.release()
        cv2.destroyAllWindows()

        if mqtt_client is not None:
            mqtt_client.disconnect()
            mqtt_client.loop_stop()

        print("Sentinel-X arrete.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, cv2.error) as error:
        print(f"Erreur : {error}")
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("Arret demande.")
