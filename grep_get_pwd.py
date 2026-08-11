with open('auth_hardening_service.py', 'r') as f:
    text = f.read()

print("get_password_hash count:", text.count("get_password_hash"))
