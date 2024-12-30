# Basis-Image für Python
FROM python:3.12.7-slim

# Arbeitsverzeichnis setzen
WORKDIR /app

# Kopiere die requirements.txt und installiere Abhängigkeiten
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Kopiere das Python-Skript in das Arbeitsverzeichnis
COPY . .

# Setze Umgebungsvariablen (diese können auch durch docker run oder compose übergeben werden)

# Führe das Skript aus
CMD ["python", "main.py"]