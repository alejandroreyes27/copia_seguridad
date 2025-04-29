FROM python:3.13-alpine 
# Establecer el directorio de trabajo
WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \         # gcc, make, etc.
      python3-dev \             # cabeceras de Python para extensiones C
      libcurl4-openssl-dev \    # curl-config y cabeceras de libcurl
 && rm -rf /var/lib/apt/lists/*
 
# Copiar requirements.txt e instalar dependencias
COPY requirements.txt .
RUN pip install --default-timeout=100 --no-cache-dir -r requirements.txt
# Copiar el resto del código
COPY . .
EXPOSE 5000
CMD [ "python", "run.py" ]
#CMD sh -c "gunicorn --bind 0.0.0.0:8081 --workers 4 --forwarded-allow-ips=*  wsgi:app"