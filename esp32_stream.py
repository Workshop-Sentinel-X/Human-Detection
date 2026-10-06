"""Détecte les personnes sur la webcam ou l'ESP32-CAM (Q pour quitter)."""

import cv2
from ultralytics import YOLO
from ultralytics.engine.results import Results


# True pour tester la webcam du PC ; False pour utiliser l'ESP32-CAM.
USE_WEBCAM = True
WEBCAM_INDEX = 1  # Caméra actuellement utilisée ; 0 pour la première caméra.

# Remplacez cette URL par celle fournie par le firmware de votre ESP32-CAM.
STREAM_URL = "http://192.168.1.100:81/stream"
WINDOW_NAME = f"Sentinel-X - {'Webcam PC' if USE_WEBCAM else 'ESP32-CAM'} (Q pour quitter)"

MODEL_PATH = "yolo11n.pt"  # Modèle nano pré-entraîné, téléchargé au premier lancement.
CONFIDENCE_THRESHOLD = 0.5
IMAGE_SIZE = 416  # Réduire à 320 pour accélérer sur un PC moins puissant.
PERSON_CLASS_ID = 0  # Classe "person" du modèle pré-entraîné sur COCO.


def detect_people(model: YOLO, frame) -> bool:
    """Annote l'image et renvoie True si au moins une personne est détectée."""
    predictions = model.predict(
        source=frame,
        classes=[PERSON_CLASS_ID],
        conf=CONFIDENCE_THRESHOLD,
        imgsz=IMAGE_SIZE,
        verbose=False,
        stream=False,
    )
    if not isinstance(predictions, list) or not predictions:
        raise RuntimeError("YOLO n'a pas renvoyé de résultat pour cette image.")
    result = predictions[0]
    if not isinstance(result, Results):
        raise RuntimeError("Le résultat YOLO n'est pas un résultat de détection.")
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return False
    intrusion_detected = True

    if intrusion_detected:
        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            confidence = float(box.conf[0])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                frame, f"person {confidence:.0%}", (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
            )
        cv2.putText(
            frame, "ALERTE INTRUSION", (10, 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2,
        )

    return intrusion_detected


def main() -> None:
    print(f"Chargement du modèle {MODEL_PATH}...")
    model = YOLO(MODEL_PATH)
    intrusion_detected = False
    capture = cv2.VideoCapture()
    try:
        if USE_WEBCAM:
            opened = capture.open(WEBCAM_INDEX, cv2.CAP_DSHOW)
        else:
            opened = capture.open(
                STREAM_URL,
                cv2.CAP_FFMPEG,
                [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000,
                ],
            )
        if not opened:
            if USE_WEBCAM:
                raise RuntimeError(
                    "Impossible d'ouvrir la webcam. Vérifiez WEBCAM_INDEX, "
                    "les autorisations caméra de Windows et fermez les autres "
                    "applications qui utilisent la caméra."
                )
            raise RuntimeError(
                "Impossible d'ouvrir le flux. Vérifiez STREAM_URL, "
                "la connexion Wi-Fi et que l'ESP32-CAM diffuse bien la vidéo."
            )

        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        print("Flux ouvert. Appuyez sur Q dans la fenêtre vidéo pour quitter.")

        while True:
            success, frame = capture.read()
            if not success:
                raise RuntimeError("Lecture interrompue : aucune image reçue du flux.")

            intrusion_detected = detect_people(model, frame)
            cv2.imshow(WINDOW_NAME, frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                break
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, cv2.error) as error:
        print(f"Erreur : {error}")
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nArrêt demandé.")
