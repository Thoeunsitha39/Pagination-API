from typing import TYPE_CHECKING

# The mixins are only ever combined into ApiTool(..., QMainWindow). Telling the type
# checker that lets it accept `self` as a Qt parent and resolve Qt methods on `self`;
# at runtime the base is plain object, so the class hierarchy is unchanged.
if TYPE_CHECKING:
    from PySide6.QtWidgets import QMainWindow as MixinBase
else:
    MixinBase = object
