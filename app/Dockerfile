FROM python:3.10-slim
WORKDIR /app
ENV PATH "$PATH:/app"
COPY requirements.txt requirements.txt
RUN apt-get update && apt-get install -y iproute2 && pip3 install -r requirements.txt
COPY . .
RUN chmod +x /app/*
