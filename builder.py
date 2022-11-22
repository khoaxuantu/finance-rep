class Users(object):
    """ 
    .. py:class:: Users()

    An user-builder class
    
    :param str username: user's username
    :param str password: user's encrypted password
    :param num cash: Initial cash for new user (10000)
    """
    def __init__(self):
        self.cash = 10000
    
    def setUsername(self, username=None):
        self.username = username
    
    def setPw(self, pw=None):
        self.pw = pw

    def to_dict(self):
        try:
            return {
                "username": self.username,
                "password": self.pw,
                "cash": self.cash,
            }
        except:
            if self.username is None:
                raise Exception("Users.username is not defined")
            if self.pw is None:
                raise Exception("Users.password is not defined")
