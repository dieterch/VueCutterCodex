import tomllib
with open("config.toml", mode="rb") as fp:
    cfg = tomllib.load(fp)

print("Hello, world!")
print("cfg:", cfg)

