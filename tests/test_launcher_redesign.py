"""UI-only regression: presentation must not change any tool routing or state."""
from pathlib import Path
from unittest.mock import patch
import os
import pytest
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QPalette, QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton
from launcher import ToolLauncher
from launcher_ui.help_page import guide_sources,guide_html
from launcher_ui.theme import COLORS, RADIUS, SPACING, STYLE, TYPOGRAPHY


@pytest.fixture(scope="module")
def app(): return QApplication.instance() or QApplication(["launcher-ui-test","-platform","offscreen"])


@pytest.fixture
def hub(app,tmp_path,monkeypatch):
    monkeypatch.setenv("APPDATA",str(tmp_path)); window=ToolLauncher(); window.show(); app.processEvents()
    yield window
    for tool in window.open_tools: tool.close()
    window.close(); window.deleteLater(); app.processEvents()


def test_shared_design_tokens_are_complete_and_resolved():
    assert {"canvas", "surface", "surface_elevated", "primary", "secondary", "success", "warning", "error", "text", "muted", "border"} <= COLORS.keys()
    assert tuple(SPACING) == ("xs", "sm", "md", "lg", "xl")
    assert {"display", "heading", "body", "caption", "monospace"} <= TYPOGRAPHY.keys()
    assert tuple(RADIUS) == ("small", "medium", "large")
    assert "@" not in STYLE


def test_guides_complete_and_read_inside_app(hub,app):
    view=hub.launcher_view
    with patch("PySide6.QtGui.QDesktopServices.openUrl") as external:
        hub.open_help(); app.processEvents()
        assert view.pages.currentIndex()==1 and view.nav_buttons["help"].isChecked()
        assert not external.called
    for index,(_,path) in enumerate(guide_sources()):
        view.help_page.contents.setCurrentRow(index)
        actual=" ".join(view.help_page.browser.toPlainText().split())
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line=line.strip()
            if line and not set(line)<={"=","-"}: assert " ".join(line.split()) in actual,line
    assert view.help_page.contents.count()==3
    assert view.help_page.documents.count()==3
    assert view.help_page.contents.item(0).text()=="Quy trình hiện hành"


def test_help_pages_have_independent_documents_scroll_and_search(hub,app):
    hub.open_help(); page=hub.launcher_view.help_page; app.processEvents()
    assert len({id(browser.document()) for browser in page.browsers})==3
    first=page.browser
    for _ in range(4): app.processEvents()
    first.verticalScrollBar().setValue(first.verticalScrollBar().maximum()//2)
    position=first.verticalScrollBar().value()
    page.search.setText("giấy tờ nhân thân")
    page.contents.setCurrentRow(1); app.processEvents()
    assert page.browser is not first and page.browser.verticalScrollBar().value()==0
    assert page.search.text()==""
    assert "Quy trình hiện hành" not in page.browser.toPlainText().splitlines()[0]
    page.search.setText("riêng trang thứ hai")
    page.contents.setCurrentRow(2); app.processEvents()
    assert page.browser.verticalScrollBar().value()==0 and page.search.text()==""
    page.contents.setCurrentRow(0); app.processEvents()
    assert page.browser is first and first.verticalScrollBar().value()==position
    assert page.search.text()=="giấy tờ nhân thân"
    # A match belonging only to a different document must not move this page.
    first.setPlainText("first-page-only")
    page.browsers[1].setPlainText("second-page-only")
    page.search.setText("second-page-only"); page.find_text()
    assert "Không tìm thấy" in page.search_status.text()
    assert page.documents.currentIndex()==0


def test_help_search_and_no_results(hub,app):
    hub.open_help(); page=hub.launcher_view.help_page
    page.search.setText("giấy tờ nhân thân"); page.find_text()
    assert "Đã tìm thấy" in page.search_status.text() and page.browser.textCursor().selectedText()
    page.find_text(True); assert "Đã tìm thấy" in page.search_status.text()
    page.search.setText("no-result-unique-qa"); page.find_text()
    assert "Không tìm thấy" in page.search_status.text()


def test_search_category_and_return_preserve_ui_state(hub,app):
    view=hub.launcher_view; view.search.setText("thong bao"); app.processEvents()
    assert view.visible_tool_keys==["notice"]
    view.show_help(); view.navigate("all"); assert view.search.text()=="thong bao"
    view.reset_search(); view.navigate("hpnet")
    assert view.visible_tool_keys==["downloader","upload","approve"]
    view.search.setText("nothing-qa"); assert view.visible_tool_keys==[] and view.empty.isVisible()
    view.reset_search(); assert len(view.visible_tool_keys)==9
    assert len(hub.tool_buttons)==9


@pytest.mark.parametrize("size",[(900,660),(960,680),(1240,860),(1600,1000)])
def test_layout_no_horizontal_scroll_and_buttons_reachable(hub,app,size):
    hub.resize(*size); view=hub.launcher_view; app.processEvents()
    assert view.scroll.horizontalScrollBar().maximum()==0
    assert view.grid_columns in (1,2,3)
    for button in hub.tool_buttons.values():
        view.scroll.ensureWidgetVisible(button); button.setFocus(); app.processEvents()
        assert button.width()>=180 and button.height()>=40
        assert button.minimumSizeHint().width()<=button.width()
        assert button.accessibleName().startswith("Mở ")
    view.show_help(); app.processEvents()
    assert view.help_page.browser.horizontalScrollBar().maximum()==0


def test_cards_are_single_click_targets_with_minimal_hover_affordance(hub,app):
    view=hub.launcher_view; card=view.cards["excel"]
    assert card.findChildren(QPushButton)==[]
    assert card.cursor().shape()==Qt.PointingHandCursor
    assert "Mở công cụ" not in card.text()
    assert not card.arrow.isVisible()
    QApplication.sendEvent(card,QEvent(QEvent.Enter)); app.processEvents()
    assert card.arrow.isVisible() and card.property("hovered") is True
    QApplication.sendEvent(card,QEvent(QEvent.Leave)); app.processEvents()
    assert not card.arrow.isVisible()


def test_search_width_sidebar_and_help_readability(hub):
    view=hub.launcher_view
    assert view.search.maximumWidth()==680
    assert view.findChild(QPushButton,"openTool") is None
    assert "line-height:165%" in view.help_page.browsers[0].document().defaultStyleSheet()
    assert "QFrame#sidebarNote { background: transparent" in STYLE


def test_card_loading_prevents_double_click_and_reports_success(hub,app):
    card=hub.launcher_view.cards["downloader"]
    with patch.object(hub,"launch_external",return_value=True) as launch:
        card.click(); card.click()
        assert card.busy and not card.isEnabled()
        assert card.status.text()=="Đang mở công cụ…"
        app.processEvents()
        assert launch.call_count==1
    assert card.isEnabled() and not card.busy
    assert card.property("cardState")=="success"
    assert hub.launcher_view.toast.isVisible()


def test_card_error_feedback_restores_click_target(hub,app):
    card=hub.launcher_view.cards["downloader"]
    card.handler=lambda: False
    card.click(); assert not card.isEnabled()
    app.processEvents()
    assert card.isEnabled() and card.property("cardState")=="error"
    assert "Không thể" in card.status.text()


def test_keyboard_search_and_help_never_launch_tools(hub,app):
    view=hub.launcher_view; view.search.setFocus(); app.processEvents()
    QTest.keyClick(view.search,Qt.Key_F1); app.processEvents()
    assert view.pages.currentIndex()==1
    view.help_page.search.setFocus(); QTest.keyClicks(view.help_page.search,"Muc")
    assert not hub.open_tools


def test_sections_not_clipped_after_navigation_and_resize(hub,app):
    view=hub.launcher_view
    for size in ((900,660),(1240,860),(1600,1000),(900,660)):
        hub.resize(*size)
        for category in ("hpnet","help","all","prepare","all"):
            view.navigate(category)
            for _ in range(4): app.processEvents()
            if category=="help":
                assert view.help_page.contents.horizontalScrollBar().maximum()==0
                continue
            for key in view.visible_tool_keys:
                card=view.cards[key]; section=card.parentWidget()
                assert section.rect().contains(card.geometry()), (size,category,key,section.size(),card.geometry())
                assert card.rect().contains(card.arrow.geometry())


def test_theme_local_and_accessible_text_contrast(hub,app):
    def luminance(value):
        parts=[int(value[i:i+2],16)/255 for i in (1,3,5)]
        return sum(c*w for c,w in zip([c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4 for c in parts],(.2126,.7152,.0722)))
    for fore,back in ((COLORS['text'],COLORS['surface']),(COLORS['muted'],COLORS['canvas']),
                      ('#FFFFFF',COLORS['primary']),(COLORS['primary'],COLORS['tint'])):
        values=sorted([luminance(fore),luminance(back)])
        assert (values[1]+.05)/(values[0]+.05)>=4.5
    before=app.palette().color(QPalette.Base)
    hub.open_help(); assert app.palette().color(QPalette.Base)==before


def test_help_escapes_text_not_html(tmp_path):
    guide=tmp_path/'guide.txt'; guide.write_text('1. Section\n<script>not executable</script>',encoding='utf-8')
    html,_,_=guide_html([('Test',guide)])
    assert '<script>' not in html and '&lt;script&gt;' in html


def test_help_highlights_operational_labels_and_warnings(tmp_path):
    guide=tmp_path/'guide.txt'
    guide.write_text('MỤC ĐÍCH: Tạo file\nQUY TRÌNH: Chọn → Kiểm tra\nLƯU Ý: Không ghi đè',encoding='utf-8')
    html,_,_=guide_html([('Test',guide)])
    assert '<strong>MỤC ĐÍCH:</strong> Tạo file' in html
    assert '<strong>QUY TRÌNH:</strong> Chọn → Kiểm tra' in html
    assert 'class="guide-label warning"' in html
    assert '<strong>LƯU Ý:</strong> Không ghi đè' in html
