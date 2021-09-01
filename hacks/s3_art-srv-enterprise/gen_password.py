

DO NOT CHANGE SEED / "REPLACE_ME" IN THIS FILE. COPY THIS FUNCTION AND WORK OUTSIDE YOUR GIT WORKSPACE
OR BETTER YET, IPYTHON

def gen_password(username):
    import hashlib
    import base64
    m = hashlib.sha256()
    SUPER_SECRET_PASSWORD_SEED = REPLACE_ME
    m.update(SUPER_SECRET_PASSWORD_SEED.encode('utf-8'))
    m.update(username.encode('utf-8'))
    print(f'Username: {username}')
    print(f'Password: {base64.b64encode(m.digest()).decode("utf-8")}')