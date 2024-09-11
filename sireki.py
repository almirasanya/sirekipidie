import requests
import json
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import os
from google.oauth2 import service_account

# Ambil JSON dari environment variable
credentials_json = os.getenv('CREDENTIALS')

if credentials_json:
    # Parse JSON ke dictionary
    credentials_info = json.loads(credentials_json)

    # Buat credentials dari dictionary
    creds = service_account.Credentials.from_service_account_info(credentials_info)

    # Lanjutkan dengan konfigurasi Google Sheets
    # Misalnya:
    # client = gspread.authorize(creds)
else:
    raise ValueError("Environment variable 'GOOGLE_CREDENTIALS' tidak ditemukan.")
    
# Mengatur tema warna dan gaya
st.markdown(
    """
    <style>
    /* Mengatur warna sidebar */
    .css-1d391kg {
        background-color: #2F4F4F !important; /* Warna abu-abu tua */
    }
    
    /* Mengatur warna header */
    .css-1v0v2d3 { /* Ganti dengan class header yang benar jika berbeda */
        background-color: #003366 !important; /* Warna biru donker */
        color: white !important;
    }
    
    /* Mengatur warna teks dan link di sidebar */
    .css-1d391kg a {
        color: #4B9CDB !important;
        font-size: 16px !important;
    }

    .css-1d391kg a:hover {
        color: #003366 !important; /* Warna biru donker saat hover */
    }

    /* Mengatur tampilan utama */
    .css-1f2c1hf { /* Ganti dengan class tampilan utama yang benar jika berbeda */
        background-color: #D3D3D3 !important; /* Warna abu-abu terang untuk tampilan utama */
    }

    /* Mengatur ukuran dan posisi logo */
    .css-1a54z77 { /* Ganti dengan class logo yang benar jika berbeda */
        display: block;
        margin-left: auto;
        margin-right: auto;
        width: 100%;
        max-width: 150px; /* Batas maksimal ukuran logo */
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Menambahkan logo BPS dan tulisan di sidebar
logo_path = "bps_logo.png"  # Pastikan path logo sesuai
st.sidebar.image(
    logo_path,
    width=80,
    use_column_width=False,
)  # Mengatur ukuran logo menjadi lebih kecil (80px)
st.sidebar.markdown(
    "<h2 style='text-align: center;'>SIREKI - BPS Kabupaten Pidie</h2>",
    unsafe_allow_html=True,
)

# Pilihan menu di sidebar
page = st.sidebar.selectbox(
    "Pilih Halaman", ["Input Survei", "Dashboard Progres", "Petugas"]
)


# Fungsi untuk mengatur akses Google Sheets
def configure_google_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    spreadsheet_id = (
        "1589Us7yAhYZH_AWTlKackgUkNtklbwYpPEeadscgXBM"  # Ganti dengan ID Spreadsheet
    )
    sheet = client.open_by_key(spreadsheet_id)
    return sheet


def get_sheet_names(sheet):
    return [worksheet.title for worksheet in sheet.worksheets()]


def get_worksheet(sheet, name):
    try:
        return sheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        return None


def create_new_sheet(sheet, name):
    return sheet.add_worksheet(title=name, rows="100", cols="20")


def add_sample_count_column(worksheet):
    try:
        headers = worksheet.row_values(1)
        if "Jumlah Sampel Selesai Data" not in headers:
            # Add the new column in the 7th position (column G)
            worksheet.add_cols(1)
            worksheet.update_cell(1, 7, "Jumlah Sampel Selesai Data")
    except Exception as e:
        st.error(f"Kesalahan dalam menambahkan kolom: {e}")


def handle_special_values(df):
    # Convert special float values to strings
    def convert(value):
        if isinstance(value, float):
            if value == float("inf") or value == float("-inf") or pd.isna(value):
                return str(value)
        elif isinstance(value, pd.Timestamp):
            return value.strftime("%Y-%m-%d")  # Convert Timestamp to string
        return value

    return df.applymap(convert)


# Fungsi untuk mengunggah data ke Google Sheets
def upload_to_google_sheets(df, worksheet):
    try:
        worksheet.clear()
        df = handle_special_values(df)
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        st.success("Data berhasil disimpan ke Google Sheets!")
    except Exception as e:
        st.error(f"Terjadi kesalahan saat menyimpan data: {e}")


# Fungsi untuk mengatur pengiriman pengingat
def schedule_reminders(row, phone_number, api_key):
    try:
        start_date = datetime.strptime(row["Tanggal Mulai"], "%Y-%m-%d")
        end_date = datetime.strptime(row["Tanggal Selesai"], "%Y-%m-%d")
        total_days = (end_date - start_date).days

        # Reminder 1: Hari ke-2
        reminder_1_date = start_date + timedelta(days=2)
        if reminder_1_date <= datetime.today():
            reminder_1_message = (
                f"_*Ini adalah pesan yang dibuat secara otomatis dari BPS Kabupaten Pidie*_\n\n"
                f"*Reminder Ke-1:* \n\n"
                f"Kepada {row['Nama Petugas']},\n\n"
                f"Ini adalah pengingat tentang tugas survei Anda pada:\n\n"
                f"Survei yang Diikuti: {row['Survei yang Diikuti']}\n\n"
                f"Tanggal Mulai: {row['Tanggal Mulai']}\n"
                f"Tanggal Selesai: {row['Tanggal Selesai']}\n"
                f"Jangan lupa mengisi progres pendataan hari ini!\n\n"
                f"Link input Progres: http://link-survei.com/input/{row['Nomor Telepon']}"
            )
            send_whatsapp_message_fonnte(phone_number, reminder_1_message, api_key)

        # Reminder 2: 4 hari sebelum tanggal selesai
        reminder_2_date = end_date - timedelta(days=4)
        if reminder_2_date <= datetime.today():
            reminder_2_message = (
                f"*Reminder 2:* Survey akan segera berakhir, pastikan progres pendataan sudah maksimal!\n\n"
                f"Tanggal Selesai: {row['Tanggal Selesai']}\n"
                f"Link input: http://link-survei.com/input/{row['Nomor Telepon']}"
            )
            send_whatsapp_message_fonnte(phone_number, reminder_2_message, api_key)

        # Reminder 3: 1 hari sebelum tanggal selesai
        reminder_3_date = end_date - timedelta(days=1)
        if reminder_3_date <= datetime.today():
            reminder_3_message = (
                f"*Reminder 3:* 1 hari lagi sebelum survei selesai!\n\n"
                f"Pastikan semua data sudah diinput.\n"
                f"Link input: http://link-survei.com/input/{row['Nomor Telepon']}"
            )
            send_whatsapp_message_fonnte(phone_number, reminder_3_message, api_key)

    except Exception as e:
        st.error(f"Kesalahan dalam penjadwalan reminder: {e}")


# Menampilkan konten berdasarkan halaman yang dipilih
if page == "Input Survei":
    st.header("Upload Data Survei")

    # Menambahkan template Excel untuk diunduh
    st.markdown("#### Unduh Template Survei")
    with open("template_survei.xlsx", "rb") as file:
        st.download_button(
            label="Unduh Template Excel",
            data=file,
            file_name="template_survei.xlsx",
            mime="application/vnd.ms-excel",
        )
    st.text("Catatan!!")
    st.text("1. Untuk format Tanggal (YYYY-MM-DD)")
    st.text("2. Untun Nomor Telp di mulai dengan 628xxxxxxxx")

    # Input nama survei
    survey_name = st.text_input("Masukkan Nama Survei")
    if survey_name:
        sheet = configure_google_sheets()
        worksheet_names = get_sheet_names(sheet)

        if survey_name not in worksheet_names:
            st.warning(
                f"Sheet dengan nama '{survey_name}' tidak ditemukan. Membuat sheet baru."
            )
            worksheet = create_new_sheet(sheet, survey_name)
        else:
            worksheet = get_worksheet(sheet, survey_name)

        # Form untuk upload file
        uploaded_file = st.file_uploader("Unggah File Excel", type=["xlsx"])
        if uploaded_file:
            df = pd.read_excel(uploaded_file)
            upload_to_google_sheets(df, worksheet)
            add_sample_count_column(worksheet)

elif page == "Dashboard Progres":
    st.header("Dashboard Progres")

    # Input untuk memilih survei
    sheet = configure_google_sheets()
    worksheet_names = get_sheet_names(sheet)
    selected_survey = st.selectbox("Pilih Survei", worksheet_names)

    if selected_survey:
        worksheet = get_worksheet(sheet, selected_survey)
        if worksheet:
            # Ambil data petugas dan total sampel
            data = worksheet.get_all_records()
            df = pd.DataFrame(data)

            # Tampilkan tabel progres pendataan
            st.subheader("Tabel Progres Pendataan Survei")
            if not df.empty:
                # Hitung total sampel per petugas
                df["Jumlah Sampel"] = pd.to_numeric(
                    df["Jumlah Sampel"], errors="coerce"
                ).fillna(0)
                df["Jumlah Sampel Selesai Data"] = pd.to_numeric(
                    df["Jumlah Sampel Selesai Data"], errors="coerce"
                ).fillna(0)
                df["Progres"] = (
                    df["Jumlah Sampel Selesai Data"] / df["Jumlah Sampel"] * 100
                )

                st.write(
                    df[
                        [
                            "Nama Petugas",
                            "Jumlah Sampel",
                            "Jumlah Sampel Selesai Data",
                            "Progres",
                        ]
                    ]
                )

                # Grafik bar untuk progres pendataan
                st.subheader("Grafik Progress Pendataan Survei")
                fig = go.Figure()

                fig.add_trace(
                    go.Bar(x=df["Nama Petugas"], y=df["Progres"], name="Progres (%)")
                )

                fig.update_layout(
                    title="Grafik Progress Pendataan Survei",
                    xaxis_title="Nama Petugas",
                    yaxis_title="Progres (%)",
                    yaxis=dict(range=[0, 100]),
                )

                st.plotly_chart(fig)

                # Hitung keseluruhan progres survei
                total_samples = df["Jumlah Sampel"].sum()
                total_samples_collected = df["Jumlah Sampel Selesai Data"].sum()

                if total_samples > 0:
                    overall_progress_percentage = (
                        total_samples_collected / total_samples
                    ) * 100
                else:
                    overall_progress_percentage = 0

                # Tampilkan progres keseluruhan
                st.subheader("Progres Keseluruhan Survei")
                st.write(f"Total Jumlah Sampel: {total_samples}")
                st.write(
                    f"Total Jumlah Sampel yang Telah Dikumpulkan: {total_samples_collected}"
                )
                st.write(
                    f"Persentase Progres Keseluruhan: {overall_progress_percentage:.2f}%"
                )


elif page == "Petugas":
    st.header("Menu Petugas")
    sheet = configure_google_sheets()
    worksheet_names = get_sheet_names(sheet)

    selected_survey = st.selectbox("Pilih Survei", worksheet_names)
    if selected_survey:
        worksheet = get_worksheet(sheet, selected_survey)
        if worksheet:
            petugas_names = worksheet.col_values(
                1  # Assuming 'Nama Petugas' is in the first column
            )
            if "Nama Petugas" in petugas_names:
                petugas_names.remove("Nama Petugas")

            selected_petugas = st.selectbox("Pilih Nama Petugas", petugas_names)

            if selected_petugas:
                data = worksheet.get_all_records()
                petugas_data = [
                    row for row in data if row["Nama Petugas"] == selected_petugas
                ]

                if petugas_data:
                    st.write(pd.DataFrame(petugas_data))
                    # Add column for sample count if not already present
                    add_sample_count_column(worksheet)
                    # Input field for sample count
                    sample_count = st.number_input(
                        "Masukkan Jumlah Sampel yang Sudah di Data", min_value=0
                    )
                    if st.button("Simpan Jumlah Sampel"):
                        # Find the row index for the selected petugas
                        for i, row in enumerate(worksheet.get_all_records()):
                            if row["Nama Petugas"] == selected_petugas:
                                row_index = (
                                    i + 2
                                )  # Adjusting for 1-based index and header row
                                worksheet.update_cell(
                                    row_index, 7, sample_count  # Column G is index 7
                                )
                        st.success("Jumlah sampel berhasil disimpan.")
