"""Application icon for the current theme."""


def application_icon_path(evernight=False):
    """Keep the original March 7th icon until the Easter egg is displayed."""
    if not evernight:
        return './assets/logo/March7th.ico'
    return './assets/logo/evernight/icon.ico'


def application_name(evernight):
    return 'Evernight Assistant' if evernight else 'March7th Assistant'


def sponsor_image_path(evernight, dark):
    if evernight:
        return './assets/app/images/sponsor_evernight.webp'
    return './assets/app/images/sponsor_dark.jpg' if dark else './assets/app/images/sponsor.jpg'
