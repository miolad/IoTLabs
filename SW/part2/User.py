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