from flask import Flask, render_template, request, Response
import io
import re
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
import barcode
from barcode.writer import ImageWriter
from PIL import Image

app = Flask(__name__)

# [IMPORTANTE] Libera uploads de até 50MB
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/preview', methods=['POST'])
def preview_label():
    try:
        zpl_data = request.form.get('zpl_code', '')
        logo_file = request.files.get('logo_file')
        
        logo_img = None
        if logo_file:
            try:
                logo_img = ImageReader(logo_file)
            except: pass

        # Configurações da Etiqueta
        label_width = 4 * inch
        label_height = 6 * inch
        
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(label_width, label_height))
        
        labels = [l for l in zpl_data.split('^XZ') if l.strip()]
        if not labels: labels = [zpl_data]

        for label_zpl in labels:
            draw_label(c, label_zpl, label_height, logo_img)
            c.showPage()

        c.save()
        buffer.seek(0)

        return Response(buffer.getvalue(), mimetype='application/pdf',
                        headers={'Content-Disposition': 'inline; filename=etiqueta.pdf'})
    except Exception as e:
        return f"Erro Interno: {str(e)}", 500

def draw_label(c, zpl, label_h, logo_img):
    if logo_img:
        try: c.drawImage(logo_img, 10, label_h - 60, width=50, height=50, mask='auto', preserveAspectRatio=True)
        except: pass

    commands = re.split(r'\^(?=[A-Z]{2})', zpl)
    current_x, current_y, font_size = 10, label_h - 10, 10
    
    for cmd in commands:
        if not cmd: continue
        try:
            cmd_type = cmd[:2]
            params = cmd[2:].split(',')
            
            if cmd_type in ['FO', 'FT']:
                try:
                    current_x = int(params[0]) * 0.35
                    current_y = label_h - (int(params[1]) * 0.35)
                except: pass
            
            elif cmd_type in ['CF', 'A0']:
                try: font_size = int(params[0]) * 0.8
                except: pass

            elif cmd_type == 'FD':
                text = cmd[2:].split('^FS')[0]
                # SEU ERRO ESTAVA AQUI: Removemos o filtro que apagava o texto
                c.setFont("Helvetica-Bold", max(font_size, 6))
                c.drawString(current_x, current_y - font_size, text)

            elif cmd_type == 'BC':
                match = re.search(r'\^FD(.*?)\^FS', zpl[zpl.find(cmd):])
                if match:
                    code = re.sub(r'[^\x00-\x7F]+', '', match.group(1))
                    if code:
                        rv = io.BytesIO()
                        writer = ImageWriter()
                        barcode.get_barcode_class('code128')(code, writer=writer).write(rv, options={'write_text':False, 'module_height':8.0, 'module_width':0.3})
                        rv.seek(0)
                        c.drawImage(ImageReader(rv), current_x, current_y-40, width=150, height=40)
        except: pass
