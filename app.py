from flask import Flask, request, send_file
import os

app = Flask(__name__)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.route('/convert', methods=['POST'])
def convert():
    if "file" not in request.files:
        return {"error": "No file uploaded"}, 400
    file = request.files["file"]
    input_path = os.path.join(UPLOAD_DIR, file.filename)
    file.save(input_path)
    return {"message": "File uploaded successfully"}

if __name__ == '__main__':
    app.run(debug=True, port = 5000)