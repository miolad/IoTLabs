#es2
import requests

if __name__ == "__main__":
    while(True):
        cmd = input("Choise an option:\nm : get MQTTMessageBroker\nau : get all users\n\
u : get user with specific ID\nad : get all devices\nd : get device with specific ID\nq : quit\n")
        if cmd == 'm':
            r = requests.get('http://localhost:8080/getMQTTMessageBroker')
            print(r.json())
        elif cmd == "au":
            r = requests.get('http://localhost:8080/getUsers')
            print(r.json())
        elif cmd == "u":
            id = input('Insert the ID of the user that you want retrive:')  
            r = requests.get('http://localhost:8080/getUser?id='+id)
            print(r.json())
        elif cmd == "ad":
            r = requests.get('http://localhost:8080/getDevices')
            print(r.json())
        elif cmd == "d":
            id = input('Insert the ID of the device that you want retrive:')  
            r = requests.get('http://localhost:8080/getDevice?id='+id)
            print(r.json())
        elif cmd == "q":
            break
        else:
            print("please insert a valid command")