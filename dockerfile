#FROM ubuntu:22.04 

# Use an official Python runtime as a base image
FROM python:3.9-alpine

# Install any needed packages specified in requirements.txt
RUN apk add --update ffmpeg

# user to not break permissions
# RUN apk add --no-cache apache2 sudo \
#     && adduser -S user -s /bin/ash -D -H -u 1000 \
#     && echo "newuser ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/newuser \
#     && chmod 0440 /etc/sudoers.d/newuser
# RUN mkdir -p /home/user
# RUN chown -R user /home/user
# USER user

ENV TZ="Etc/UTC"

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip3 install -r requirements.txt


COPY main.py /app/main.py

EXPOSE 8762

CMD python3 main.py
