from python:alpine3.13

# Install and upgrade pip, setuptools and wheel within venv
# hadolint ignore=DL3013
RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir --upgrade setuptools && \
    python3 -m pip install --no-cache-dir --upgrade wheel

COPY requirements.txt /

RUN python3 -m pip install --no-cache-dir -r /requirements.txt

COPY src/ /opt/src

WORKDIR /opt/src

ENTRYPOINT [ "python3" ]

CMD [ "/opt/src/service.py" ]
