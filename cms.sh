#!/bin/bash
rm -rf cms.sh
sudo mkdir -p /www 
sudo mkdir -p /www/mysql
sudo mkdir -p /www/cms && cd /www/cms
wget https://gh.con.sh/https://raw.githubusercontent.com/magicblack/maccms_down/master/maccms10.zip
sudo unzip maccms10.zip
sudo chmod -R 777 /www
sudo docker run -it --name cms --restart=always -p 3306:3306 -v /www/mysql:/var/lib/mysql -e MYSQL_DATABASE=cms -e MYSQL_USER=cms -e MYSQL_PASSWORD=123456 -e MYSQL_ROOT_PASSWORD=123456 --network=1panel-network --ip=172.18.0.13 yobasystems/alpine-mariadb:10.11
sudo docker run -d --name film  --restart=always --user $(id -u):$(id -g) -v /www/cms:/var/www/html  -p 80:80 -e ND_LOGLEVEL=info --network=1panel-network --ip=172.18.0.12 shinsenter/phpfpm-apache:dev-php7.4 
sudo chmod -R 777 /www
cd ~
echo "Everything is ok!"
echo "Open the website: http://`hostname -I|awk '{print $1}'`"
