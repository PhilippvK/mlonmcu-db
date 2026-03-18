import sys
import bcrypt

assert len(sys.argv) == 2

password = sys.argv[1].encode()
hashed = bcrypt.hashpw(password, bcrypt.gensalt())
print(hashed.decode())
