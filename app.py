import streamlit as st
import pandas as pd
import json
import os
import re
from config.system_prompts import PROMPT_KARYA_ILMIAH_HUKUM, PROMPT_BUKU_AKADEMIK
from modules.ai_engine import generate_section_content_with_pdf, chat_interactive_agent
from modules.api_references import fetch_openalex_articles, fetch_crossref_articles, fetch_google_books, generate_ris_string
from modules.docx_exporter import export_chapter_to_docx
from modules.gdrive_manager import save_to_gdrive, list_gdrive_files, load_from_gdrive

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & SECURE LOGIN SYSTEM
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Athied Smart Document",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS Tampilan Akademis
st.markdown("""
    <style>
    .stApp {
        background-color: #0F172A;
        color: #E2E8F0;
    }
    .word-preview {
        font-family: 'Times New Roman', Times, serif;
        font-size: 12pt;
        line-height: 1.15;
        text-align: justify;
        background-color: #FFFFFF;
        color: #111111;
        padding: 40px;
        border: 1px solid #CBD5E1;
        border-radius: 6px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        white-space: pre-wrap;
    }
    .word-paragraph {
        text-indent: 1.27cm;
        margin-bottom: 6pt;
    }
    .subheading-text {
        font-weight: bold;
        text-indent: 0cm;
        margin-top: 12pt;
        margin-bottom: 4pt;
    }
    </style>
""", unsafe_allow_html=True)

# Sistem Keamanan Password Akses
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("⚖️ Athied Smart Document - Portal Akses Private")
    st.caption("Aplikasi Pembuat & Revisi Dokumen Hukum / Akademik Terstruktur")

    input_pass = st.text_input("Masukkan Password Akses App:", type="password")
    if st.button("Masuk"):
        target_pass = st.secrets.get("APP_PASSWORD", "admin")
        if input_pass == target_pass:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Password salah. Akses ditolak.")
    st.stop()

# -----------------------------------------------------------------------------
# 2. SESSION STATE INITIALIZATION
# -----------------------------------------------------------------------------
if "draft_chapters" not in st.session_state:
    st.session_state.draft_chapters = {}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = {}
if "collected_references" not in st.session_state:
    st.session_state.collected_references = []
if "concept_data" not in st.session_state:
    st.session_state.concept_data = {}
if "locked_title" not in st.session_state:
    st.session_state.locked_title = ""
if "locked_outline" not in st.session_state:
    st.session_state.locked_outline = []
if "current_project_name" not in st.session_state:
    st.session_state.current_project_name = "Proyek_Disertasi_1"

# -----------------------------------------------------------------------------
# 3. SIDEBAR PANEL (MANAJEMEN PROYEK TERPUSAT - GOOGLE DRIVE)
# -----------------------------------------------------------------------------
with st.sidebar:
    if os.path.exists("profile.png"):
        st.image("profile.png", use_container_width=True)
    else:
        st.title("⚖️ Athied Smart Doc")

    st.caption("Kepakaran Terkunci: HAN Prosedural & Perbandingan Hukum")
    st.divider()

    api_key_active = st.secrets.get("GEMINI_API_KEY", "")
    gdrive_folder_id = st.secrets.get("GDRIVE_FOLDER_ID", "")

    st.subheader("☁️ Manajemen Proyek Google Drive")

    # Kolom Input Nama Proyek
    project_name_input = st.text_input(
        "Nama Berkas Proyek", 
        value=st.session_state.current_project_name, 
        help="Nama proyek yang tersimpan di Google Drive"
    )
    st.session_state.current_project_name = project_name_input.strip().replace(" ", "_")

    # Menyiapkan Struktur Data Proyek
    current_project_data = {
        "project_name": st.session_state.current_project_name,
        "draft_chapters": st.session_state.draft_chapters,
        "chat_history": st.session_state.chat_history,
        "concept_data": st.session_state.concept_data,
        "references": st.session_state.collected_references,
        "locked_title": st.session_state.locked_title,
        "locked_outline": st.session_state.locked_outline
    }
    json_project_bytes = json.dumps(current_project_data, indent=2, ensure_ascii=False).encode('utf-8')

    # SATU TOMBOL TUNGGAL UTAMA SIMPAN PROYEK KE GOOGLE DRIVE
    if st.button("💾 Simpan Proyek ke Google Drive", type="primary", use_container_width=True):
        if not gdrive_folder_id:
            st.error("GDRIVE_FOLDER_ID belum dikonfigurasi di Secrets.")
        else:
            with st.spinner("Menyimpan & menimpa berkas di Google Drive..."):
                success, msg = save_to_gdrive(
                    st.session_state.current_project_name, 
                    json_project_bytes, 
                    gdrive_folder_id
                )
                if success:
                    st.success(msg)
                else:
                    st.error(msg)

    if st.button("🔄 Mulai Proyek Baru", use_container_width=True):
        st.session_state.draft_chapters = {}
        st.session_state.chat_history = {}
        st.session_state.collected_references = []
        st.session_state.concept_data = {}
        st.session_state.locked_title = ""
        st.session_state.locked_outline = []
        st.session_state.current_project_name = "Proyek_Disertasi_Baru"
        st.rerun()

    st.divider()
    st.markdown("**📂 Buka Proyek dari Google Drive:**")
    
    if gdrive_folder_id:
        gdrive_files = list_gdrive_files(gdrive_folder_id)
        if gdrive_files:
            file_options = {f['name']: f['id'] for f in gdrive_files}
            selected_file_name = st.selectbox("Pilih Proyek Tersimpan:", list(file_options.keys()))
            
            if st.button("📂 Muat Proyek dari Cloud", use_container_width=True):
                with st.spinner("Mengunduh data proyek dari Google Drive..."):
                    file_id = file_options[selected_file_name]
                    data_load = load_from_gdrive(file_id)
                    
                    if data_load:
                        st.session_state.draft_chapters = data_load.get("draft_chapters", {})
                        st.session_state.chat_history = data_load.get("chat_history", {})
                        st.session_state.concept_data = data_load.get("concept_data", {})
                        st.session_state.collected_references = data_load.get("references", [])
                        st.session_state.locked_title = data_load.get("locked_title", "")
                        st.session_state.locked_outline = data_load.get("locked_outline", [])
                        st.session_state.current_project_name = selected_file_name.replace(".athied", "")
                        st.success(f"Proyek '{selected_file_name}' Berhasil Dimuat!")
                        st.rerun()
        else:
            st.caption("Belum ada berkas proyek tersimpan di folder Google Drive.")
    else:
        st.caption("Konfigurasi Google Drive belum aktif.")

    st.divider()
    st.caption("🔒 Status Engine Terkunci:")
    st.caption("• Model Tab 1: Gemini 3.1 Pro (Analisis SOTA & Gap)")
    st.caption("• Model Tab 2: Gemini 3.8 Flash (Drafting & Autoreferensi)")

# -----------------------------------------------------------------------------
# 4. MAIN NAVIGATION TABS
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs([
    "💡 TAB 1: Inisiasi & Konsep (SOTA, Judul & Outline)", 
    "📝 TAB 2: Athied Smart Workspace", 
    "📚 TAB 3: Exporter & Plain Text RIS"
])

# =============================================================================
# TAB 1: INISIASI, SOTA, PEMILIHAN JUDUL & PERSETUJUAN OUTLINE
# =============================================================================
with tab1:
    st.header("Modul Analisis SOTA, Penentuan Judul & Outline Bab")
    st.caption("Tahap inisiasi untuk merumuskan Research Gap, menyepakati Judul utama, dan mengunci Outline Bab sebelum masuk ke lembar kerja.")

    col_a, col_b = st.columns(2)
    with col_a:
        doc_category = st.selectbox("Kategori Dokumen Utama", [
            "Disertasi Hukum (Doktoral - Level Maestro)",
            "Tesis Hukum (Magister)",
            "Skripsi Hukum (Sarjana)",
            "Buku Referensi Akademik",
            "Buku Monograf Akademik",
            "Buku Ajar Akademik",
            "Dokumen Akademik & Kelembagaan"
        ])
        methodology_type = st.radio("Tipe Penelitian Hukum", ["Penelitian Hukum Normatif", "Penelitian Hukum Empiris/Sosiologis"])
        scale_scope = st.selectbox("Skala Penelitian", ["Lokal / Wilayah", "Nasional", "Internasional"])

    with col_b:
        expertise_field = st.text_input("Bidang Kepakaran (Terkunci)", value="HAN Prosedural dan Perbandingan Hukum", disabled=True)

        if methodology_type == "Penelitian Hukum Normatif":
            phenomenon_label = "Isu Hukum / Kekosongan Norma / Antinomi Hukum (Opsional untuk Normatif)"
            phenomenon_placeholder = "Masukkan isu pertentangan norma, kekosongan hukum, atau kekaburan doktrin (opsional)..."
        else:
            phenomenon_label = "Fenomena Hukum / Data Lapangan (Wajib untuk Empiris)"
            phenomenon_placeholder = "Masukkan fenomena hukum riil di masyarakat atau data masalah lapangan..."

        initial_phenomenon = st.text_area(phenomenon_label, placeholder=phenomenon_placeholder)

    st.subheader("📁 Unggah Berkas PDF SOTA (Artikel Jurnal / Hasil Scan Buku)")
    uploaded_sota_pdfs = st.file_uploader("Pilih satu atau beberapa berkas PDF sekaligus (Dibebaskan dari aturan 5 tahun)", type=["pdf"], accept_multiple_files=True)

    if st.button("🚀 1. Pindai PDF & Analisis Research Gap", type="primary"):
        if methodology_type == "Penelitian Hukum Empiris/Sosiologis" and not initial_phenomenon:
            st.warning("Penelitian Hukum Empiris mewajibkan pengisian fenomena / data lapangan.")
        else:
            with st.spinner("Memindai berkas PDF & menganalisis SOTA menggunakan Gemini 3.1 Pro..."):
                pdf_bytes_list = []
                if uploaded_sota_pdfs:
                    for pdf_file in uploaded_sota_pdfs:
                        pdf_bytes_list.append(pdf_file.read())

                prompt_analysis = f"""
                Lakukan analisis SOTA dan Research Gap mendalam berdasarkan data berikut:
                - Kategori Dokumen: {doc_category} ({methodology_type}, Skala: {scale_scope})
                - Kepakaran Terkunci: {expertise_field}
                - Fenomena/Isu Hukum: {initial_phenomenon if initial_phenomenon else 'Analisis berbasis problem norma/doktrin'}

                TUGAS UTAMA BERKAS PDF:
                1. Pemetaan Research Gap secara kritis dari PDF SOTA yang diunggah.
                2. Formulasi 3 Rekomendasi Judul (DILARANG KERAS MENGGUNAKAN TANDA TITIK DUA (:). Judul WAJIB disusun mengalir utuh secara natural. Jika Buku Referensi/Monograf, gunakan judul bervariasi, komersial, dan menarik minat pembaca. Jika Disertasi Hukum, gunakan diksi doktrinal puncak).
                3. Penentuan Kebaharuan Ilmiah (Doctrinal Novelty) yang sangat unik.
                4. Rekomendasi Teori Hukum (Grand, Middle, Applied) & Adagium Hukum Baku.
                """

                sys_prompt = PROMPT_KARYA_ILMIAH_HUKUM if "Hukum" in doc_category or "Disertasi" in doc_category or "Tesis" in doc_category or "Skripsi" in doc_category else PROMPT_BUKU_AKADEMIK
                result = generate_section_content_with_pdf(
                    api_key_active, 
                    sys_prompt, 
                    prompt_analysis, 
                    pdf_bytes_list=pdf_bytes_list, 
                    model_name="gemini-3.1-pro-preview"
                )

                st.session_state.concept_data = {
                    "category": doc_category,
                    "methodology": methodology_type,
                    "phenomenon": initial_phenomenon,
                    "analysis": result
                }
                st.success("Analisis Konsep & SOTA Berhasil Disusun!")
                st.rerun()

    # HASIL ANALISIS SOTA & FORM PEMILIHAN JUDUL / OUTLINE
    if st.session_state.concept_data.get("analysis"):
        st.divider()
        st.subheader("📌 Hasil Analisis SOTA, Research Gap, & Novelty (Tersimpan)")
        st.markdown(st.session_state.concept_data["analysis"])

        st.divider()
        st.subheader("🎯 2. Pemilihan Judul Utama & Penyusunan Outline Bab")

        selected_title_input = st.text_input(
            "Ketik atau Salin Judul Utama yang Disepakati dari Rekomendasi AI di Atas (Tanpa Titik Dua):",
            value=st.session_state.locked_title,
            placeholder="Contoh: Pengawasan Hukum Administrasi terhadap Transaksi Komoditas Digital dan Implikasi Perlindungan Hukum Subjek Administrasi"
        )

        col_out1, col_out2 = st.columns(2)
        with col_out1:
            if st.button("📐 Buatkan Draf Outline Bab", type="primary"):
                if not selected_title_input:
                    st.warning("Masukkan atau pilih judul terlebih dahulu.")
                else:
                    with st.spinner("Merumuskan struktur bab baku..."):
                        prompt_outline = f"""
                        Buatkan draf daftar bab (outline) baku untuk dokumen kategori: {doc_category}.
                        Judul Disepakati: {selected_title_input}

                        Aturan Jumlah & Struktur Bab:
                        - Jika Karya Ilmiah Hukum (Skripsi/Tesis/Disertasi): WAJIB persis 5 Bab (BAB I PENDAHULUAN, BAB II KAJIAN TEORETIS, BAB III METODE PENELITIAN, BAB IV HASIL DAN PEMBAHASAN, BAB V KESIMPULAN).
                        - Jika Buku Referensi: Buatkan minimal 8 - 10 Bab komprehensif.
                        - Jika Buku Monograf: Buatkan minimal 5 - 7 Bab spesifik.
                        - Jika Buku Ajar: Buatkan 12 - 14 Bab sesuai RPS perkuliahan.

                        Output HANYA berupa daftar nama bab (satu bab per baris) tanpa penjelasan lain.
                        """
                        sys_prompt = PROMPT_KARYA_ILMIAH_HUKUM if "Hukum" in doc_category else PROMPT_BUKU_AKADEMIK
                        outline_res = generate_section_content_with_pdf(api_key_active, sys_prompt, prompt_outline, model_name="gemini-3.8-flash")

                        parsed_chapters = [line.strip() for line in outline_res.split('\n') if line.strip()]
                        st.session_state.temp_outline = parsed_chapters
                        st.session_state.locked_title = selected_title_input
                        st.rerun()

        active_outline = st.session_state.get("temp_outline", st.session_state.locked_outline)
        if active_outline:
            st.markdown("**Review & Edit Daftar Bab yang Disepakati:**")
            outline_text_area = st.text_area("Struktur Bab (Satu bab per baris):", value="\n".join(active_outline), height=200)

            if st.button("🔒 Kunci Konsep & Kirim ke Tab 2 Workspace", type="primary"):
                final_chapters = [line.strip() for line in outline_text_area.split('\n') if line.strip()]
                st.session_state.locked_title = selected_title_input
                st.session_state.locked_outline = final_chapters
                st.success("Judul & Outline Bab Berhasil Dikunci! Silakan beralih ke Tab 2 (Athied Smart Workspace).")
                st.rerun()

# =============================================================================
# TAB 2: ATHIED SMART WORKSPACE
# =============================================================================
with tab2:
    st.subheader("Athied Smart Workspace")

    if st.session_state.locked_title:
        st.info(f"📖 **Judul Disepakati:** {st.session_state.locked_title}")

    tier1 = st.radio("Tier 1: Kategori Utama", ["Buku Akademik", "Karya Ilmiah Hukum", "Dokumen Akademik & Kelembagaan"], horizontal=True)

    if tier1 == "Buku Akademik":
        tier2 = st.selectbox("Tier 2: Jenis Buku", ["Buku Referensi Akademik", "Buku Monograf Akademik", "Buku Ajar Akademik"])
        fallback_chapters = [f"BAB {roman}" for roman in ["I", "II", "III", "IV", "V", "VI", "VII", "VIII"]]
    elif tier1 == "Karya Ilmiah Hukum":
        tier2 = st.selectbox("Tier 2: Jenis Karya Ilmiah", ["Disertasi Hukum (Doktoral - Level Maestro)", "Tesis Hukum (Magister)", "Skripsi Hukum (Sarjana)"])
        fallback_chapters = ["BAB I PENDAHULUAN", "BAB II KAJIAN TEORETIS", "BAB III METODE PENELITIAN", "BAB IV HASIL DAN PEMBAHASAN", "BAB V KESIMPULAN"]
    else:
        tier2 = st.selectbox("Tier 2: Jenis Dokumen Tata Kelola", ["Statuta Perguruan Tinggi", "Rencana Strategis (Renstra)", "Standard Operating Procedure (SOP)"])
        fallback_chapters = ["BAGIAN I PENDAHULUAN", "BAGIAN II TATA KELOLA", "BAGIAN III PROSEDUR & SUBSTANSI", "BAGIAN IV PENUTUP"]

    active_chapters = st.session_state.locked_outline if st.session_state.locked_outline else fallback_chapters

    selected_chapter = st.radio("Tier 3: Modul Bab Aktif", active_chapters, horizontal=True)
    st.divider()

    col_workspace, col_control = st.columns([2, 1])

    # AREA KERJA UTAMA (SISI KIRI)
    with col_workspace:
        st.subheader(f"📌 {selected_chapter}")
        chapter_key = f"{tier1}_{tier2}_{selected_chapter}"
        current_text = st.session_state.draft_chapters.get(chapter_key, "")
        words_count = len(current_text.split()) if current_text else 0

        tb_col1, tb_col2, tb_col3 = st.columns([1.5, 1.5, 1])
        with tb_col1:
            if st.button("🚀 Generate Bab (Autoreferensi API)", type="primary", use_container_width=True):
                is_high_academic = any(k in tier2 for k in ["Disertasi", "Referensi", "Monograf"])
                ref_limit_openalex = 15 if is_high_academic else 3
                ref_limit_crossref = 10 if is_high_academic else 2
                ref_limit_books = 5 if is_high_academic else 1
                target_word_str = "MINIMAL 7.000 KATA MURNI SUBSTANSI BAB (DI LUAR DAFTAR PUSTAKA/SITASI)" if is_high_academic else "komprehensif dan mendalam"

                with st.spinner(f"Menarik 30 referensi API (DOI Wajib, 2021-2026) & menyusun {selected_chapter}..."):
                    phenom_query = st.session_state.concept_data.get("phenomenon", st.session_state.locked_title or "Hukum Administrasi Negara Prosedural")

                    api_refs = (
                        fetch_openalex_articles(phenom_query, limit=ref_limit_openalex) + 
                        fetch_crossref_articles(phenom_query, limit=ref_limit_crossref) +
                        fetch_google_books(phenom_query, limit=ref_limit_books)
                    )
                    st.session_state.collected_references.extend(api_refs)

                    ref_text_context = json.dumps(api_refs, indent=2)
                    concept_ctx = st.session_state.concept_data.get("analysis", "")

                    prompt_gen = f"""
                    Susun draf utuh dan komprehensif untuk {selected_chapter} pada dokumen {tier2}.
                    Judul Disepakati: {st.session_state.locked_title}
                    Konteks Analisis SOTA / Konsep: {concept_ctx}
                    TARGET PANJANG NASKAH: {target_word_str}. DILARANG KERAS MENGHITUNG TEKS DAFTAR PUSTAKA UNTUK MEMENUHI TARGET KATA.

                    ATURAN KHUSUS SITASI APA STYLE 7TH EDITION (BODYNOTE + DAFTAR PUSTAKA):
                    1. WAJIB BODYNOTE DALAM TEKS: Setiap paragraf pada BAGIAN I dan BAGIAN II WAJIB menyisipkan sitasi bodynote di dalam kalimat/paragraf pembahasan dari data referensi riil yang tersedia di bawah. Contoh: (NamaPenulis, Tahun) atau Menurut NamaPenulis (Tahun)...
                    2. BAGIAN IV DAFTAR PUSTAKA BAB: Di bagian paling bawah bab, buatkan Daftar Pustaka lengkap dari seluruh referensi yang telah disitasi di dalam paragraf, dipisahkan secara tegas:
                       - A. BUKU (Disusun alfabetis A–Z berdasarkan nama belakang penulis)
                       - B. ARTIKEL JURNAL (Disusun alfabetis A–Z berdasarkan nama belakang penulis, LENGKAP DENGAN DOI RIIL)

                    STRUKTUR WAJIB PENULISAN BAB:
                    1. BAGIAN I PENDAHULUAN BAB: Latar belakang isu yang mengarahkan pembaca secara halus ke pokok bahasan bab ini (Wajib ada bodynote).
                    2. BAGIAN II PEMBAHASAN INTI DOKTRINAL: Minimal 5-7 sub-subbab komprehensif, menyandingkan data, Teori Hukum, Adagium, dan komparasi hukum (Wajib ada bodynote pada setiap paragraf).
                    3. BAGIAN III PENUTUP BAB: Kesimpulan bab dan jembatan alur ke bab berikutnya.
                    4. BAGIAN IV DAFTAR PUSTAKA BAB: Memuat MINIMAL 30 SITASI RIIL lengkap dari data API.

                    DATA REFERENSI RIIL TERSEDIA (WAJIB DISITASI BODYNOTE-NYA KE DALAM PARAGRAF):
                    {ref_text_context}

                    Ketentuan Khusus Penulisan:
                    - Integrasikan sitasi bodynote dari data API di atas secara alami dalam pembahasan di setiap subbab.
                    - Gaya penulisan formal-akademis mengalir, tanpa antitesis kaku, bebas gaya AI.
                    """

                    sys_prompt = PROMPT_KARYA_ILMIAH_HUKUM if tier1 == "Karya Ilmiah Hukum" else PROMPT_BUKU_AKADEMIK
                    new_content = generate_section_content_with_pdf(api_key_active, sys_prompt, prompt_gen, model_name="gemini-3.8-flash")
                    st.session_state.draft_chapters[chapter_key] = new_content
                    st.rerun()

        with tb_col2:
            if current_text:
                docx_bytes = export_chapter_to_docx(selected_chapter, current_text)
                clean_fn = re.sub(r'[^\w\s-]', '', selected_chapter)[:30].strip().replace(" ", "_")
                st.download_button(
                    label="📥 Unduh Bab Ini (.docx)",
                    data=docx_bytes,
                    file_name=f"{clean_fn}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )

        with tb_col3:
            st.metric(label="Jumlah Kata Total", value=f"{words_count} kata")

        # FITUR PERLUAS DRAF BAB
        if current_text:
            st.markdown("---")
            if st.button("➕ Perluas & Tambahkan Kedalaman Bab (+3.000 Kata Substansi)", type="secondary", use_container_width=True):
                with st.spinner("Memperluas pembahasan sub-subbab dan menambahkan analisis doktrinal baru..."):
                    expand_prompt = f"""
                    TEKS BAB SAAT INI:
                    {current_text}

                    TUGAS: Perluas dan perdalam pembahasan BAGIAN I, BAGIAN II, DAN BAGIAN III pada bab di atas agar substansinya jauh lebih komprehensif. Tambahkan analisis komparasi hukum, pembahasan teori doktrinal baru, dan sub-subbab baru dengan menyuntikkan bodynote APA Style (Nama, Tahun) pada paragraf baru. Target total mendalam dan komprehensif (7.000+ kata MURNI SUBSTANSI BAB, di luar daftar pustaka).
                    """
                    sys_prompt = PROMPT_KARYA_ILMIAH_HUKUM if tier1 == "Karya Ilmiah Hukum" else PROMPT_BUKU_AKADEMIK
                    expanded_text = generate_section_content_with_pdf(api_key_active, sys_prompt, expand_prompt, model_name="gemini-3.8-flash")
                    st.session_state.draft_chapters[chapter_key] = expanded_text
                    st.rerun()

        # Visual Formatted Word Preview
        st.markdown("### Pratinjau Teks (Formatted Word Standar)")
        if current_text:
            paragraphs_html = ""
            for p in current_text.split('\n'):
                p_clean = p.strip()
                if p_clean:
                    if any(p_clean.startswith(x) for x in ["A.", "B.", "C.", "D.", "E.", "1.", "2.", "3."]) and len(p_clean) < 80:
                        paragraphs_html += f"<div class='subheading-text'>{p_clean}</div>"
                    else:
                        paragraphs_html += f"<div class='word-paragraph'>{p_clean}</div>"
            st.markdown(f"<div class='word-preview'>{paragraphs_html}</div>", unsafe_allow_html=True)
        else:
            st.info("Draf bab ini belum dibuat. Klik 'Generate Bab (Autoreferensi API)' untuk memulai.")

    # PANEL KONTROL & CHAT AGENT REVISI (SISI KANAN)
    with col_control:
        st.subheader("🤖 Chat Assistant Revisi")
        st.caption("Instruksi revisi real-time untuk draf di sisi kiri.")

        if chapter_key not in st.session_state.chat_history:
            st.session_state.chat_history[chapter_key] = []

        chat_container = st.container(height=380)
        with chat_container:
            for message in st.session_state.chat_history[chapter_key]:
                with st.chat_message(message["role"]):
                    st.write(message["content"])

        user_msg = st.chat_input("Instruksi revisi paragraf...")
        if user_msg:
            st.session_state.chat_history[chapter_key].append({"role": "user", "content": user_msg})
            with st.spinner("Mengolah revisi draf..."):
                chat_context = f"""
                TEKS BAB SAAT INI:
                {st.session_state.draft_chapters.get(chapter_key, '')}

                INSTRUKSI REVISI PENGGUNA:
                {user_msg}

                Perbarui draf bab utuh di atas secara presisi sesuai instruksi. Pertahankan format sitasi bodynote dan hapus simbol markdown liar.
                """
                sys_prompt = PROMPT_KARYA_ILMIAH_HUKUM if tier1 == "Karya Ilmiah Hukum" else PROMPT_BUKU_AKADEMIK
                agent_response = chat_interactive_agent(
                    api_key_active, 
                    sys_prompt, 
                    st.session_state.chat_history[chapter_key], 
                    chat_context, 
                    model_name="gemini-3.8-flash"
                )
                st.session_state.chat_history[chapter_key].append({"role": "assistant", "content": "Draf telah diperbarui."})
                st.session_state.draft_chapters[chapter_key] = agent_response
                st.rerun()

# =============================================================================
# TAB 3: EXPORTER & PLAIN TEXT RIS DISPLAY
# =============================================================================
with tab3:
    st.header("Modul Sitasi RIS (Plain Text) & Ekspor Dokumen Utuh")

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.subheader("📋 Kode Plain Text RIS (Siap Salin ke Notepad / Mendeley)")
        st.caption("Seluruh referensi riil terdaftar (Filter DOI Wajib & Terbitan 2021-2026).")

        if st.session_state.collected_references:
            ris_plain_text = generate_ris_string(st.session_state.collected_references)

            st.text_area(
                "Salin Teks Kode RIS di bawah ini:", 
                value=ris_plain_text, 
                height=350,
                help="Blok seluruh teks ini ke Notepad laptop Anda."
            )

            st.download_button(
                label="📥 atau Unduh Berkas .RIS",
                data=ris_plain_text,
                file_name="referensi_athied_smart_doc.ris",
                mime="text/plain",
                type="primary"
            )
        else:
            st.info("Belum ada referensi yang tersimpan dari eksekusi bab di Tab 2.")

    with col_r2:
        st.subheader("📚 Penggabungan Seluruh Bab")
        st.caption("Menggabungkan seluruh draf bab yang dibuat menjadi satu berkas Word (.docx) utuh terformat baku.")

        if st.button("📚 Gabungkan Seluruh Bab & Unduh Naskah Utuh (.docx)", type="primary"):
            combined_text = ""
            if st.session_state.locked_title:
                combined_text += f"# {st.session_state.locked_title.upper()}\n\n"

            for ch_title, ch_content in st.session_state.draft_chapters.items():
                combined_text += f"\n\n=== {ch_title} ===\n\n" + ch_content

            if combined_text:
                full_docx_bytes = export_chapter_to_docx("NASKAH UTUH LENGKAP", combined_text)
                st.download_button(
                    label="📥 Unduh Naskah Utuh (.docx)",
                    data=full_docx_bytes,
                    file_name="Naskah_Utuh_Athied_Smart_Document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            else:
                st.warning("Belum ada draf bab yang dibuat di Tab 2.")
