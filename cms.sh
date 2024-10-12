#!/bin/bash
rm -rf cms.sh
mkdir -p /www 
mkdir -p /www/mysql
mkdir -p /www/cms && cd /www/cms
wget https://gh.con.sh/https://raw.githubusercontent.com/magicblack/maccms_down/master/maccms10.zip
unzip maccms10.zip
chmod -R 777 /www/cms
docker stop cms >/dev/null 2>&1
docker rm cms >/dev/null 2>&1
docker network create --subnet 172.19.0.0/16 --gateway 172.19.1.1 --driver bridge film_network
docker run -d --name film  --restart=always --user $(id -u):$(id -g) -v /www/cms:/var/www/html  -p 80:80 -e ND_LOGLEVEL=info --network=film_network --ip=172.19.0.2 shinsenter/phpfpm-apache:dev-php7.4 
docker run -it --name cms --restart=always -p 3306:3306 -v /www/mysql:/var/lib/mysql -e MYSQL_DATABASE=cms -e MYSQL_USER=cms -e MYSQL_PASSWORD=123456 -e MYSQL_ROOT_PASSWORD=123456 --network=film_network --ip=172.19.0.3 yobasystems/alpine-mariadb:10.11
chmod -R 777 /www
cd ~
echo "Everything is ok!"
echo "Open the website: http://`hostname -I|awk '{print $1}'`"
