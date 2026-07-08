from pathlib import Path

from fpdf import FPDF

from config import REPORT_DIR

WINDOWS_CJK_FONT_CANDIDATES = [
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("C:/Windows/Fonts/simfang.ttf"),
    Path("C:/Windows/Fonts/simkai.ttf"),
    Path("C:/Windows/Fonts/simsunb.ttf"),
]


def resolve_pdf_font_path() -> Path:
    # 优先走系统自带中文字体，省得额外打包字体文件，也能避开 PDF 中文乱码问题。
    for candidate in WINDOWS_CJK_FONT_CANDIDATES:
        if candidate.exists():
            return candidate
    raise RuntimeError(
        "No supported Chinese font was found under C:/Windows/Fonts. "
        "Expected one of: simhei.ttf, simfang.ttf, simkai.ttf, simsunb.ttf."
    )


def save_text_to_pdf(text: str, filename: str = "knowledge_report.pdf") -> str:
    """Save generated text to a PDF report file."""
    safe_name = "".join(ch for ch in filename if ch.isalnum() or ch in ("-", "_", "."))
    if not safe_name.endswith(".pdf"):
        safe_name = f"{safe_name}.pdf"

    path = REPORT_DIR / safe_name
    font_path = resolve_pdf_font_path()
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("KnowledgeAssistantCJK", "", str(font_path), uni=True)
    pdf.set_font("KnowledgeAssistantCJK", size=12)
    # 空行也要占位写进去，不然导出的段落结构会被吃掉。
    for line in text.splitlines():
        pdf.multi_cell(0, 8, line or " ")
    pdf.output(str(path))
    return str(Path(path).resolve())
