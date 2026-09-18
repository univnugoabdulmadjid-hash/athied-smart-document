import io
import re
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

def sanitize_text(text):
    """
    Membersihkan karakter kontrol tersembunyi yang dilarang dalam skema XML MS Word.
    """
    if not text:
        return ""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]', '', str(text))

def safe_add_runs(paragraph, text, is_bold=False, is_italic=False):
    """
    Memproses format bold (**teks**) dan italic (*teks*) menjadi Run Word asli
    secara aman tanpa menyisakan simbol asteris (*).
    """
    clean_input = sanitize_text(text)
    if not clean_input:
        return

    tokens = re.split(r'(\*\*.*?\*\*|\*.*?\*|_[^_]+_)', clean_input)
    for token in tokens:
        if not token:
            continue

        if token.startswith('**') and token.endswith('**') and len(token) > 4:
            r = paragraph.add_run(token[2:-2])
            r.bold = True
        elif (token.startswith('*') and token.endswith('*') and len(token) > 2) or (token.startswith('_') and token.endswith('_') and len(token) > 2):
            r = paragraph.add_run(token[1:-1])
            r.italic = True
        else:
            r = paragraph.add_run(token)
            if is_bold:
                r.bold = True
            if is_italic:
                r.italic = True

        r.font.name = 'Times New Roman'
        r.font.size = Pt(12)

def export_chapter_to_docx(chapter_title, content_paragraphs):
    """
    Exporter Fail-Safe 100% Baku MS Word (Bebas Corrupt Error XML):
    - Margin Standar Akademis: Top 4cm, Left 4cm, Bottom 3cm, Right 3cm
    - Font: Times New Roman 12pt, Spasi 1.15, Indent 1.27cm
    """
    doc = Document()

    # Layout Margin (4-3-4-3 cm)
    for sec in doc.sections:
        sec.top_margin = Cm(4)
        sec.left_margin = Cm(4)
        sec.bottom_margin = Cm(3)
        sec.right_margin = Cm(3)

    # Style Dasar
    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(12)

    # Judul Bab (Tengah & Bold)
    if chapter_title:
        p_head = doc.add_paragraph()
        p_head.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_head.paragraph_format.line_spacing = 1.15
        p_head.paragraph_format.space_after = Pt(12)
        p_head.paragraph_format.first_line_indent = Cm(0)
        safe_add_runs(p_head, chapter_title.upper().replace("#", "").strip(), is_bold=True)

    if isinstance(content_paragraphs, str):
        lines = content_paragraphs.split('\n')
    else:
        lines = content_paragraphs

    i = 0
    n = len(lines)

    while i < n:
        raw_line = lines[i].strip()
        if not raw_line:
            i += 1
            continue

        # PEMROSESAN TABEL MARKDOWN FAIL-SAFE
        if raw_line.startswith('|') and raw_line.endswith('|'):
            table_data = []
            while i < n and lines[i].strip().startswith('|') and lines[i].strip().endswith('|'):
                row_str = lines[i].strip()
                # Abaikan baris pembatas (|---|---|)
                if not re.match(r'^\|[\s\:\-\|]+\|$', row_str):
                    cells = [c.strip() for c in row_str.split('|')[1:-1]]
                    if cells:
                        table_data.append(cells)
                i += 1

            if table_data:
                try:
                    max_cols = max(len(r) for r in table_data)
                    tbl = doc.add_table(rows=len(table_data), cols=max_cols)
                    tbl.style = 'Table Grid'
                    for r_idx, r_cells in enumerate(table_data):
                        for c_idx, cell_txt in enumerate(r_cells):
                            if c_idx < max_cols:
                                cell_p = tbl.cell(r_idx, c_idx).paragraphs[0]
                                cell_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                                cell_p.paragraph_format.line_spacing = 1.0
                                cell_p.paragraph_format.space_before = Pt(2)
                                cell_p.paragraph_format.space_after = Pt(2)
                                safe_add_runs(cell_p, cell_txt, is_bold=(r_idx == 0))
                except Exception:
                    # Fallback aman jika struktur tabel bermasalah
                    for r_cells in table_data:
                        p_fb = doc.add_paragraph()
                        p_fb.paragraph_format.line_spacing = 1.15
                        p_fb.paragraph_format.space_after = Pt(4)
                        safe_add_runs(p_fb, " | ".join(r_cells))
            continue

        # PEMROSESAN SUBHEADING & PARAGRAF BIASA
        is_h = raw_line.startswith('#')
        clean_l = re.sub(r'^#+\s*', '', raw_line) if is_h else raw_line

        is_sub = is_h or (
            any(clean_l.startswith(prefix) for prefix in ["A.", "B.", "C.", "D.", "E.", "F.", "G.", "1.", "2.", "3.", "4.", "5.", "Tabel ", "Gambar "]) 
            and len(clean_l) < 120
        )

        p = doc.add_paragraph()
        if is_sub:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_before = Pt(8)
            p.paragraph_format.space_after = Pt(4)
            p.paragraph_format.first_line_indent = Cm(0)
            safe_add_runs(p, clean_l, is_bold=True)
        elif clean_l.lower().startswith("sumber"):
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.first_line_indent = Cm(0)
            safe_add_runs(p, clean_l, is_italic=True)
        else:
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.first_line_indent = Cm(1.27)
            safe_add_runs(p, clean_l)

        i += 1

    file_stream = io.BytesIO()
    doc.save(file_stream)
    return file_stream.getvalue()