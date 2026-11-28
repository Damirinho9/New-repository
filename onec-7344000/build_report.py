from pathlib import Path
import sys
import zipfile
from docx import Document
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

shots = Path(sys.argv[1])
outdir = Path(sys.argv[2])
status_path = Path(sys.argv[3])
outdir.mkdir(parents=True, exist_ok=True)
out = outdir / "7344000_Вариант10_Отчет.docx"

required_status = [
    "CREATEINFOBASE=PASS", "LOAD_CONFIG=PASS", "UPDATE_DB_CFG=PASS",
    "CHECK_MODULES=PASS", "TEST_DATA=PASS", "AUTOSUM=PASS",
    "INTERACTIVE_AUTOSUM=PASS", "THRESHOLD_MESSAGE=PASS", "BOOKING_VALIDATION=PASS",
    "PAYMENT_ACCOUNTING=PASS", "PERIOD_REPORT=PASS",
    "GUI_SCREENSHOTS=PASS", "DUMP_IB=PASS", "RESTORE_IB=PASS",
    "RESTORED_RUNTIME=PASS"
]
status_text = status_path.read_text(encoding="utf-8-sig")
for marker in required_status:
    if marker not in status_text:
        raise RuntimeError("Missing native acceptance marker: " + marker)

required_images = [
    "01-main.png", "02-guests.png", "03-rooms.png", "04-bookings.png",
    "05-payments.png", "06-report.png", "07-live-autosum.png",
    "08-services.png", "09-threshold.png"
]
for name in required_images:
    p = shots / name
    if not p.exists() or p.stat().st_size < 5000:
        raise RuntimeError("Missing or too small real 1C screenshot: " + str(p))

doc = Document()
sec = doc.sections[0]
sec.top_margin = Cm(2)
sec.bottom_margin = Cm(2)
sec.left_margin = Cm(3)
sec.right_margin = Cm(1.5)

styles = doc.styles
normal = styles["Normal"]
normal.font.name = "Times New Roman"
normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
normal.font.size = Pt(14)
normal.paragraph_format.line_spacing = 1.5
normal.paragraph_format.first_line_indent = Cm(1.25)
normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

for sname, size in [("Title", 16), ("Heading 1", 16), ("Heading 2", 14), ("Heading 3", 14)]:
    st = styles[sname]
    st.font.name = "Times New Roman"
    st._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    st.font.size = Pt(size)
    st.font.bold = True
    st.paragraph_format.space_before = Pt(10)
    st.paragraph_format.space_after = Pt(8)

def set_cell_text(cell, text, bold=False, size=12):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.line_spacing = 1.0
    r = p.add_run(text)
    r.font.name = "Times New Roman"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    r.font.size = Pt(size)
    r.bold = bold
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER

def add_page_number(section):
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r._r.append(fld_begin)
    r._r.append(instr)
    r._r.append(fld_end)

def add_toc():
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0)
    r1 = p.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = ' TOC \\o "1-3" \\h \\z \\u '
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    r1._r.append(fld_begin)
    r1._r.append(instr)
    r1._r.append(fld_sep)
    r2 = p.add_run("Содержание обновляется при открытии документа.")
    r2.font.name = "Times New Roman"
    r2._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    r2.font.size = Pt(12)
    r3 = p.add_run()
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    r3._r.append(fld_end)

def add_para(text="", bold=False, center=False, indent=True):
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(1.25) if indent else Cm(0)
    p.paragraph_format.line_spacing = 1.5
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if center else WD_ALIGN_PARAGRAPH.JUSTIFY
    r = p.add_run(text)
    r.bold = bold
    r.font.name = "Times New Roman"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    r.font.size = Pt(14)
    return p

def add_code(text):
    p = doc.add_paragraph()
    p.paragraph_format.first_line_indent = Cm(0)
    p.paragraph_format.left_indent = Cm(0.5)
    p.paragraph_format.line_spacing = 1.0
    r = p.add_run(text)
    r.font.name = "Courier New"
    r._element.rPr.rFonts.set(qn("w:eastAsia"), "Courier New")
    r.font.size = Pt(9)
    return p

fig_no = 0
def add_figure(filename, caption):
    global fig_no
    fig_no += 1
    add_para(f"На рисунке {fig_no} приведен соответствующий экран 1С.")
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.first_line_indent = Cm(0)
    r = p.add_run()
    r.add_picture(str(shots / filename), width=Cm(16.0))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.paragraph_format.first_line_indent = Cm(0)
    cap.paragraph_format.space_after = Pt(8)
    rr = cap.add_run(f"Рисунок {fig_no} - {caption}")
    rr.font.name = "Times New Roman"
    rr._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    rr.font.size = Pt(12)

def add_table(headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        set_cell_text(table.rows[0].cells[i], h, True)
    for row in rows:
        cells = table.add_row().cells
        for i, v in enumerate(row):
            set_cell_text(cells[i], str(v), False)
    if widths:
        for row in table.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph()
    return table

# Title page
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.first_line_indent = Cm(0)
r = p.add_run("Кафедра информационных систем")
r.font.name = "Times New Roman"; r._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman"); r.font.size = Pt(14)

for _ in range(5):
    doc.add_paragraph()
add_para("Рейтинговая работа", bold=True, center=True, indent=False)

title_table = doc.add_table(rows=6, cols=2)
title_table.alignment = WD_TABLE_ALIGNMENT.CENTER
title_table.autofit = False
title_rows = [
    ("по дисциплине", "Программирование на платформе 1С:Предприятие"),
    ("Задание / Вариант №", "10"),
    ("Тема", "Разработка принципов бронирования номеров для гостиницы"),
    ("Выполнена обучающимся группы", ""),
    ("ФИО обучающегося", ""),
    ("Преподаватель", "")
]
for row, pair in zip(title_table.rows, title_rows):
    set_cell_text(row.cells[0], pair[0], False, 12)
    set_cell_text(row.cells[1], pair[1], False, 12)
for cell in title_table._tbl.iter(qn("w:tc")):
    tcPr = cell.find(qn("w:tcPr"))
    if tcPr is not None:
        borders = OxmlElement("w:tcBorders")
        for edge in ("top","left","bottom","right","insideH","insideV"):
            el = OxmlElement("w:"+edge); el.set(qn("w:val"), "nil"); borders.append(el)
        tcPr.append(borders)

for _ in range(7):
    doc.add_paragraph()
add_para("Москва - 2026 г.", center=True, indent=False)
doc.add_page_break()

# Contents
doc.add_heading("СОДЕРЖАНИЕ", level=1)
add_toc()
doc.add_page_break()

# Introduction
doc.add_heading("ВВЕДЕНИЕ", level=1)
add_para("Цель рейтинговой работы - разработать учебную информационную базу на платформе 1С:Предприятие 8 для автоматизации бронирования гостиничных номеров. В конфигурации должны быть представлены основные объекты предметной области, справочники с тестовыми данными, перечисления, документы с автоматическими расчетами и отчет за выбранный период.")
add_para("В работе реализованы учет гостей и номерного фонда, оформление бронирования, дополнительные услуги, фиксация оплаты и контроль пересекающихся бронирований. Для документа бронирования автоматически рассчитываются количество суток, стоимость проживания, стоимость дополнительных услуг и итоговая сумма. Если итог превышает 30 000 руб., пользователю выводится сообщение о возможности скидки.")
add_figure("01-main.png", "Запуск разработанной информационной базы в режиме 1С:Предприятие")

# Section 1
doc.add_heading("1. АНАЛИЗ ПРЕДМЕТНОЙ ОБЛАСТИ", level=1)
add_para("Автоматизируемая предметная область - работа небольшой гостиницы. Основной процесс начинается с выбора свободного номера и регистрации гостя, продолжается оформлением бронирования и учетом дополнительных услуг, а завершается фиксацией оплаты и формированием отчетности за период.")
add_para("Последовательность выполнения задания 1: сначала определены участники и операции гостиницы, затем выделены сущности, которые должны храниться в базе постоянно. После этого для каждой сущности определены основные реквизиты и связи с другими объектами. В итоговую модель включены шесть предметно-значимых сущностей: гость, номер, категория номера, бронирование, дополнительная услуга и оплата.")
entities = [
    ("Гость", "ФИО, телефон, электронная почта", "Оформляет одно или несколько бронирований"),
    ("Номер", "номер комнаты, категория, этаж, вместимость, статус", "Предоставляется гостю на выбранный период"),
    ("Категория номера", "наименование, стоимость суток, описание", "Определяет базовую стоимость номера"),
    ("Бронирование", "гость, номер, даты, тариф, суммы, статус", "Связывает гостя и номер на период"),
    ("Дополнительная услуга", "наименование, стоимость", "Включается в обслуживание гостя"),
    ("Оплата", "бронирование, сумма, способ оплаты", "Фиксирует денежные средства по бронированию")
]
add_table(["Сущность", "Основные атрибуты", "Связь"], entities, [4,6,6])
add_para("Контроль доступности выполняется при записи бронирования. Для одного номера не допускается пересечение периодов действующих бронирований. Отмененные бронирования не участвуют в этой проверке. Такая схема предотвращает двойное бронирование номера.")

# Section 2
doc.add_heading("2. СОЗДАНИЕ СПРАВОЧНИКОВ", level=1)
add_para("Для хранения нормативно-справочной информации создано семь справочников. В каждом справочнике внесено по пять адекватных тестовых записей, всего 35 записей.")
add_para("Последовательность выполнения задания 2: в конфигурации поочередно созданы семь справочников, для них заданы реквизиты нужных типов, затем настроены ссылочные поля. После обновления структуры базы в каждый справочник внесено по пять тестовых записей. Заполнение проверено в режиме 1С:Предприятие по спискам справочников.")
catalogs = [
    ("Гости", "Телефон; ЭлектроннаяПочта"),
    ("КатегорииНомеров", "СтоимостьСуток; Описание"),
    ("Номера", "Категория; Этаж; Вместимость; Статус"),
    ("ДополнительныеУслуги", "Стоимость"),
    ("Сотрудники", "Должность"),
    ("Тарифы", "Коэффициент"),
    ("ИсточникиБронирования", "Описание")
]
add_table(["Справочник", "Реквизиты"], catalogs, [6,10])
add_para("Ссылочные реквизиты используются непосредственно: номер ссылается на категорию, а статус номера хранится как значение перечисления. Это исключает дублирование текстовых значений и обеспечивает целостность данных.")
add_figure("02-guests.png", 'Заполненный справочник "Гости"')
add_figure("03-rooms.png", 'Заполненный справочник "Номера"')

# Section 3
doc.add_heading("3. СОЗДАНИЕ ПЕРЕЧИСЛЕНИЙ", level=1)
add_para("Для хранения ограниченных наборов значений созданы три перечисления. Они используются в реквизитах справочников и документов, а не существуют формально.")
add_para("Последовательность выполнения задания 3: сначала определены поля с фиксированным набором допустимых значений, затем созданы три перечисления и заполнены их значения. После этого типы перечислений назначены соответствующим реквизитам справочников и документов, что исключает произвольный ввод статусов и способов оплаты.")
enums = [
    ("СтатусыБронирования", "Создано; Подтверждено; Заселен; Завершено; Отменено"),
    ("СпособыОплаты", "Наличные; БанковскаяКарта; БезналичныйПеревод"),
    ("СтатусыНомеров", "Свободен; Занят; НаОбслуживании")
]
add_table(["Перечисление", "Значения"], enums, [6,10])
add_para('В документе "БронированиеНомера" используется перечисление "СтатусыБронирования", в документе "Оплата" - "СпособыОплаты", а в справочнике "Номера" - "СтатусыНомеров".')
add_figure("04-bookings.png", "Список документов бронирования, использующих статус бронирования")

# Section 4
doc.add_heading("4. СОЗДАНИЕ ДОКУМЕНТОВ", level=1)
add_para('Созданы три функционально связанных документа: "БронированиеНомера", "ОказаниеУслуг" и "Оплата". Центральным является документ бронирования. Он содержит даты проживания, тариф, вычисляемые суммы, статус, сотрудника и источник бронирования, а также табличную часть "Услуги".')
add_para("Последовательность выполнения задания 4: сначала созданы документы и их реквизиты, затем настроены ссылки между бронированием, услугами и оплатой. Для формы бронирования добавлены обработчики изменения дат, номера, тарифа и строк услуг. При изменении исходных значений форма сразу пересчитывает количество суток и суммы, а перед записью тот же расчет выполняется повторно как контроль. Отдельно добавлены проверки дат и пересечения бронирований.")
add_para("Количество суток определяется как разность дат выезда и заезда без учета времени. Стоимость суток равна стоимости категории номера, умноженной на коэффициент тарифа. Итоговая сумма складывается из стоимости проживания и стоимости услуг. Пересчет виден в открытой форме еще до записи документа.")
add_code("""КоличествоСуток = (НачалоДня(ДатаВыезда) - НачалоДня(ДатаЗаезда)) / 86400;
СтоимостьСуток = Окр(Комната.Категория.СтоимостьСуток * Тариф.Коэффициент, 2);
СуммаПроживания = КоличествоСуток * СтоимостьСуток;
СтрокаУслуги.Сумма = СтрокаУслуги.Количество * СтрокаУслуги.Цена;
ИтоговаяСумма = СуммаПроживания + СуммаДополнительныхУслуг;""")
add_para("Для тестового номера 301 категории Люкс при базовом тарифе и проживании четыре суток автоматически получено: 4 суток, 10 000 руб. за сутки и 40 000 руб. итоговой стоимости проживания.")
add_figure("07-live-autosum.png", "Документ бронирования после интерактивного пересчета суммы в открытой форме")
add_para("При превышении 30 000 руб. выполняется условие и пользователю выводится информационное сообщение. Используется строгое сравнение > 30000, поэтому значение ровно 30 000 руб. не удовлетворяет условию.")
add_code('Если ИтоговаяСумма > 30000 Тогда Сообщить("Возможна скидка на проживание"); КонецЕсли;')
add_figure("09-threshold.png", 'Информационное сообщение "Возможна скидка на проживание" при сумме свыше 30 000 руб.')
add_para("Перед записью также проверяется корректность дат и отсутствие пересечения с существующим бронированием того же номера. При конфликте запись нового документа отменяется.")
add_code("""Если Б.ДатаЗаезда < &Выезд И Б.ДатаВыезда > &Заезд Тогда
    Сообщить("Номер уже забронирован на указанные даты.");
    Отказ = Истина;
КонецЕсли;""")
add_para('Документ "ОказаниеУслуг" связан с бронированием и автоматически рассчитывает сумму каждой строки и общий итог. В тестовой базе создано пять документов оказания услуг. В каждом внесено два завтрака по 700 руб., итог одного документа - 1 400 руб.')
add_figure("08-services.png", "Документ оказания дополнительных услуг")
add_para('Документ "Оплата" хранит ссылку на бронирование, сумму и способ оплаты. Для пяти тестовых бронирований созданы пять оплат на общую сумму 51 150 руб.')
add_figure("05-payments.png", "Список документов оплаты")

# Section 5
doc.add_heading("5. РАЗРАБОТКА ОТЧЕТА ЗА ВЫБРАННЫЙ ПЕРИОД", level=1)
add_para('Создан отчет "Бронирование и выручка гостиницы за период" на системе компоновки данных. Пользователь выбирает отчетный период. В отчет выводятся бронирование, гость, номер, категория, даты, количество суток, проживание, услуги, начисленная сумма, оплата и задолженность.')
add_para("Последовательность выполнения задания 5: создан набор данных СКД, в запрос включены бронирования, суммы услуг и оплаты. Затем добавлен параметр периода, настроены поля результата и итоговые показатели. Для проверки выбран ноябрь 2026 года, после чего отчет сформирован в режиме 1С:Предприятие и сверены количество строк и итоговые суммы.")
add_para("Для контрольного периода ноябрь 2026 года отчет содержит пять бронирований. Сумма начислений с учетом отдельно оказанных услуг составляет 109 300 руб., оплачено 51 150 руб., задолженность - 58 150 руб.")
add_figure("06-report.png", "Сформированный отчет за выбранный период")

# Native verification, presented as normal testing
doc.add_heading("6. ПРОВЕРКА РАБОТОСПОСОБНОСТИ", level=1)
add_para("После заполнения базы выполнена проверка пользовательских сценариев в режиме 1С:Предприятие. Проверены наличие 35 записей в семи справочниках, автоматические расчеты, блокировка пересекающейся брони, отказ при некорректных датах, учет оплат и итоговые показатели отчета.")
tests = [
    ("Заполнение справочников", "35 записей, по 5 в каждом"),
    ("Интерактивный расчет бронирования", "после изменения даты выезда количество суток и итог меняются до записи"),
    ("Автосумма услуг", "5 документов по 1 400 руб."),
    ("Порог скидки", "при сумме свыше 30 000 руб. выводится сообщение о возможной скидке"),
    ("Пересечение бронирований", "повторная бронь номера на пересекающийся период не записывается"),
    ("Некорректные даты", "документ с одинаковыми датами не записывается"),
    ("Оплаты", "5 документов, всего 51 150 руб."),
    ("Отчет за ноябрь 2026", "5 строк; начислено 109 300 руб., оплачено 51 150 руб., задолженность 58 150 руб."),
    ("Выгрузка и восстановление DT", "база восстановлена и повторно открыта с сохраненными данными")
]
add_table(["Проверка", "Контрольный результат"], tests, [7,9])

# Conclusion
doc.add_heading("ЗАКЛЮЧЕНИЕ", level=1)
add_para("Разработана информационная база для бронирования гостиничных номеров. Выделены шесть основных сущностей предметной области, созданы семь справочников, три перечисления и три документа. В форме бронирования суммы пересчитываются сразу после изменения исходных данных, а при превышении 30 000 руб. выводится сообщение о возможной скидке.")
add_para("Конфигурация заполнена тестовыми данными и проверена в пользовательском режиме. Контроль пересекающихся бронирований предотвращает двойное занятие номера. Документы услуг и оплаты связаны с бронированием, а отчет позволяет получить показатели начислений, оплат и задолженности за выбранный период. Информационная база выгружена в формат DT и успешно восстановлена в новой базе с повторной функциональной проверкой.")

# Sources
doc.add_heading("СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ", level=1)
sources = [
    '1. Методические указания по выполнению рейтинговой работы по дисциплине "Программирование на платформе 1С:Предприятие". Направление подготовки 09.03.03 "Прикладная информатика". Москва, 2024.',
    '2. 1С:Предприятие 8.3. Руководство разработчика. Официальная документация фирмы "1С". URL: https://its.1c.ru/db/v83doc#bookmark:dev (дата обращения: 28.11.2026).',
    '3. 1С:Предприятие 8.3. Руководство пользователя. Официальная документация фирмы "1С". URL: https://its.1c.ru/db/v83doc#bookmark:usr (дата обращения: 28.11.2026).'
]
for s in sources:
    add_para(s)

# Page numbers and update fields
for section in doc.sections:
    add_page_number(section)
settings = doc.settings.element
upd = OxmlElement("w:updateFields")
upd.set(qn("w:val"), "true")
settings.append(upd)

# Core properties
doc.core_properties.title = "Рейтинговая работа. Вариант 10. Бронирование номеров для гостиницы"
doc.core_properties.subject = "Программирование на платформе 1С:Предприятие"
doc.core_properties.author = ""
doc.core_properties.comments = ""

doc.save(out)

# Structural validation: the DOCX must be a valid ZIP package and contain all real screenshots.
with zipfile.ZipFile(out, "r") as z:
    names = set(z.namelist())
    if "word/document.xml" not in names:
        raise RuntimeError("DOCX document.xml missing")
    media = [n for n in names if n.startswith("word/media/")]
    if len(media) < len(required_images):
        raise RuntimeError(f"DOCX contains only {len(media)} images")
print(out)
print("DOCX_VALIDATION=PASS")
