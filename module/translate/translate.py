import os
import gettext


class Translate:
    _instance = None

    def __new__(cls, init_locale=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.translations = {}
            cls._instance.current_locale = None
            cls._instance.init_translations(init_locale)
        return cls._instance

    def init_translations(self, init_locale=None):
        # locales_dir = os.path.join(os.path.dirname(__file__), 'locales')
        locales_dir = './assets/locales'
        locales = os.listdir(locales_dir)
        for locale in locales:
            if os.path.isdir(os.path.join(locales_dir, locale)):
                translation = gettext.translation('messages', localedir=locales_dir, languages=[locale])
                self.translations[locale] = translation
        if init_locale:
            self.set_locale(init_locale)

    def set_locale(self, locale):
        if locale in self.translations:
            self.current_locale = locale
            self.translations[locale].install()

    def get_translation(self):
        if self.current_locale:
            return self.translations[self.current_locale]
        return None

    def gettext(self, message):
        translation = self.get_translation()
        if translation:
            return translation.gettext(message)
        return message
