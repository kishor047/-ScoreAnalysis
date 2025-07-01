import streamlit as st
import pandas as pd
import pymongo
import gridfs
from io import BytesIO
import bcrypt
from pymongo import MongoClient

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client['result_system']
users_collection = db['users']
fs = gridfs.GridFS(db)

# Initialize session state variables
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None
    st.session_state.signup_mode = False
    st.session_state.uploaded_results = {}  # Stores uploaded results in memory for the session

# Function to handle login
def handle_login(username, password):
    user = users_collection.find_one({"username": username})
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password']):
        st.session_state.logged_in = True
        st.session_state.role = user['role']
        st.session_state.username = username
    else:
        st.error("Invalid username or password.")

# Function to handle signup
def handle_signup(new_username, new_password, role):
    existing_user = users_collection.find_one({"username": new_username})
    if existing_user:
        st.error("Username already exists! Try logging in.")
    else:
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        users_collection.insert_one({"username": new_username, "password": hashed_password, "role": role})
        st.success(f"Signup successful! You can now log in as {new_username}.")
        st.session_state.signup_mode = False

# Login/Signup UI
def login_signup_ui():
    st.title("Login / Signup")
    
    if st.session_state.signup_mode:
        # Signup form
        st.subheader("Signup")
        new_username = st.text_input("Create Username", key="signup_username")
        new_password = st.text_input("Create Password", type="password", key="signup_password")
        role = st.selectbox("Select Role", ["teacher", "student"], key="signup_role")

        if st.button("Signup"):
            if new_username and new_password:
                handle_signup(new_username, new_password, role)
            else:
                st.error("Please fill in both username and password.")

        if st.button("Back to Login"):
            st.session_state.signup_mode = False

    else:
        # Login form
        st.subheader("Login")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Login"):
            if username and password:
                handle_login(username, password)
            else:
                st.error("Please fill in both username and password.")

        if st.button("Signup"):
            st.session_state.signup_mode = True

# Save CSV file to MongoDB GridFS
def save_csv_to_mongodb(year, dept, semester, file_content):
    file_id = fs.put(file_content, filename=f"{year}_{dept}_{semester}.csv")
    return file_id

# Export to CSV or Excel functionality
def export_file(dataframe, file_type):
    if file_type == 'CSV':
        return dataframe.to_csv(index=False).encode('utf-8')
    elif file_type == 'Excel':
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            dataframe.to_excel(writer, index=False, sheet_name='Sheet1')
        return output.getvalue()

# Teacher's Dashboard for CSV Upload and Result Analysis
def teacher_dashboard():
    st.title(f"Welcome, {st.session_state.username} (Teacher)")
    
    # Teacher inputs the year, department, and semester
    year = st.text_input("Enter Year (e.g., FE/ SE/TE/BE)")
    dept = st.text_input("Enter Department (e.g., CS/IT)")
    semester = st.text_input("Enter Semester (e.g., I/II)")

    # Upload CSV file for the specific year, dept, and semester
    uploaded_file = st.file_uploader("Upload your result CSV file", type="csv")
    
    if uploaded_file is not None:
        if year and dept and semester:
            df = pd.read_csv(uploaded_file)
            df['GRADE'] = pd.to_numeric(df['GRADE'], errors='coerce')  # Convert GRADE to numeric

            # Save the uploaded CSV file to MongoDB
            save_csv_to_mongodb(year, dept, semester, uploaded_file.getvalue())
            st.success(f"CSV file uploaded and saved for {year} {dept} {semester}.")

            # Store the uploaded file in session state
            st.session_state.uploaded_results[f"{year}_{dept}_{semester}"] = df
            
            # Teacher options
            option = st.selectbox("Choose an option", 
                                  ("Select", "Top 5 students", "Failed students", "Passed students", 
                                   "Average marks", "Above average students", "Below average students", "Summary"))

            file_type = st.selectbox("Select file format for export", ("CSV", "Excel"))

            if option == "Top 5 students":
                top_5_students = df[['NAME', 'GRADE']].nlargest(5, 'GRADE')
                st.write("### Top 5 Students:")
                st.table(top_5_students)

                export_data = export_file(top_5_students, file_type)
                st.download_button(label=f"Download Top 5 Students as {file_type}", data=export_data, file_name=f"top_5_students.{file_type.lower() if file_type == 'CSV' else 'xlsx'}")

            elif option == "Failed students":
                failed_students = df[df['RESULT'] == 'FAIL'][['NAME', 'RESULT']]
                st.write("### Failed Students:")
                st.table(failed_students)

                export_data = export_file(failed_students, file_type)
                st.download_button(label=f"Download Failed Students as {file_type}", data=export_data, file_name=f"failed_students.{file_type.lower() if file_type == 'CSV' else 'xlsx'}")

            elif option == "Passed students":
                passed_students = df[df['RESULT'] == 'PASS'][['NAME', 'RESULT']]
                st.write("### Passed Students:")
                st.table(passed_students)

                export_data = export_file(passed_students, file_type)
                st.download_button(label=f"Download Passed Students as {file_type}", data=export_data, file_name=f"passed_students.{file_type.lower() if file_type == 'CSV' else 'xlsx'}")

            elif option == "Average marks":
                avg_marks = df['GRADE'].mean()
                st.write(f"### Average Marks: {avg_marks:.2f}")

            elif option == "Above average students":
                avg_marks = df['GRADE'].mean()
                above_avg_students = df[df['GRADE'] > avg_marks][['NAME', 'GRADE']]
                st.write(f"### Above Average Students (Grade > {avg_marks:.2f}):")
                st.table(above_avg_students)

                export_data = export_file(above_avg_students, file_type)
                st.download_button(label=f"Download Above Average Students as {file_type}", data=export_data, file_name=f"above_average_students.{file_type.lower() if file_type == 'CSV' else 'xlsx'}")

            elif option == "Below average students":
                avg_marks = df['GRADE'].mean()
                below_avg_students = df[df['GRADE'] < avg_marks][['NAME', 'GRADE']]
                st.write(f"### Below Average Students (Grade < {avg_marks:.2f}):")
                st.table(below_avg_students)

                export_data = export_file(below_avg_students, file_type)
                st.download_button(label=f"Download Below Average Students as {file_type}", data=export_data, file_name=f"below_average_students.{file_type.lower() if file_type == 'CSV' else 'xlsx'}")
            
            elif option == "Summary":
                # Number of passed, failed, and absent students
                num_passed = df[df['RESULT'] == 'PASS'].shape[0]
                num_failed = df[df['RESULT'] == 'FAIL'].shape[0]
                num_absent = df[df['RESULT'] == 'ABSENT'].shape[0]
                total_students = df.shape[0]

                st.write("### Summary of Results")
                st.write(f"**Total Students**: {total_students}")
                st.write(f"**Passed Students**: {num_passed}")
                st.write(f"**Failed Students**: {num_failed}")
                st.write(f"**Absent Students**: {num_absent}")

                # Create a summary dataframe for export
                summary_data = pd.DataFrame({
                    'Total Students': [total_students],
                    'Passed Students': [num_passed],
                    'Failed Students': [num_failed],
                    'Absent Students': [num_absent]
                })

                export_data = export_file(summary_data, file_type)
                st.download_button(label=f"Download Summary as {file_type}", data=export_data, file_name=f"summary.{file_type.lower() if file_type == 'CSV' else 'xlsx'}")

# Student's Dashboard for Result Search
def student_dashboard():
    st.title(f"Welcome, {st.session_state.username} (Student)")
    
    # Display available results (uploaded by teacher)
    if st.session_state.uploaded_results:
        available_results = list(st.session_state.uploaded_results.keys())
        selected_result = st.selectbox("Select available result file", available_results)
        
        if selected_result:
            student_name = st.text_input("Enter your name to search for your result:")
            if student_name:
                df = st.session_state.uploaded_results[selected_result]
                student_result = df[df['NAME'].str.lower() == student_name.lower()]
                
                if not student_result.empty:
                    # Round the 'GRADE' to two decimals
                    student_result['GRADE'] = student_result['GRADE'].round(2)
                    st.write(f"### Result for {student_name}:")
                    st.table(student_result)
                else:
                    st.error(f"No result found for {student_name}")
    else:
        st.warning("No results have been uploaded yet by teachers.")

# Logout function
def logout():
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None

# Main App Logic
if st.session_state.logged_in:
    if st.session_state.role == 'teacher':
        teacher_dashboard()
    elif st.session_state.role == 'student':
        student_dashboard()
    st.button("Logout", on_click=logout)
else:
    login_signup_ui()
