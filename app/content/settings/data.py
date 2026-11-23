from app.data_settings import build_data_cards


def build(host):
    build_data_cards(host, host.card_parent)
    return host.finish("data")
