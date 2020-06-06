# User class

class User:
    def __init__(self, userID, name, surname, email):
        self.userID = userID
        self.name = name
        self.surname = surname
        self.email = email

    def serialize(self) -> dict:
        # Serializes the current User object and returns a dict representing the same entity
        return {"userID": self.userID, "name": self.name, "surname": self.surname, "email": self.email}

    @staticmethod
    def parseUser(userDesc: dict):
        # Check if every field is present, otherwise raise an exception
        if "userID" not in userDesc or "name" not in userDesc or "surname" not in userDesc or "email" not in userDesc:
            raise ValueError("JSON doesn't contain necessary params")

        u = User(userDesc["userID"], userDesc["name"], userDesc["surname"], userDesc["email"])
        
        return u