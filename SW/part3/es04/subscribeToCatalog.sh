#!/bin/sh
mosquitto_pub -h test.mosquitto.org -t "/tiot/19/catalog/addDevice" -m '{"deviceID":"Yun","resources":["temperature","pir","sound","actuation","lcd"],"endPoints":[{"service":"/tiot/19/Yun/temperature","type":"mqttTopic","mqttClientType":"publisher"},{"service":"/tiot/19/Yun/pir","type":"mqttTopic","mqttClientType":"publisher"},{"service":"/tiot/19/Yun/sound","type":"mqttTopic","mqttClientType":"publisher"},{"service":"/tiot/19/Yun/actuation","type":"mqttTopic","mqttClientType":"subscriber"},{"service":"/tiot/19/Yun/lcd","type":"mqttTopic","mqttClientType":"subscriber"}]}'
