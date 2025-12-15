from flask import Flask, request, send_file
from flask_cors import CORS
import os
from pdf_processor.processor import process_pdf

app = Flask(__name__)
CORS(app)

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Optional but recommended
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB


def cleanup_uploaded_pdfs():
    for filename in os.listdir(UPLOAD_DIR):
        if filename.lower().endswith(".pdf"):
            file_path = os.path.join(UPLOAD_DIR, filename)
            try:
                os.remove(file_path)
            except Exception:
                pass


@app.route("/convert", methods=["POST"])
def convert():
    cleanup_uploaded_pdfs()

    if "file" not in request.files:
        return {"error": "No file uploaded"}, 400

    file = request.files["file"]

    if not file.filename.lower().endswith(".pdf"):
        return {"error": "Only PDF files are allowed"}, 400

    input_path = os.path.join(UPLOAD_DIR, file.filename)
    output_path = os.path.join(UPLOAD_DIR, "output.pdf")

    try:
        file.save(input_path)
        process_pdf(input_path, output_path)
        return send_file(output_path, as_attachment=True)
    finally:
        cleanup_uploaded_pdfs()


@app.route("/", methods=["GET"])
def index():
    cleanup_uploaded_pdfs()
    return {
        "status": "ok",
        "message": "Temporary PDF files cleared"
    }


# DO NOT use app.run() in production (Render uses Gunicorn)
if __name__ == "__main__":
    app.run()