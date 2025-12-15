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

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/preview', methods=['POST'])
def preview_label():
    zpl_data = request.form.get('zpl_code', '')
    logo_file = request.files.get('logo_file') # Recebe a logo (opcional)
    
    # Prepara a imagem da logo se foi enviada
    logo_img = None
    if logo_file:
        try:
            logo_img = ImageReader(logo_file)
        except:
            pass

    # Configuração da Etiqueta (Padrão 4x6 polegadas = 10x15cm)
    label_width = 4 * inch
    label_height = 6 * inch
    
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(label_width, label_height))
    
    # Separa as etiquetas
    labels = [l for l in zpl_data.split('^XZ') if l.strip()]

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
    """Renderiza Textos, Barcodes e QR Codes localmente"""
    
    # 1. Se tiver logo, desenha ela no topo esquerdo (padrão de logística)
    if logo_img:
        # Ajuste a posição (x, y, largura, altura) conforme sua necessidade
        c.drawImage(logo_img, 10, label_h - 60, width=50, height=50, mask='auto')

    # Regex para capturar comandos
    commands = re.split(r'\^(?=[A-Z]{2})', zpl)
    
    current_x = 0
    current_y = 0
    font_size = 10
    
    for cmd in commands:
        if not cmd: continue
        try:
            cmd_type = cmd[:2]
            params = cmd[2:].split(',')
            
            # --- POSIÇÃO (^FO) ---
            if cmd_type == 'FO':
                # Conversão aproximada: 1 dot = 0.35mm (para impressoras 203dpi)
                current_x = int(params[0]) * 0.35 
                # Inverte o Y (PDF cresce pra cima, ZPL cresce pra baixo)
                current_y = label_h - (int(params[1]) * 0.35)

            # --- FONTE (^A0, ^CF) ---
            elif cmd_type == 'CF' or cmd_type == 'A0':
                h = int(params[0]) if params[0].isdigit() else 20
                font_size = h * 0.8
            
            # --- TEXTO (^FD) ---
            elif cmd_type == 'FD':
                text = cmd[2:].split('^')[0]
                c.setFont("Helvetica-Bold", font_size)
                # Verifica se é hexadecimal puro (às vezes acontece)
                if not re.match(r'^[0-9A-F]+$', text): 
                    c.drawString(current_x, current_y - font_size, text)

            # --- CÓDIGO DE BARRAS 128 (^BC) ---
            elif cmd_type == 'BC':
                # O texto do barcode geralmente vem no próximo ^FD
                # Vamos procurar o próximo FD neste trecho
                match = re.search(r'\^FD(.*?)\^FS', zpl[zpl.find(cmd):])
                if match:
                    code_data = match.group(1)
                    # Gera o barcode na memória
                    rv = io.BytesIO()
                    Code128 = barcode.get_barcode_class('code128')
                    writer = ImageWriter()
                    # Configurações para o barcode ficar limpo (sem texto embaixo se quiser)
                    bc = Code128(code_data, writer=writer)
                    bc.write(rv, options={'write_text': False, 'module_height': 10.0, 'module_width': 0.3})
                    rv.seek(0)
                    
                    # Desenha no PDF
                    bc_img = ImageReader(rv)
                    # Ajuste de tamanho do barcode
                    c.drawImage(bc_img, current_x, current_y - 50, width=150, height=40)

            # --- QR CODE (^BQ) ---
            elif cmd_type == 'BQ':
                # QR Code no ZPL é chato, ele pede o conteudo no ^FD seguinte
                match = re.search(r'\^FD(.*?)\^FS', zpl[zpl.find(cmd):])
                if match:
                    qr_data = match.group(1)
                    # Alguns ZPLs de QR começam com QA,QM... removemos isso
                    if len(qr_data) > 3 and qr_data[2] == ',': qr_data = qr_data[3:]
                    
                    # Gera QR
                    qr = qrcode.make(qr_data)
                    qr_mem = io.BytesIO()
                    qr.save(qr_mem, format='PNG')
                    qr_mem.seek(0)
                    
                    c.drawImage(ImageReader(qr_mem), current_x, current_y - 80, width=80, height=80)

        except Exception as e:
            # Ignora erros de parsing para não travar a etiqueta toda
            pass
