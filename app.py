from flask import Flask, render_template, request, Response
import requests
import io
from pypdf import PdfWriter, PdfReader

app = Flask(__name__)

# Configurações
LABELARY_API = "http://api.labelary.com/v1/printers"

# Limites de Segurança
# Reduzimos para lotes menores para garantir que etiquetas com imagens passem
MAX_LABELS_PER_BATCH = 10  # Maximo de etiquetas por vez
MAX_BYTES_PER_BATCH = 150000 # 150KB por requisição (Segurança contra erro 413)

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
    # Adicionamos o ^XZ de volta pois o split o remove
    labels = [label + '^XZ' for label in raw_zpl.split('^XZ') if label.strip()]
    
    # Limpeza de espaços extras no final
    if labels and not labels[-1].strip().endswith('^XZ'):
        labels.pop()

    if not labels:
        return "Nenhuma etiqueta válida identificada (faltou ^XZ?)", 400

    # 2. Criação Inteligente de Lotes (Chunking por Tamanho e Quantidade)
    batches = []
    current_batch = []
    current_size = 0
    
    for label in labels:
        label_size = len(label.encode('utf-8')) # Tamanho em bytes
        
        # Verifica se adicionar essa etiqueta estoura o limite de bytes ou de quantidade
        if (current_size + label_size > MAX_BYTES_PER_BATCH) or (len(current_batch) >= MAX_LABELS_PER_BATCH):
            if current_batch: # Salva o lote atual se não estiver vazio
                batches.append(current_batch)
            # Começa um novo lote com a etiqueta atual
            current_batch = [label]
            current_size = label_size
        else:
            # Adiciona ao lote atual
            current_batch.append(label)
            current_size += label_size
            
    if current_batch:
        batches.append(current_batch) # Adiciona o último lote

    # 3. Processamento dos Lotes
    pdf_merger = PdfWriter()
    
    url = f"{LABELARY_API}/{dpmm}/labels/{width}x{height}/0/"
    headers = {'Accept': 'application/pdf'}

    try:
        for i, batch in enumerate(batches):
            zpl_payload = '\n'.join(batch)
            
            # Envia para a API
            response = requests.post(url, headers=headers, data=zpl_payload, timeout=60)
            
            if response.status_code == 200:
                chunk_pdf = io.BytesIO(response.content)
                pdf_reader = PdfReader(chunk_pdf)
                for page in pdf_reader.pages:
                    pdf_merger.add_page(page)
            else:
                # Se der erro, mostramos qual lote falhou
                return f"Erro ao processar o lote {i+1}: A API recusou o tamanho. Tente enviar menos etiquetas.", 500

        # 4. Finalização
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
        return f"Erro interno no servidor: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
