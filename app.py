import streamlit as st
import cv2
import face_recognition
import sqlite3
import numpy as np
from pyzbar import pyzbar
import pandas as pd

# --- 1. DATABASE INITIALIZATION ---
def init_db():
    conn = sqlite3.connect('library.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (id INTEGER PRIMARY KEY, 
                  name TEXT, 
                  face_encoding BLOB, 
                  current_issue TEXT DEFAULT 'No', 
                  barcode TEXT DEFAULT NULL)''')
    conn.commit()
    conn.close()

init_db()

# --- 2. TRANSACTION LOGIC ---
def process_transaction(student_name, book_id):
    conn = sqlite3.connect('library.db')
    cur = conn.cursor()
    cur.execute("SELECT current_issue, barcode FROM students WHERE name=?", (student_name,))
    row = cur.fetchone()
    
    if row:
        status, existing_b = row
        if status == 'Yes':
            if existing_b == book_id:
                cur.execute("UPDATE students SET current_issue='No', barcode=NULL WHERE name=?", (student_name,))
                st.balloons()
                st.toast(f"✅ RETURNED: {book_id}")
            else:
                st.error(f"❌ {student_name} must return {existing_b} first!")
        else:
            cur.execute("UPDATE students SET current_issue='Yes', barcode=? WHERE name=?", (book_id, student_name))
            st.balloons()
            st.toast(f"📖 ISSUED: {book_id}")
        conn.commit()
    conn.close()

# --- 3. SIDEBAR NAVIGATION ---
st.sidebar.title("📚 Library Menu")
st.sidebar.write("🟢 **System Status:** Online")
st.sidebar.write("🤖 **AI Core:** Active (128D)")
menu = st.sidebar.radio("Navigate to:", ["👤 Registration", "🛒 Smart Kiosk", "📊 View Records"])

st.sidebar.markdown("---")
st.sidebar.caption("🚀 **Project Credits**")
st.sidebar.write("👤 **Developer:** Shubham Shukla")
st.sidebar.write("🤖 **AI Architect:** Google Gemini (2026)")

# --- PAGE 1: REGISTRATION ---
if menu == "👤 Registration":
    st.title("Student Enrollment")
    st.info("Register once. The system blocks duplicate faces.")
    
    reg_name = st.text_input("Enter Full Name")
    img_file = st.camera_input("Capture Face for Enrollment")
    
    if st.button("Finalize Registration") and reg_name and img_file:
        image = face_recognition.load_image_file(img_file)
        encs = face_recognition.face_encodings(image)
        
        if encs:
            new_enc = encs[0]
            conn = sqlite3.connect('library.db')
            cursor = conn.cursor()
            cursor.execute("SELECT name, face_encoding FROM students WHERE face_encoding IS NOT NULL")
            existing_data = cursor.fetchall()
            
            is_already_registered = False
            if existing_data:
                known_encs = [np.frombuffer(row[1], dtype=np.float64) for row in existing_data]
                matches = face_recognition.compare_faces(known_encs, new_enc, tolerance=0.4)
                if True in matches: is_already_registered = True

            if is_already_registered:
                st.error("🚨 DUPLICATE: You are already registered!")
            else:
                cursor.execute("INSERT INTO students (name, face_encoding) VALUES (?, ?)", 
                                (reg_name, new_enc.tobytes()))
                conn.commit()
                st.success(f"✅ {reg_name} registered!")
            conn.close()
        else:
            st.error("❌ No face detected. Please try again.")

# --- PAGE 2: SMART KIOSK ---
elif menu == "🛒 Smart Kiosk":
    st.title("AI Automated Circulation Hub")
    
    if 'verified_user' not in st.session_state:
        st.session_state.verified_user = None

    if st.session_state.verified_user is None:
        st.subheader("Step 1: Identify Face")
        kiosk_img = st.camera_input("Scan face to log in")

        if kiosk_img:
            # Load known faces
            conn = sqlite3.connect('library.db')
            rows = conn.cursor().execute("SELECT name, face_encoding FROM students WHERE face_encoding IS NOT NULL").fetchall()
            conn.close()

            if rows:
                known_names = [r[0] for r in rows]
                known_encodings = [np.frombuffer(r[1], dtype=np.float64) for r in rows]
                
                # Convert camera input to face encoding
                test_image = face_recognition.load_image_file(kiosk_img)
                test_encodings = face_recognition.face_encodings(test_image)

                if test_encodings:
                    matches = face_recognition.compare_faces(known_encodings, test_encodings[0], tolerance=0.45)
                    if True in matches:
                        st.session_state.verified_user = known_names[matches.index(True)]
                        st.rerun()
                    else:
                        st.error("Face not recognized. Please register first.")
                else:
                    st.warning("No face detected. Adjust lighting and try again.")
            else:
                st.warning("Database is empty. Please register students first.")

    else:
        # User is Verified
        st.success(f"Verified User: **{st.session_state.verified_user}**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Step 2: Book Entry")
            # For cloud barcode scanning, we use another camera input
            barcode_img = st.camera_input("Scan Book Barcode/QR")
            scanned_code = None
            
            if barcode_img:
                # Convert streamlit image to opencv format for pyzbar
                file_bytes = np.asarray(bytearray(barcode_img.read()), dtype=np.uint8)
                opencv_image = cv2.imdecode(file_bytes, 1)
                
                # Detect Barcode
                detected_codes = pyzbar.decode(opencv_image)
                if detected_codes:
                    scanned_code = detected_codes[0].data.decode('utf-8')
                    st.info(f"Scanned Code: {scanned_code}")
                else:
                    st.warning("No barcode detected in the photo.")

        with col2:
            st.subheader("Manual Entry")
            manual_code = st.text_input("Enter 8-Digit Barcode manually")
            
            final_code = scanned_code if scanned_code else manual_code
            
            if st.button("Confirm Transaction") and final_code:
                if len(final_code) >= 4: # Adjusted for flexibility
                    process_transaction(st.session_state.verified_user, final_code)
                    st.session_state.verified_user = None # Log out after transaction
                    st.rerun()
                else:
                    st.error("Invalid Barcode")
        
        if st.button("Log Out / Switch User"):
            st.session_state.verified_user = None
            st.rerun()

# --- PAGE 3: RECORDS ---
elif menu == "📊 View Records":
    st.title("Library Database")
    conn = sqlite3.connect('library.db')
    df = pd.read_sql_query("SELECT id, name, current_issue, barcode FROM students", conn)
    st.dataframe(df, use_container_width=True)
    conn.close()
