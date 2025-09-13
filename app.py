from flask import Flask, request, render_template, redirect, url_for, jsonify
import fitz  # PyMuPDF
import spacy
from pymongo import MongoClient
import os
import re

app = Flask(__name__)
nlp = spacy.load("en_core_web_sm")

# MongoDB connection
client = MongoClient("mongodb://localhost:27017/")
db = client["resumes_db"]
collection = db["candidates"]

# Extract text from PDF
def extract_text_from_pdf(file_path):
    text = ""
    doc = fitz.open(file_path)
    for page in doc:
        text += page.get_text()
    doc.close()  # Close the document
    return text

# Extract structured info
def extract_info(text):
    doc = nlp(text)
    name = ""
    email = ""
    phone = ""
    skills = []
    education = []
    experience = []
    summary = ""

    for ent in doc.ents:
        if ent.label_ == "PERSON" and not name:
            name = ent.text

    email_match = re.search(r"\b[\w\.-]+@[\w\.-]+\.\w{2,4}\b", text)
    phone_match = re.search(r"\b\d{10}\b", text)
    email = email_match.group() if email_match else ""
    phone = phone_match.group() if phone_match else ""

    sample_skills = [
        "Python", "Java", "SQL", "Excel", "C++", "Machine Learning", 
        "Data Science", "TensorFlow", "Pandas", "Numpy", "Power BI", 
        "React", "Node.js", "JavaScript", "HTML", "CSS", "MongoDB",
        "Flask", "Django", "AWS", "Docker", "Kubernetes", "Git"
    ]
    for skill in sample_skills:
        if skill.lower() in text.lower():
            skills.append(skill)

    education_keywords = ["B.Tech", "M.Tech", "Bachelor", "Master", "PhD", "BSc", "MSc", "MBA", "High School"]
    for line in text.splitlines():
        for keyword in education_keywords:
            if keyword.lower() in line.lower():
                education.append(line.strip())

    experience_keywords = ["experience", "worked", "project", "internship", "job", "role", "position"]
    for line in text.splitlines():
        if any(word in line.lower() for word in experience_keywords):
            experience.append(line.strip())

    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
    summary = paragraphs[0] if paragraphs else ""

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "skills": list(set(skills)),
        "education": list(set(education)),
        "experience": experience[:5],
        "summary": summary
    }

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")  # This will serve your futuristic UI

@app.route("/upload", methods=["POST"])
def upload_resume():
    try:
        if "resume" not in request.files:
            return jsonify({"success": False, "message": "No file uploaded"}), 400

        file = request.files["resume"]
        if file.filename == '':
            return jsonify({"success": False, "message": "No file selected"}), 400

        if not file.filename.lower().endswith('.pdf'):
            return jsonify({"success": False, "message": "Only PDF files are allowed"}), 400

        # Create uploads directory if it doesn't exist
        os.makedirs("uploads", exist_ok=True)
        file_path = os.path.join("uploads", file.filename)
        file.save(file_path)

        try:
            # Extract text and info
            text = extract_text_from_pdf(file_path)
            data = extract_info(text)
            
            # Insert into MongoDB
            result = collection.insert_one(data)
            data['_id'] = str(result.inserted_id)
            
            # Clean up uploaded file
            os.remove(file_path)
            
            return jsonify({"success": True, "data": data})
            
        except Exception as processing_error:
            # Clean up file if processing fails
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({"success": False, "message": f"Processing error: {str(processing_error)}"}), 500
        
    except Exception as e:
        return jsonify({"success": False, "message": f"Upload error: {str(e)}"}), 500

# Optional: Add a route to view all resumes
@app.route("/resumes", methods=["GET"])
def view_resumes():
    try:
        resumes = list(collection.find())
        # Convert ObjectId to string for JSON serialization
        for resume in resumes:
            resume['_id'] = str(resume['_id'])
        return jsonify({"success": True, "resumes": resumes})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)