import requests
import json

USER_EMAIL = "abdulmadjidpodungge@unugo.ac.id"
CURRENT_YEAR = 2026
MIN_YEAR = CURRENT_YEAR - 5  # Batas ketat 5 tahun terakhir (2021 - 2026)

def fetch_openalex_articles(query, limit=15):
    """
    Mengambil artikel ilmiah dari OpenAlex API.
    Syarat Ketat: WAJIB MEMILIKI DOI dan Terbitan 5 Tahun Terakhir (>= 2021).
    """
    url = f"https://api.openalex.org/works?search={query}&per_page={limit * 2}&mailto={USER_EMAIL}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data.get("results", []):
                doi_raw = item.get("doi", "")
                if not doi_raw:
                    continue

                pub_year = item.get("publication_year", 0)
                if pub_year < MIN_YEAR:
                    continue

                authors = [a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])]
                primary_loc = item.get("primary_location", {}) or {}
                source = primary_loc.get("source", {}) or {}

                results.append({
                    "title": item.get("display_name", "Tanpa Judul"),
                    "authors": authors,
                    "year": pub_year,
                    "journal": source.get("display_name", "Jurnal Tidak Terdaftar"),
                    "doi": doi_raw,
                    "url": doi_raw,
                    "type": "JOUR"
                })
                if len(results) >= limit:
                    break
            return results
    except Exception as e:
        print(f"Error OpenAlex API: {e}")
    return []

def fetch_crossref_articles(query, limit=10):
    """
    Mengambil artikel dari Crossref API.
    Syarat Ketat: WAJIB MEMILIKI DOI dan Terbitan 5 Tahun Terakhir (>= 2021).
    """
    url = f"https://api.crossref.org/works?query={query}&rows={limit * 2}&mailto={USER_EMAIL}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = []
            items = data.get("message", {}).get("items", [])
            for item in items:
                doi_val = item.get("DOI", "")
                if not doi_val:
                    continue

                issued_parts = item.get("issued", {}).get("date-parts", [[None]])[0]
                pub_year = issued_parts[0] if issued_parts and issued_parts[0] else 0
                
                if pub_year and pub_year < MIN_YEAR:
                    continue

                authors = []
                for a in item.get("author", []):
                    authors.append(f"{a.get('family', '')}, {a.get('given', '')}".strip(", "))

                title = item.get("title", ["Tanpa Judul"])[0] if item.get("title") else "Tanpa Judul"
                journal = item.get("container-title", [""])[0] if item.get("container-title") else ""
                doi_str = f"https://doi.org/{doi_val}"

                results.append({
                    "title": title,
                    "authors": authors,
                    "year": pub_year,
                    "journal": journal,
                    "doi": doi_str,
                    "publisher": item.get("publisher", ""),
                    "url": doi_str,
                    "type": "JOUR"
                })
                if len(results) >= limit:
                    break
            return results
    except Exception as e:
        print(f"Error Crossref API: {e}")
    return []

def fetch_google_books(query, limit=5, api_key=None):
    """
    Mengambil metadata buku dari Google Books API.
    """
    url = f"https://www.googleapis.com/books/v1/volumes?q={query}&maxResults={limit}"
    if api_key:
        url += f"&key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = []
            for item in data.get("items", []):
                info = item.get("volumeInfo", {})
                pub_date = info.get("publishedDate", "")
                pub_year = int(pub_date[:4]) if pub_date and pub_date[:4].isdigit() else ""

                results.append({
                    "title": info.get("title", "Tanpa Judul"),
                    "authors": info.get("authors", []),
                    "year": pub_year,
                    "publisher": info.get("publisher", "Penerbit Tidak Terdaftar"),
                    "isbn": info.get("industryIdentifiers", [{}])[0].get("identifier", "") if info.get("industryIdentifiers") else "",
                    "url": info.get("infoLink", ""),
                    "type": "BOOK"
                })
            return results
    except Exception as e:
        print(f"Error Google Books API: {e}")
    return []

def generate_ris_string(references):
    """
    Mengonversi daftar JSON referensi riil menjadi string format RIS (Plain Text baku).
    Dipisahkan secara tegas antara BUKU dan JURNAL (Lengkap DOI), tersusun Alfabetis A-Z.
    """
    books = [r for r in references if r.get("type") == "BOOK"]
    journals = [r for r in references if r.get("type") == "JOUR" and r.get("doi")]

    def get_sort_key(item):
        authors = item.get("authors", [])
        return authors[0].lower() if authors else item.get("title", "").lower()

    books.sort(key=get_sort_key)
    journals.sort(key=get_sort_key)

    ris_lines = []

    if books:
        ris_lines.append("=========================================")
        ris_lines.append("A. KELOMPOK REFERENSI BUKU (ALFABETIS A-Z)")
        ris_lines.append("=========================================\n")
        for ref in books:
            ris_lines.append("TY  - BOOK")
            for author in ref.get("authors", []):
                ris_lines.append(f"AU  - {author}")
            ris_lines.append(f"TI  - {ref.get('title', '')}")
            if ref.get("publisher"):
                ris_lines.append(f"PB  - {ref.get('publisher')}")
            if ref.get("year"):
                ris_lines.append(f"PY  - {ref.get('year')}")
            if ref.get("isbn"):
                ris_lines.append(f"SN  - {ref.get('isbn')}")
            if ref.get("url"):
                ris_lines.append(f"UR  - {ref.get('url')}")
            ris_lines.append("ER  - \n")

    if journals:
        ris_lines.append("=========================================")
        ris_lines.append("B. KELOMPOK ARTIKEL JURNAL (ALFABETIS A-Z WITH DOI)")
        ris_lines.append("=========================================\n")
        for ref in journals:
            ris_lines.append("TY  - JOUR")
            for author in ref.get("authors", []):
                ris_lines.append(f"AU  - {author}")
            ris_lines.append(f"TI  - {ref.get('title', '')}")
            if ref.get("journal"):
                ris_lines.append(f"JO  - {ref.get('journal')}")
            if ref.get("year"):
                ris_lines.append(f"PY  - {ref.get('year')}")
            ris_lines.append(f"DO  - {ref.get('doi')}")
            ris_lines.append(f"UR  - {ref.get('doi')}")
            ris_lines.append("ER  - \n")

    return "\n".join(ris_lines)