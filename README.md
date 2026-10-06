# Sentinel-X — détection de personnes

Le script analyse chaque image de la webcam du PC ou du flux ESP32-CAM avec
Ultralytics YOLO11n, un modèle nano pré-entraîné. Seule la classe `person` est
retenue : chaque personne reçoit une boîte verte avec sa confiance, et
`ALERTE INTRUSION` s'affiche en rouge si au moins une personne est détectée.
La variable booléenne `intrusion_detected` dans la boucle principale est
actualisée à chaque image : `True` avec une personne, `False` sinon.

## Préparation (PowerShell, Python 3.12)

Depuis le dossier du projet :

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Si `.venv` existe déjà, exécuter uniquement la commande d'installation.
Ultralytics installe automatiquement ses dépendances, dont PyTorch.
Le premier lancement télécharge `yolo11n.pt` et nécessite Internet.
Les lancements suivants réutilisent ce fichier local.

## Test

Pour tester d'abord la webcam du PC, laisser `USE_WEBCAM = True` dans
`esp32_stream.py` puis lancer la commande ci-dessous. `WEBCAM_INDEX = 0`
sélectionne la première caméra ; essayer `1` si nécessaire.

Pour passer ensuite à l'ESP32-CAM :

1. Connecter le PC et l'ESP32-CAM à un réseau permettant leur communication.
2. Mettre `USE_WEBCAM = False` et modifier `STREAM_URL` dans `esp32_stream.py` avec l'URL du flux fournie par l'équipe.
   `http://192.168.1.100:81/stream` est un exemple : l'adresse, le port et le chemin
   dépendent du firmware de l'ESP32-CAM.
3. Lancer depuis le dossier du projet :

```powershell
.\.venv\Scripts\python.exe .\esp32_stream.py
```

Cliquer dans la fenêtre vidéo puis appuyer sur **Q** pour quitter.
En cas de coupure du flux, le script affiche une erreur et libère la caméra.
Les lectures réseau ont un délai maximal de 5 secondes ; une coupure peut donc
retarder la réponse à Q jusqu'à la fin de la lecture en cours.

Dans VS Code, sélectionner `.venv\Scripts\python.exe` via **Python: Select Interpreter**.
L'activation de l'environnement n'est pas nécessaire avec les commandes ci-dessus.

## Réglages IA

- `CONFIDENCE_THRESHOLD = 0.5` : seuil minimal pour retenir une personne.
- `IMAGE_SIZE = 416` : résolution d'analyse ; essayer `320` pour accélérer,
  ou `640` pour mieux repérer les petites personnes, au prix de plus de calcul.
- `MODEL_PATH = "yolo11n.pt"` : modèle utilisé.

La cadence dépend du PC et du flux : chaque image lue est analysée, sans saut
volontaire d'images. L'alerte correspond à la présence d'une personne, sans
distinction entre membre de l'équipe et intrus.
