"""Code-native vector symbols; one stroke language, no emoji or remote assets."""
from functools import lru_cache
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS = {
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "notice": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9zM14 3v6h6M8 13h8M8 17h5"/>',
    "excel": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 9v12M15 9v12M3 15h18"/>',
    "duplicate_parcel": '<rect x="3" y="4" width="14" height="16" rx="2"/><path d="M3 10h14M9 4v16M18 8l3 3-6 6-3 1 1-3z"/>',
    "data_normalizer": '<path d="M4 5h16M8 5v14M5 19h6M14 11h7M17.5 7.5v7M14 19h7"/>',
    "rename": '<path d="M9 4H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2v-4M13 3h8v8M21 3 10 14M7 17h7"/>',
    "cleaner": '<path d="M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6zM8 12l3 3 5-6"/>',
    "downloader": '<path d="M12 3v12m-5-5 5 5 5-5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
    "upload": '<path d="M12 16V4m-5 5 5-5 5 5M4 16v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4"/>',
    "approve": '<path d="m3 11 18-8-7 18-3-7-8-3zM11 14 21 3"/>',
    "help": '<path d="M12 5c-3-2-6-2-9-1v16c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1v16M6 8h3M15 8h3M6 12h3M15 12h3"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    "arrow": '<path d="M4 12h16m-6-6 6 6-6 6"/>',
    "folder": '<path d="M3 7V5a2 2 0 0 1 2-2h5l2 4h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
}


@lru_cache(maxsize=64)
def icon(name, color="#2458C5"):
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</svg>'
    renderer=QSvgRenderer(QByteArray(svg.encode())); result=QIcon()
    for size in (24,32,48,64,96):
        pixmap=QPixmap(size,size); pixmap.fill(Qt.transparent)
        painter=QPainter(pixmap); renderer.render(painter); painter.end(); result.addPixmap(pixmap)
    return result
