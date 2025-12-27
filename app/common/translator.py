# coding: utf-8
from PyQt5.QtCore import QObject


class Translator(QObject):

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.text = 'Text'
        self.view = 'View'
        self.menus = 'Menus & toolbars'
        self.icons = 'Icons'
        self.layout = 'Layout'
        self.dialogs = 'Dialogs & flyouts'
        self.scroll = 'Scrolling'
        self.material = 'Material'
        self.dateTime = 'Date & time'
        self.navigation = 'Navigation'
        self.basicInput = 'Basic input'
        self.statusInfo = 'Status & info'