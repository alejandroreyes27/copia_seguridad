FROM python:3.13-alpine 
# Establecer el directorio de trabajo
WORKDIR /app

RUN apk add --no-cache \
    build-base \
    python3-dev \
    curl-dev \
    qt5-qtbase-dev \
    qt5-qttools-dev && \
    ln -sf /usr/bin/qmake-qt5 /usr/bin/qmake

# Copiar requirements.txt e instalar dependencias
COPY requirements.txt .
RUN pip install --default-timeout=100 --no-cache-dir -r requirements.txt
# Copiar el resto del código
COPY . .
EXPOSE 8080
CMD [ "python", "run.py" ]
#CMD sh -c "gunicorn --bind 0.0.0.0:8081 --workers 4 --forwarded-allow-ips=*  wsgi:app"