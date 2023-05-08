FROM ghcr.io/flant/shell-operator:latest
RUN apk add --no-cache curl
ADD hooks /hooks