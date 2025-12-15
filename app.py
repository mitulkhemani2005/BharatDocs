from flask import Flask, request, send_file
import os
from pdf_processor.processor import process_pdf

app = Flask(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def cleanup_uploaded_pdfs():
    for filename in os.listdir(UPLOAD_DIR):
        if filename.lower().endswith(".pdf"):
            file_path = os.path.join(UPLOAD_DIR, filename)
            try:
                os.remove(file_path)
            except Exception:
                pass  # fail silently, never crash

@app.route('/convert', methods=['POST'])
def convert():
    cleanup_uploaded_pdfs()
    if "file" not in request.files:
        return {"error": "No file uploaded"}, 400
    file = request.files["file"]
    input_path = os.path.join(UPLOAD_DIR, file.filename)
    file.save(input_path)
    # return {"message": "File uploaded successfully"}
    output_path = os.path.join(UPLOAD_DIR, "output.pdf")
    process_pdf(input_path, output_path)
    return send_file(output_path, as_attachment=True)

@app.route("/", methods=["GET"])
def index():
    cleanup_uploaded_pdfs()
    return {
        "status": "ok",
        "message": "Temporary PDF files cleared"
    }


if __name__ == '__main__':
    app.run(debug=True, port = 5000)