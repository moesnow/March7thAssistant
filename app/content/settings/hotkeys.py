from app.content.keys import build_keys


def build(host):
    build_keys(host, "hotkeys")
    return host.finish("hotkeys")
