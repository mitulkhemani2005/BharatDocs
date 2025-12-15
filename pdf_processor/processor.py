import fitz

def process_pdf(input_pdf: str, output_pdf: str):
    doc = fitz.open(input_pdf)
    doc.save(output_pdf)
    doc.close()