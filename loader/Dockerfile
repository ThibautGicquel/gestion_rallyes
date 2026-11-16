FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /projet

COPY requirements.txt .
RUN pip install -r requirements.txt nbconvert

COPY loader/charger.py .

CMD ["python", "charger.py"]
