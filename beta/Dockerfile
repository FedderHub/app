FROM python:3.11-slim

WORKDIR /app

COPY beta/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY beta/ml /app/ml
COPY beta/grpc_weight_sender.py /app/grpc_weight_sender.py
COPY gama/phase2 /app/gama/phase2

ENTRYPOINT ["python", "/app/ml/train.py"]
