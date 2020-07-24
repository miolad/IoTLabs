#!/bin/sh
mosquitto_pub -h test.mosquitto.org -t "/tiot/19/catalog/addDevice" -m '{"deviceID":"Yun","resources":["timeUpdate", "alarmTrigger"],"endPoints":[{"service":"/tiot/19/Yun/timeUpdate","type":"mqttTopic","mqttClientType":"subscriber"},{"service":"/tiot/19/Yun/alarmTrigger","type":"mqttTopic","mqttClientType":"subscriber"}]}'
