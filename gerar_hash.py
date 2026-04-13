import hashlib

senha = input("Digite a senha: ").strip()
print(hashlib.sha256(senha.encode("utf-8")).hexdigest())