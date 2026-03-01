FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema + Node.js (para MCP servers stdio como Brave Search)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY agent/ ./agent/
COPY config/ ./config/


# Pre-descargar modelos (silero VAD, turn detector)
RUN python -m agent.main download-files

# Entrypoint
CMD ["python", "-m", "agent.main", "start"]
