FROM python:3.6-alpine3.9

WORKDIR /ftp
ADD . .
ENTRYPOINT ["CMD-SHELL", "python", "main.py"]
