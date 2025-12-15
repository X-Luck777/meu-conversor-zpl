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

# --- CORREÇÃO DO ERRO "TOO LARGE" ---
# Configura o Flask para aceitar até 50MB de dados (o padrão é pequeno)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/preview', methods=['POST'])
def preview_label():
    try:
        zpl_data = request.form.get('zpl_code', '')
        logo_file = request.files.get('logo_file')
        
        # Prepara a imagem da logo
        logo_img = None
        if logo_file:
            try:
                logo_img = ImageReader(logo_file)
            except Exception as e:
                print(f"Erro ao ler logo: {e}")

        # Configuração da Etiqueta (4x6 polegadas padrão)
        label_width = 4 * inch
        label_height = 6 * inch
        
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=(label_width, label_height))
        
        # Separa as etiquetas pelo delimitador ^XZ
        # Se não tiver ^XZ, assume que é uma etiqueta só
        labels = [l for l in zpl_data.split('^XZ') if l.strip()]
        if not labels:
            labels = [zpl_data]

        for label_zpl in labels:
            draw_label(c, label_zpl, label_height, logo_img)
            c.showPage()

        c.save()
        buffer.seek(0)

        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={'Content-Disposition': 'inline; filename=etiquetas_pro_v2.pdf'}
        )
    except Exception as e:
        # Em caso de erro grave, retorna o erro na tela em vez de travar
        return f"Erro Interno do Servidor: {str(e)}", 500

def draw_label(c, zpl, label_h, logo_img):
    """Renderiza Textos e Barcodes"""
    
    # Desenha a logo se existir
    if logo_img:
        try:
            c.drawImage(logo_img, 10, label_h - 60, width=50, height=50, mask='auto', preserveAspectRatio=True)
        except:
            pass

    # Regex simples para pegar comandos ZPL
    commands = re.split(r'\^(?=[A-Z]{2})', zpl)
    
    current_x = 10
    current_y = label_h - 10
    font_size = 10
    
    for cmd in commands:
        if not cmd: continue
        try:
            cmd_type = cmd[:2]
            params_str = cmd[2:]
            params = params_str.split(',')
            
            # --- POSICIONAMENTO (^FO ou ^FT) ---
            if cmd_type == 'FO' or cmd_type == 'FT':
                try:
                    x = int(params[0])
                    y = int(params[1])
                    current_x = x * 0.35 # Conversão dots -> points
                    current_y = label_h - (y * 0.35)
                except:
                    pass

            # --- TAMANHO DA FONTE (^A0, ^CF) ---
            elif cmd_type == 'CF' or cmd_type == 'A0':
                try:
                    h = int(params[0]) if params[0].isdigit() else 20
                    font_size = h * 0.8
                    if font_size < 6: font_size = 6
                except:
                    pass
            
            # --- DADOS DE TEXTO (^FD) ---
            elif cmd_type == 'FD':
                text_content = params_str.split('^FS')[0]
                
                # --- CORREÇÃO DAS PÁGINAS EM BRANCO ---
                # Removido o filtro agressivo. Agora só ignoramos se for
                # um bloco GIGANTE sem espaços (provavelmente imagem hexadecimal)
                if len(text_content) > 200 and ' ' not in text_content:
                    continue # Ignora lixo hexadecimal da imagem antiga

                c.setFont("Helvetica-Bold", font_size)
                c.drawString(current_x, current_y - font_size, text_content)

            # --- CÓDIGO DE BARRAS (^BC) ---
            elif cmd_type == 'BC':
                # Procura o conteúdo do código de barras no próximo ^FD
                snippet = zpl[zpl.find(cmd):]
                match = re.search(r'\^FD(.*?)\^FS', snippet)
                
                if match:
                    code_data = match.group(1)
                    # Limpeza básica para Code128
                    code_data = re.sub(r'[^\x00-\x7F]+', '', code_data)
                    
                    if code_data:
                        rv = io.BytesIO()
                        Code128 = barcode.get_barcode_class('code128')
                        writer = ImageWriter()
                        bc = Code128(code_data, writer=writer)
                        # Gera barcode limpo
                        bc.write(rv, options={'write_text': False, 'module_height': 8.0, 'module_width': 0.3, 'quiet_zone': 1.0})
                        rv.seek(0)
                        
                        bc_img = ImageReader(rv)
                        c.drawImage(bc_img, current_x, current_y - 40, width=150, height=40)

        except Exception:
            pass # Continua desenhando o resto se um comando falhar
