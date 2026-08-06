from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

INK = colors.HexColor("#18332D")
BRAND = colors.HexColor("#0F766E")
MUTED = colors.HexColor("#64746F")
PAPER = colors.HexColor("#FFFDF7")
LINE = colors.HexColor("#DFE9E5")

PDF_COPY = {
    "vi": ("Lịch trình", "Ngày đi", "Thời tiết", "Chi phí/người", "Nguồn thời tiết", "Chưa xác định", "Chưa có", "Ngày {day}", "Nguồn chưa ghi", "Nguồn", "Lưu ý", "Mình Đi Đâu Thế - lịch trình có nguồn kiểm chứng", "Trang {page}"),
    "en": ("Itinerary", "Departure date", "Weather", "Cost/person", "Weather source", "Not specified", "Unavailable", "Day {day}", "Source not provided", "Source", "Notes", "Mình Đi Đâu Thế - a source-verified itinerary", "Page {page}"),
    "ar": ("خط سير الرحلة", "تاريخ المغادرة", "الطقس", "التكلفة/للشخص", "مصدر الطقس", "غير محدد", "غير متوفر", "اليوم {day}", "المصدر غير مذكور", "المصدر", "ملاحظات", "Mình Đi Đâu Thế - خط سير موثق المصادر", "الصفحة {page}"),
    "bg": ("Маршрут", "Дата на тръгване", "Време", "Цена/човек", "Източник за времето", "Не е посочено", "Няма данни", "Ден {day}", "Няма посочен източник", "Източник", "Бележки", "Mình Đi Đâu Thế - маршрут с проверени източници", "Страница {page}"),
    "de": ("Reiseplan", "Abreisedatum", "Wetter", "Kosten/Person", "Wetterquelle", "Nicht angegeben", "Nicht verfügbar", "Tag {day}", "Quelle nicht angegeben", "Quelle", "Hinweise", "Mình Đi Đâu Thế - Reiseplan mit geprüften Quellen", "Seite {page}"),
    "es": ("Itinerario", "Fecha de salida", "Tiempo", "Costo/persona", "Fuente meteorológica", "Sin especificar", "No disponible", "Día {day}", "Fuente no indicada", "Fuente", "Notas", "Mình Đi Đâu Thế - itinerario con fuentes verificadas", "Página {page}"),
    "fr": ("Itinéraire", "Date de départ", "Météo", "Coût/personne", "Source météo", "Non précisée", "Indisponible", "Jour {day}", "Source non indiquée", "Source", "Remarques", "Mình Đi Đâu Thế - itinéraire aux sources vérifiées", "Page {page}"),
    "he": ("מסלול טיול", "תאריך יציאה", "מזג אוויר", "עלות/לאדם", "מקור מזג האוויר", "לא צוין", "לא זמין", "יום {day}", "לא צוין מקור", "מקור", "הערות", "Mình Đi Đâu Thế - מסלול עם מקורות מאומתים", "עמוד {page}"),
    "hi": ("यात्रा कार्यक्रम", "प्रस्थान तिथि", "मौसम", "लागत/व्यक्ति", "मौसम स्रोत", "निर्दिष्ट नहीं", "उपलब्ध नहीं", "दिन {day}", "स्रोत नहीं दिया गया", "स्रोत", "टिप्पणियाँ", "Mình Đi Đâu Thế - स्रोत-सत्यापित यात्रा कार्यक्रम", "पृष्ठ {page}"),
    "it": ("Itinerario", "Data di partenza", "Meteo", "Costo/persona", "Fonte meteo", "Non specificata", "Non disponibile", "Giorno {day}", "Fonte non indicata", "Fonte", "Note", "Mình Đi Đâu Thế - itinerario con fonti verificate", "Pagina {page}"),
    "ja": ("旅程", "出発日", "天気", "1人あたりの費用", "天気情報源", "未指定", "利用不可", "{day}日目", "情報源の記載なし", "情報源", "注意事項", "Mình Đi Đâu Thế - 情報源を確認済みの旅程", "{page}ページ"),
    "nl": ("Reisplan", "Vertrekdatum", "Weer", "Kosten/persoon", "Weerbron", "Niet opgegeven", "Niet beschikbaar", "Dag {day}", "Bron niet vermeld", "Bron", "Notities", "Mình Đi Đâu Thế - reisplan met geverifieerde bronnen", "Pagina {page}"),
    "pl": ("Plan podróży", "Data wyjazdu", "Pogoda", "Koszt/osobę", "Źródło pogody", "Nie określono", "Niedostępne", "Dzień {day}", "Nie podano źródła", "Źródło", "Uwagi", "Mình Đi Đâu Thế - plan ze zweryfikowanymi źródłami", "Strona {page}"),
    "pt": ("Itinerário", "Data de partida", "Clima", "Custo/pessoa", "Fonte meteorológica", "Não especificada", "Indisponível", "Dia {day}", "Fonte não indicada", "Fonte", "Observações", "Mình Đi Đâu Thế - itinerário com fontes verificadas", "Página {page}"),
    "ru": ("Маршрут", "Дата отправления", "Погода", "Стоимость/человек", "Источник погоды", "Не указано", "Недоступно", "День {day}", "Источник не указан", "Источник", "Примечания", "Mình Đi Đâu Thế - маршрут с проверенными источниками", "Страница {page}"),
    "tr": ("Gezi planı", "Hareket tarihi", "Hava durumu", "Kişi başı maliyet", "Hava durumu kaynağı", "Belirtilmedi", "Mevcut değil", "Gün {day}", "Kaynak belirtilmedi", "Kaynak", "Notlar", "Mình Đi Đâu Thế - kaynakları doğrulanmış gezi planı", "Sayfa {page}"),
    "zh": ("行程", "出发日期", "天气", "每人费用", "天气来源", "未指定", "暂无", "第{day}天", "未注明来源", "来源", "注意事项", "Mình Đi Đâu Thế - 来源经核实的行程", "第{page}页"),
    "ko": ("여행 일정", "출발일", "날씨", "1인당 비용", "날씨 출처", "미지정", "정보 없음", "{day}일차", "출처 미기재", "출처", "유의 사항", "Mình Đi Đâu Thế - 출처가 검증된 여행 일정", "{page}페이지"),
    "th": ("แผนการเดินทาง", "วันที่ออกเดินทาง", "สภาพอากาศ", "ค่าใช้จ่าย/คน", "แหล่งข้อมูลอากาศ", "ไม่ระบุ", "ไม่มีข้อมูล", "วันที่ {day}", "ไม่ได้ระบุแหล่งที่มา", "แหล่งที่มา", "หมายเหตุ", "Mình Đi Đâu Thế - แผนการเดินทางที่ตรวจสอบแหล่งที่มาแล้ว", "หน้า {page}"),
}


def _font_path(bold: bool = False) -> Path:
    candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    path = next((candidate for candidate in candidates if candidate.exists()), None)
    if not path:
        raise RuntimeError("Không tìm thấy font Unicode để xuất PDF")
    return path


def _register_fonts() -> None:
    if "TravelSans" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("TravelSans", str(_font_path())))
        pdfmetrics.registerFont(TTFont("TravelSans-Bold", str(_font_path(True))))


def _footer(canvas, document, copy: tuple[str, ...]) -> None:
    canvas.saveState()
    canvas.setFont("TravelSans", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 12 * mm, copy[11])
    canvas.drawRightString(192 * mm, 12 * mm, copy[12].format(page=document.page))
    canvas.restoreState()


def build_itinerary_pdf(plan: dict, locale: str = "vi") -> bytes:
    _register_fonts()
    copy = PDF_COPY.get(locale, PDF_COPY["vi"])
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=20 * mm,
        title=plan.get("tieu_de", copy[0]), author="Mình Đi Đâu Thế",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "TravelTitle", parent=styles["Title"], fontName="TravelSans-Bold",
        fontSize=25, leading=30, textColor=INK, alignment=TA_CENTER, spaceAfter=7 * mm,
    )
    body = ParagraphStyle(
        "TravelBody", parent=styles["BodyText"], fontName="TravelSans",
        fontSize=9.5, leading=14, textColor=INK,
    )
    small = ParagraphStyle(
        "TravelSmall", parent=body, fontSize=8, leading=11, textColor=MUTED,
    )
    day_style = ParagraphStyle(
        "TravelDay", parent=body, fontName="TravelSans-Bold", fontSize=15,
        leading=20, textColor=BRAND, spaceBefore=5 * mm, spaceAfter=3 * mm,
    )
    story = [Paragraph(escape(plan.get("tieu_de", copy[0])), title)]
    story.append(Paragraph(escape(plan.get("tom_tat", "")), body))
    story.append(Spacer(1, 5 * mm))
    weather = plan.get("thoi_tiet", {})
    facts = [
        [copy[1], plan.get("ngay_di", copy[5])],
        [copy[2], weather.get("tinh_trang", copy[6])],
        [copy[3], f"{int(plan.get('chi_phi_moi_nguoi', 0)):,} VND"],
        [copy[4], weather.get("nguon") or copy[6]],
    ]
    fact_table = Table(facts, colWidths=[42 * mm, 115 * mm])
    fact_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "TravelSans"),
        ("FONTNAME", (0, 0), (0, -1), "TravelSans-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9), ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF7F4")),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(fact_table)
    for day_index, day in enumerate(plan.get("ngay", [])):
        if day_index and day_index % 2 == 0:
            story.append(PageBreak())
        story.append(Paragraph(escape(day.get("nhan_de", copy[7].format(day=day_index + 1))), day_style))
        for slot in day.get("khoang_gio", []):
            source = escape(slot.get("nguon") or copy[8])
            source_url = slot.get("nguon_url")
            source_line = (
                f'<link href="{escape(source_url)}" color="#0F766E">{copy[9]}: {source}</link>'
                if isinstance(source_url, str) and source_url.startswith("https://") else f"{copy[9]}: {source}"
            )
            detail = Paragraph(
                f'<b>{escape(slot["ten_dia_diem"])}</b><br/>'
                f'{escape(slot.get("mo_ta", ""))}<br/>'
                f'<font color="#64746F">{int(slot.get("chi_phi", 0)):,} VND - {source_line}</font>',
                body,
            )
            time = Paragraph(
                f'<b>{escape(slot["bat_dau"])}</b><br/><font color="#64746F">{escape(slot["ket_thuc"])}</font>',
                small,
            )
            table = Table([[time, detail]], colWidths=[26 * mm, 131 * mm])
            table.setStyle(TableStyle([
                ("FONTNAME", (0, 0), (-1, -1), "TravelSans"),
                ("BACKGROUND", (0, 0), (-1, -1), PAPER),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("LINEBEFORE", (0, 0), (0, 0), 3, BRAND),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.extend([KeepTogether(table), Spacer(1, 2.5 * mm)])
    if plan.get("luu_y"):
        story.append(Paragraph(copy[10], day_style))
        for note in plan["luu_y"]:
            story.append(Paragraph(f"• {escape(note)}", body))
    footer = lambda canvas, doc: _footer(canvas, doc, copy)
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
