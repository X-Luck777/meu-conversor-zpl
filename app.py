from flask import Flask, render_template, request, Response
import requests
import io
from pypdf import PdfWriter, PdfReader

app = Flask(__name__)

# Configurações
LABELARY_API = "http://api.labelary.com/v1/printers"
LIMIT_PER_REQUEST = 50  # Limite de segurança da API

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/preview', methods=['POST'])
def preview_label():
    raw_zpl = request.form.get('zpl_code', '')
    dpmm = request.form.get('density', '8dpmm')
    width = request.form.get('width', '4')
    height = request.form.get('height', '6')
    
    if not raw_zpl.strip():
        return "Erro: Código ZPL vazio", 400

    # 1. Separa as etiquetas (Split)
    # O ZPL usa ^XZ para indicar o fim de uma etiqueta. Vamos usar isso para contar.
    # Adicionamos o ^XZ de volta porque o split remove.
    labels = [label + '^XZ' for label in raw_zpl.split('^XZ') if label.strip()]
    
    # Se o split gerou algum lixo no final (espaços em branco), removemos
    if labels and not labels[-1].strip().endswith('^XZ'):
        labels.pop()

    # 2. Cria os lotes (Chunks) de 50 em 50
    chunks = [labels[i:i + LIMIT_PER_REQUEST] for i in range(0, len(labels), LIMIT_PER_REQUEST)]
    
    # Preparar o "Juntador" de PDFs
    pdf_merger = PdfWriter()
    
    try:
        url = f"{LABELARY_API}/{dpmm}/labels/{width}x{height}/0/"
        headers = {'Accept': 'application/pdf'}

        # 3. Processa cada lote
        for chunk in chunks:
            # Junta o lote de volta em uma string ZPL única para enviar
            zpl_chunk = '\n'.join(chunk)
            
            response = requests.post(url, headers=headers, data=zpl_chunk, timeout=30)
            
            if response.status_code == 200:
                # Lê o PDF recebido e adiciona ao nosso arquivo final
                chunk_pdf = io.BytesIO(response.content)
                pdf_reader = PdfReader(chunk_pdf)
                for page in pdf_reader.pages:
                    pdf_merger.add_page(page)
            else:
                return f"Erro na API (Lote): {response.text}", 500

        # 4. Finaliza e envia o PDFzão completo
        output_pdf = io.BytesIO()
        pdf_merger.write(output_pdf)
        output_pdf.seek(0)

        return Response(
            output_pdf.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': 'inline; filename=etiquetas_completas.pdf'
            }
        )

    except Exception as e:
        return f"Erro interno: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
