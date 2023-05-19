FROM ghcr.io/flant/shell-operator:latest
RUN apk add --no-cache python3 py3-pip && pip3 install requests kubernetes
ADD hooks /hooks