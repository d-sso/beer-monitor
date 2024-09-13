FROM python:3.9

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt
RUN pip install requests

COPY ./MQTTRead.py /code/MQTTRead.py
COPY ./secrets.py /code/secrets.py

CMD ["python", "/code/MQTTRead.py"]