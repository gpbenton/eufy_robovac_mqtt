FROM python:3.9.2-alpine3.12


# Install dependencies
RUN apk add --no-cache openssl-dev git gcc libffi-dev musl-dev rust cargo

WORKDIR /usr/src/app

RUN git clone https://github.com/gpbenton/eufy_robovac_mqtt.git

RUN cd eufy_robovac_mqtt && git submodule init && git submodule update

RUN pip install -e eufy_robovac_mqtt/eufy_robovac

RUN pip install paho-mqtt PyYAML simplejson

CMD [ "python", "eufy_robovac_mqtt/eufy_robovac_mqtt.py" ]
    


