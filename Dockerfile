FROM ubuntu:xenial
MAINTAINER Chris Pressland <cp@bink.com>

ADD . /usr/local/src/hermes

RUN addgroup --gid 1550 apps && \
 adduser --system --no-create-home --uid 1550 --gid 1550 apps && \
 echo "deb http://ppa.launchpad.net/nginx/stable/ubuntu xenial main" >> /etc/apt/sources.list && \
 echo "deb-src http://ppa.launchpad.net/nginx/stable/ubuntu xenial main" >> /etc/apt/sources.list && \
 apt-key adv --keyserver keyserver.ubuntu.com --recv-keys C300EE8C && \
 apt-get update && \
 apt-get -y install rsync git git-core python3 python3-pip libpq-dev libxml2-dev libxslt1-dev python3-dev nginx curl && \
 curl -L 'https://github.com/just-containers/s6-overlay/releases/download/v1.18.1.5/s6-overlay-amd64.tar.gz' -o /tmp/s6-overlay-amd64.tar.gz && \
 tar xzf /tmp/s6-overlay-amd64.tar.gz -C / && \
 sed -i -e 's/user www-data;/user apps;/g' /etc/nginx/nginx.conf && \
 rsync -a --remove-source-files /usr/local/src/hermes/docker_root/ / && \
 pip3 install --upgrade pip && \
 pip3 install uwsgi && \
 pip3 install -r /usr/local/src/hermes/requirements.txt && \
 python3 /usr/local/src/hermes/manage.py collectstatic --noinput && \
 chown apps:apps /usr/local/src -R && \
 apt-get -y remove rsync git git-core curl && \
 apt-get -y autoremove && \
 apt-get clean && \
 rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENTRYPOINT ["/init"]
