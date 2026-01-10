from PySide6.QtWidgets import QApplication
from ..common.style_sheet import StyleSheet
from qfluentwidgets import PushButton, Signal, setFont, Pivot


class PivotItem(PushButton):
    """ Pivot item """

    itemClicked = Signal(bool)

    def _postInit(self):
        self.isSelected = False
        self.setProperty('isSelected', False)
        self.clicked.connect(lambda: self.itemClicked.emit(True))

        StyleSheet.PIVOT.apply(self)
        setFont(self, 18)

    def setSelected(self, isSelected: bool):
        if self.isSelected == isSelected:
            return

        self.isSelected = isSelected
        self.setProperty('isSelected', isSelected)
        self.setStyle(QApplication.style())
        self.update()


class SettingPivot(Pivot):
    def __init__(self, parent=None):
        super().__init__(parent)

    def insertItem(self, index: int, routeKey: str, text: str, onClick=None, icon=None):
        """ insert item

        Parameters
        ----------
        index: int
            insert position

        routeKey: str
            the unique name of item

        text: str
            the text of navigation item

        onClick: callable
            the slot connected to item clicked signal

        icon: str
            the icon of navigation item
        """
        if routeKey in self.items:
            return

        item = PivotItem(text, self)
        if icon:
            item.setIcon(icon)

        self.insertWidget(index, routeKey, item, onClick)
        return item
