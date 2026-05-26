import struct
from PySide6.QtCore import Qt, QBuffer, QByteArray, QIODevice, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import QApplication

app = QApplication([])

def draw_icon(pm):
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    sz = pm.width()
    m = max(2, sz // 16)
    cx, cy = sz // 2, sz // 2
    r = sz * 0.28
    pw = max(3, sz // 12)
    p.setBrush(QColor("#339AF0"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(m, m, sz - 2*m, sz - 2*m)
    pen = QPen(QColor("white"), pw)
    pen.setCapStyle(Qt.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawLine(cx, cy, cx, cy - int(r + pw))
    p.drawArc(QRect(int(cx-r), int(cy-r), int(2*r), int(2*r)), 300*16, 300*16)
    p.end()

def png_bytes(pm):
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    pm.save(buf, "PNG")
    buf.close()
    return bytes(data)

entries = []
for sz in (64, 32):
    pm = QPixmap(sz, sz)
    pm.fill(Qt.transparent)
    draw_icon(pm)
    entries.append((png_bytes(pm), sz, sz))

count = len(entries)
hdr = struct.pack("<HHH", 0, 1, count)
ofs = 6 + count * 16
ico = bytearray(hdr)
for png, w, h in entries:
    ico.extend(struct.pack("<BBBBHHII", w if w<256 else 0, h if h<256 else 0, 0, 0, 1, 32, len(png), ofs))
    ofs += len(png)
for png, _, _ in entries:
    ico.extend(png)

with open("app_icon.ico", "wb") as f:
    f.write(ico)
print("OK - app_icon.ico created")
