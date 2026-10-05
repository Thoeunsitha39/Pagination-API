import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from api_tool.ui.widgets.pickers import DelayPicker, StatusPicker


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


def test_status_picker_presets_and_typing():
    picker = StatusPicker()
    assert picker.currentText() == "200 OK" and picker.value() == 200
    seen = []
    picker.valueChanged.connect(seen.append)
    picker.setValue(404)
    assert picker.currentText() == "404 Not Found" and picker.value() == 404
    picker.setValue(418)  # not in the list -> typed form
    assert picker.currentText() == "418 I'm a Teapot" and picker.value() == 418
    picker.setEditText("299")
    assert picker.value() == 299 and picker.is_valid()
    picker.setEditText("abc")
    assert not picker.is_valid() and picker.value() == 299  # keeps the last valid value
    picker.setEditText("700")
    assert not picker.is_valid()
    assert seen[:3] == [404, 418, 299]


def test_delay_picker_units():
    picker = DelayPicker()
    assert picker.currentText() == "No delay" and picker.value() == 0
    picker.setValue(2000)
    assert picker.currentText() == "2 s" and picker.value() == 2000
    picker.setValue(750)
    assert picker.currentText() == "750 ms"
    for text, ms in (("1.5 s", 1500), ("300", 300), ("300ms", 300), ("2 seconds", 2000), ("none", 0)):
        picker.setEditText(text)
        assert picker.value() == ms and picker.is_valid(), text
    picker.setEditText("soon")
    assert not picker.is_valid()
    picker.setEditText("11 min")
    assert not picker.is_valid()
    assert DelayPicker(maximum=3_600_000).parse("3600 s") == 3_600_000


def test_duration_input_number_and_unit():
    from api_tool.ui.widgets.pickers import DurationInput

    d = DurationInput()
    assert d.unit.currentText() == "No delay" and d.value() == 0 and not d.number.isEnabled()
    seen = []
    d.valueChanged.connect(seen.append)
    d.unit.setCurrentIndex(d.unit.findData("s"))  # picking a unit starts at 1
    assert d.value() == 1000 and d.number.isEnabled()
    d.number.setValue(30)
    assert d.value() == 30_000
    d.unit.setCurrentIndex(d.unit.findData("min"))
    assert d.value() == 30 * 60_000
    d.setValue(2 * 86_400_000)
    assert (d.number.value(), d.unit.currentData()) == (2, "d")
    d.setValue(5_400_000)  # 90 minutes, not a whole number of hours
    assert (d.number.value(), d.unit.currentData()) == (90, "min")
    d.setValue(1500)
    assert (d.number.value(), d.unit.currentData()) == (1500, "ms")
    d.setValue(0)
    assert d.unit.currentData() == "none" and d.value() == 0
    d.unit.setCurrentIndex(d.unit.findData("h"))
    d.number.setValue(10_000)  # clamped: 7 days max
    assert d.value() == 168 * 3_600_000 and d.is_valid()
    assert seen[:3] == [1000, 30_000, 1_800_000]


def test_format_duration():
    from api_tool.ui.widgets.pickers import format_duration

    assert [format_duration(v) for v in (0, 250, 3000, 120_000, 7_200_000, 86_400_000, 172_800_000, 1500)] == [
        "immediately", "250 ms", "3 s", "2 min", "2 h", "1 day", "2 days", "1500 ms"]
