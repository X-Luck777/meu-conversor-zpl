from flask import Flask, render_template, request, Response
import io
import re
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch, mm
from reportlab.lib.utils import ImageReader
import barcode
from barcode.writer import ImageWriter
import qrcode
from PIL import Image

app = Flask(__name__)

# Aumenta o limite de upload para 16MB (evita erro 413 do Flask)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/preview', methods=['POST'])
def preview_label():
    zpl_data = request.form.get('zpl_code', '')
    logo_file = request.files.get('logo_file')
    
    # Prepara a imagem da logo
    logo_img = None
    if logo_file:
        try:
            logo_img = ImageReader(logo_file)
        except:
            pass

    # Configuração da Etiqueta (4x6 polegadas)
    label_width = 4 * inch
    label_height = 6 * inch
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(label_width, label_height))
    
    # Separa as etiquetas pelo delimitador ^XZ
    labels = [l for l in zpl_data.split('^XZ') if l.strip()]

    if not labels:
        # Se não achou ^XZ, tenta processar tudo como uma única etiqueta
        labels = [zpl_data]

    for label_zpl in labels:
        draw_label(c, label_zpl, label_height, logo_img)
        c.showPage()

    c.save()
    buffer.seek(0)

    return Response(
        buffer.getvalue(),
        mimetype='application/pdf',
        headers={'Content-Disposition': 'inline; filename=etiquetas_pro.pdf'}
    )

def draw_label(c, zpl, label_h, logo_img):
    """Renderiza Textos e Barcodes"""
    
    if logo_img:
        c.drawImage(logo_img, 10, label_h - 60, width=50, height=50, mask='auto', preserveAspectRatio=True)

    # Regex simples para pegar comandos ZPL (^XX)
    # Procuramos por ^comando seguido de parametros
    commands = re.split(r'\^(?=[A-Z]{2})', zpl)
    
    current_x = 10 # Posição padrão segura
    current_y = label_h - 10
    font_size = 10
    
    for cmd in commands:
        if not cmd: continue
        try:
            cmd_type = cmd[:2] # Os dois primeiros caracteres são o comando
            params_str = cmd[2:] # O resto são parametros
            params = params_str.split(',')
            
            # --- POSICIONAMENTO (^FO ou ^FT) ---
            if cmd_type == 'FO' or cmd_type == 'FT':
                # Converte dots (203dpi) para pontos PDF (72dpi)
                # Fator: 72 / 203 ≈ 0.35
                try:
                    x = int(params[0])
                    y = int(params[1])
                    current_x = x * 0.35
                    # Inverte eixo Y
                    current_y = label_h - (y * 0.35)
                except:
                    pass

            # --- TAMANHO DA FONTE (^A0, ^CF) ---
            elif cmd_type == 'CF' or cmd_type == 'A0':
                try:
                    h = int(params[0]) if params[0].isdigit() else 20
                    font_size = h * 0.8
                    if font_size < 6: font_size = 6 # Mínimo legível
                except:
                    pass
            
            # --- DADOS DE TEXTO (^FD) ---
            elif cmd_type == 'FD':
                # Pega tudo até o ^FS
                text_content = params_str.split('^FS')[0]
                
                # [CORREÇÃO] Removemos o filtro de hexadecimal que estava apagando textos válidos
                # Apenas ignoramos se for MUITO longo e sem espaços (provavel imagem)
                if len(text_content) > 100 and ' ' not in text_content:
                    continue

                c.setFont("Helvetica-Bold", font_size)
                c.drawString(current_x, current_y - font_size, text_content)

            # --- CÓDIGO DE BARRAS (^BC) ---
            elif cmd_type == 'BC':
                # Tenta achar o conteudo no ^FD que vem logo depois
                # Procuramos na string original do ZPL a partir deste ponto
                snippet = zpl[zpl.find(cmd):]
                match = re.search(r'\^FD(.*?)\^FS', snippet)
                
                if match:
                    code_data = match.group(1)
                    # Limpa caracteres invalidos para barcode 128
                    code_data = re.sub(r'[^\x00-\x7F]+', '', code_data) 
                    
                    if code_data:
                        rv = io.BytesIO()
                        Code128 = barcode.get_barcode_class('code128')
                        writer = ImageWriter()
                        # Gera barcode sem texto embaixo para não sobrepor
                        bc = Code128(code_data, writer=writer)
                        bc.write(rv, options={'write_text': False, 'module_height': 8.0, 'module_width': 0.3, 'quiet_zone': 1.0})
                        rv.seek(0)
                        
                        bc_img = ImageReader(rv)
                        c.drawImage(bc_img, current_x, current_y - 40, width=150, height=40)

        except Exception as e:
            # Se um comando falhar, ignora e vai pro proximo
            # print(f"Erro no comando {cmd[:5]}: {e}") # Debug local
            pass
