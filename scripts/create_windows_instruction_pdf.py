from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Magical PDF - Windows setup and Codex handoff.pdf"
FONT = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"

pdfmetrics.registerFont(TTFont("ArialUnicode", FONT))

styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="BodyRU",
        parent=styles["BodyText"],
        fontName="ArialUnicode",
        fontSize=10.8,
        leading=15,
        textColor=colors.HexColor("#1e2322"),
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        name="TitleRU",
        parent=styles["Title"],
        fontName="ArialUnicode",
        fontSize=23,
        leading=28,
        textColor=colors.HexColor("#141e1c"),
        alignment=0,
        spaceAfter=12,
    )
)
styles.add(
    ParagraphStyle(
        name="H1RU",
        parent=styles["Heading1"],
        fontName="ArialUnicode",
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#141e1c"),
        spaceBefore=12,
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        name="CodeRU",
        parent=styles["Code"],
        fontName="ArialUnicode",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#1c2b26"),
    )
)


def bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(item, styles["BodyRU"]), leftIndent=10) for item in items],
        bulletType="bullet",
        leftIndent=18,
        bulletFontName="ArialUnicode",
        bulletFontSize=8,
    )


def code(lines):
    table = Table([[Paragraph("<br/>".join(lines), styles["CodeRU"])]], colWidths=[6.55 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F7F2")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#D6E1D8")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


story = [
    Paragraph("Magical PDF: инструкция для Windows и Codex", styles["TitleRU"]),
    Paragraph(
        "Документ для переноса проекта на ПК: как скачать репозиторий, подготовить окружение, "
        "собрать Windows-версию и продолжить работу в Codex.",
        styles["BodyRU"],
    ),
    Spacer(1, 8),
    Paragraph("1. Что уже готово", styles["H1RU"]),
    bullets(
        [
            "Проект перенесен в GitHub-репозиторий: https://github.com/beaver20007/magical-pdf",
            "Публичная веб-версия доступна по адресу: https://beaver20007.github.io/magical-pdf/",
            "Основной функционал: PDF превращается в JPEG-страницы, затем собирается обратно в PDF как скан без выделяемого текстового слоя.",
            "Также есть экспорт JPEG-страниц в ZIP.",
            "Версия macOS уже проверена по функционалу.",
        ]
    ),
    Paragraph("2. Что установить на Windows", styles["H1RU"]),
    bullets(
        [
            "Git for Windows.",
            "Node.js LTS.",
            "Rust через rustup.",
            "Visual Studio Build Tools 2022.",
            "В Visual Studio Build Tools выбрать компонент Desktop development with C++.",
            "Проверить, что установлены MSVC v143 и Windows SDK.",
            "WebView2 Evergreen Runtime, если его нет в системе.",
        ]
    ),
    Paragraph("3. Как скачать проект на ПК", styles["H1RU"]),
    Paragraph("Открыть PowerShell и выполнить команды:", styles["BodyRU"]),
    code(
        [
            r"cd $env:USERPROFILE\Documents",
            "git clone https://github.com/beaver20007/magical-pdf.git",
            "cd magical-pdf",
        ]
    ),
    Paragraph("4. Как запустить веб-версию локально", styles["H1RU"]),
    code(["npm ci", "npm run dev:web"]),
    Paragraph("После запуска открыть в браузере адрес:", styles["BodyRU"]),
    code(["http://127.0.0.1:5173/"]),
    Paragraph("5. Как собрать Windows .exe", styles["H1RU"]),
    code(["npm run build:windows"]),
    Paragraph("Готовый инсталлятор должен появиться в папке:", styles["BodyRU"]),
    code([r"src-tauri\target\release\bundle\nsis\\"]),
    Paragraph("6. Как продолжить работу в Codex на ПК", styles["H1RU"]),
    Paragraph("В Codex на Windows открыть папку проекта:", styles["BodyRU"]),
    code([r"%USERPROFILE%\Documents\magical-pdf"]),
    Paragraph("Затем написать Codex следующую команду:", styles["BodyRU"]),
    code(
        [
            "Продолжи работу над Magical PDF. Прочитай CODEX_HANDOFF.md и WINDOWS_SETUP.md,",
            "затем помоги собрать Windows .exe.",
        ]
    ),
    Paragraph("7. Важные файлы проекта", styles["H1RU"]),
    bullets(
        [
            "index.html - основная структура интерфейса.",
            "styles.css - дизайн приложения.",
            "app.js - логика загрузки, преобразования и скачивания файлов.",
            "src-tauri/src/main.rs - нативное сохранение файлов и открытие Finder/Explorer.",
            "src-tauri/tauri.conf.json - настройки приложения, названия, окна и иконок.",
            "CODEX_HANDOFF.md - краткий контекст проекта для Codex.",
            "WINDOWS_SETUP.md - техническая инструкция по Windows-сборке.",
        ]
    ),
    Paragraph("8. Что важно проверить в Windows-версии", styles["H1RU"]),
    bullets(
        [
            "Загружается ли PDF через кнопку выбора файла и перетаскивание.",
            "Создается ли новый PDF как скан, без выделяемого текста.",
            "Создается ли ZIP с JPEG-страницами.",
            "Открывается ли Explorer после сохранения файла.",
            "Корректно ли отображается название Magical PDF и иконка приложения.",
        ]
    ),
    Spacer(1, 8),
    Paragraph(
        "<b>Примечание:</b> сам чат Codex напрямую перенести нельзя. Для продолжения работы "
        "достаточно открыть репозиторий на ПК и дать Codex указание прочитать CODEX_HANDOFF.md.",
        styles["BodyRU"],
    ),
]

doc = SimpleDocTemplate(
    str(OUT),
    pagesize=LETTER,
    rightMargin=0.85 * inch,
    leftMargin=0.85 * inch,
    topMargin=0.75 * inch,
    bottomMargin=0.75 * inch,
)
doc.build(story)
print(OUT)
