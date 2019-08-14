FROM alpine:latest
RUN apk add --no-cache --update python3 && pip3 install --upgrade pip setuptools

COPY requirements.txt /bot/
RUN pip3 install --no-cache-dir -r /bot/requirements.txt

COPY ./slumometer /bot/slumometer
WORKDIR /bot/

ENV PYTHONPATH=/bot/
ENTRYPOINT ["python3", "./slumometer/bot.py"]
