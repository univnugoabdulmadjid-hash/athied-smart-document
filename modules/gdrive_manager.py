import json
import io
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive']

def get_gdrive_service():
    """Menginisialisasi koneksi Google Drive API menggunakan Service Account Secrets"""
    try:
        if "gdrive_service_account" in st.secrets:
            creds_info = dict(st.secrets["gdrive_service_account"])
            if "private_key" in creds_info:
                creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
            creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
            return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Koneksi Google Drive API gagal: {e}")
    return None

def save_to_gdrive(file_name, data_bytes, folder_id):
    """Menyimpan atau menimpa (overwrite) berkas proyek .athied langsung di Google Drive"""
    service = get_gdrive_service()
    if not service:
        return False, "Layanan Google Drive tidak siap."

    if not file_name.endswith(".athied"):
        file_name += ".athied"

    try:
        # Cari apakah berkas dengan nama yang sama sudah ada di folder Google Drive
        query = f"'{folder_id}' in parents and name = '{file_name}' and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)").execute()
        items = results.get('files', [])

        media = MediaIoBaseUpload(io.BytesIO(data_bytes), mimetype='application/json', resumable=True)

        if items:
            # Jika file sudah ada, lakukan penimpaan (update/overwrite)
            file_id = items[0]['id']
            service.files().update(fileId=file_id, media_body=media).execute()
            return True, f"Berkas '{file_name}' berhasil diperbarui/ditimpa di Google Drive!"
        else:
            # Jika file belum ada, buat file baru
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            return True, f"Berkas '{file_name}' berhasil disimpan baru di Google Drive!"
    except Exception as e:
        return False, f"Gagal menyimpan ke Google Drive: {e}"

def list_gdrive_files(folder_id):
    """Mengambil daftar seluruh berkas proyek .athied yang ada di folder Google Drive"""
    service = get_gdrive_service()
    if not service:
        return []
    try:
        query = f"'{folder_id}' in parents and name ends with '.athied' and trashed = false"
        results = service.files().list(q=query, fields="files(id, name)", orderBy="name").execute()
        return results.get('files', [])
    except Exception as e:
        st.error(f"Gagal mengambil daftar proyek dari Google Drive: {e}")
        return []

def load_from_gdrive(file_id):
    """Memuat/membaca isi berkas .athied dari Google Drive ke dalam aplikasi"""
    service = get_gdrive_service()
    if not service:
        return None
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        fh.seek(0)
        content = fh.read().decode('utf-8')
        return json.loads(content)
    except Exception as e:
        st.error(f"Gagal memuat berkas dari Google Drive: {e}")
        return None
