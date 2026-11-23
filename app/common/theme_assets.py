"""Application icon for the current theme."""


def application_icon_path(evernight=False):
    """Keep the original March 7th icon until the Easter egg is displayed."""
    if not evernight:
        return './assets/logo/March7th.ico'
    return './assets/logo/evernight/icon.ico'
