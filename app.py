from flask import Flask, render_template, request, Response
import requests

app = Flask(__name__)

# Configurações
LABELARY_API = "http://api.labelary.com/v1/printers"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/preview', methods=['POST'])
def preview_label():
    """
    Recebe o ZPL do formulário e retorna o PDF binário.
    """
    zpl = request.form.get('zpl_code', '')
    dpmm = request.form.get('density', '8dpmm') # 8dpmm = 203dpi
    width = request.form.get('width', '4')
    height = request.form.get('height', '6')
    
    if not zpl.strip():
        return "Erro: Código ZPL vazio", 400

    # Monta a URL da API (aqui você poderia substituir por um conversor local no futuro)
    url = f"{LABELARY_API}/{dpmm}/labels/{width}x{height}/0/"
    
    headers = {'Accept': 'application/pdf'}
    
    try:
        # Faz a requisição para o motor de renderização
        response = requests.post(url, headers=headers, data=zpl, timeout=10)
        
        if response.status_code == 200:
            # Retorna o PDF com o cabeçalho correto para o navegador abrir
            return Response(
                response.content,
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': 'inline; filename=etiqueta.pdf'
                }
            )
        else:
            return f"Erro na renderização: {response.text}", 500
            
    except requests.exceptions.RequestException as e:
        return "Erro de conexão com o servidor de renderização.", 502

if __name__ == '__main__':
    # Em produção, você usaria gunicorn, não app.run
    app.run(debug=True, host='0.0.0.0', port=5000)