"""UI regression without reading private data or running real batches."""
import pytest
from pathlib import Path
import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QComboBox, QListView, QScrollArea
from tools.notice_builder.ui import MainWindow
from tools.notice_builder.presentation import COLORS


@pytest.fixture(scope='module')
def app():
    app=QApplication.instance() or QApplication(['notice-ui-test', '-platform', 'offscreen'])
    for name in ('segoeui.ttf','segoeuib.ttf','seguisym.ttf'):
        QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name))
    return app


@pytest.fixture
def window(app, monkeypatch, tmp_path):
    monkeypatch.setenv('APPDATA', str(tmp_path))
    palette = app.palette()
    window = MainWindow(); window.show(); app.processEvents()
    assert app.palette() == palette
    yield window
    window.close(); window.deleteLater(); app.processEvents()


def test_notice_mapping_popup_keeps_models_and_data(window,app):
    data={key:'' for key in window.mapping}
    window.columns_ready({'source':'synthetic.xlsx','sheet':'Data','rows':10,'columns':8,
        'header_row':1,'depth':1,'suggestions':data,'headers':{'A':'Tên hộ','B':'Giấy tờ nhân thân'}})
    window.steps.setCurrentRow(2); app.processEvents()
    for combo in window.findChildren(QComboBox):
        assert isinstance(combo.view(), QListView)
        assert combo.view().model() is combo.model()
        selected=combo.currentIndex(); combo.showPopup(); app.processEvents()
        assert combo.view().palette().color(QPalette.Base).name()=='#ffffff'
        combo.hidePopup(); assert combo.currentIndex()==selected
    owner=window.mapping['owner']; owner.setFocus(); QTest.keyClick(owner,Qt.Key_Down)
    assert owner.currentData()=='A'
    owner.setCurrentIndex(owner.findData('B'))
    assert owner.currentData()=='B' and not window.confirm_button.isEnabled()


@pytest.mark.parametrize('size',[(1000,650),(1250,830),(1600,1000)])
def test_notice_steps_and_form_controls_are_reachable(window,app,size):
    window.resize(*size)
    assert window.stack.count()==window.steps.count()==8
    for index in range(8):
        window.steps.setCurrentRow(index)
        for _ in range(3): app.processEvents()
        assert window.stack.currentIndex()==index
        page=window.pages[index]
        assert page.isVisible()
        for scroll in window.findChildren(QScrollArea):
            if scroll.isVisible(): assert scroll.horizontalScrollBar().maximum()==0, (size,index,scroll.widget().minimumSizeHint(),scroll.viewport().size())
        if index==2:
            scroll=window.stack.currentWidget()
            for field in window.mapping.values():
                scroll.ensureWidgetVisible(field); field.setFocus(); app.processEvents()
                assert field.height()>=40 and field.width()>=180
                assert not field.visibleRegion().isEmpty()
    window.steps.setFocus(); window.steps.setCurrentRow(0)
    QTest.keyClick(window.steps,Qt.Key_Down)
    assert window.steps.currentRow()==1 and window.stack.currentIndex()==1


def test_notice_workflow_gates_and_values_not_changed_by_navigation(window,app):
    window.inputs['commune_code'].setText('10930')
    window.number_mode.setCurrentIndex(window.number_mode.findData('list'))
    window.number_list.setText('1,3,5-13')
    window.continue_check.setChecked(True)
    window.continue_number.setValue(15)
    for index in range(8): window.steps.setCurrentRow(index)
    assert window.inputs['commune_code'].text()=='10930'
    assert window.number_mode.currentData()=='list' and window.number_list.text()=='1,3,5-13'
    assert window.continue_number.value()==15 and window.continue_number.isEnabled()
    assert not window.start_number.isEnabled()
    assert not window.open_preview_button.isEnabled() and not window.confirm_button.isEnabled()
    assert window.job is None and window.inspection is None and window.preview_result is None


def test_notice_number_list_continues_automatically(window, app):
    window.number_mode.setCurrentIndex(window.number_mode.findData('list'))
    window.number_list.setText('300-400')
    app.processEvents()

    assert window.continue_check.isChecked()
    assert window.continue_number.value() == 401
    assert window.continue_number.isEnabled()


def test_notice_color_pairs_have_readable_contrast():
    def luminance(value):
        rgb=[int(value[i:i+2],16)/255 for i in (1,3,5)]
        return sum((c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4)*w for c,w in zip(rgb,(.2126,.7152,.0722)))
    for foreground,background in ((COLORS['text'],COLORS['surface']),
        (COLORS['muted'],COLORS['tint']),(COLORS['primary'],COLORS['tint']),('#FFFFFF',COLORS['primary'])):
        a,b=sorted((luminance(foreground),luminance(background)))
        assert (b+.05)/(a+.05)>=4.5
