from flask import Blueprint, request, jsonify, current_app
from flask_login import current_user, login_required
from app import db
from app.models.Factura import Factura
from app.models.Detallefactura import DetalleFactura
import datetime
from io import BytesIO
import os
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
import base64

bp = Blueprint('facturacion', __name__, url_prefix='/facturacion')

def generar_factura_pdf(datos):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    style_normal = styles['Normal']
    style_normal.fontName = 'Helvetica'
    style_normal.fontSize = 10
    style_title = styles['Title']
    style_title.fontName = 'Helvetica-Bold'
    style_title.fontSize = 14
    style_heading = styles['Heading3']
    style_heading.fontName = 'Helvetica-Bold'
    style_heading.fontSize = 12

    story = []
    
    # Logo y encabezado
    logo_path = os.path.join(current_app.root_path, "static", "logo.png")
    try:
        im = Image(logo_path, 2 * inch, 0.7 * inch)
        story.append(im)
    except:
        pass

    story.append(Paragraph("Zapatería Estilo S.A.", style_title))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Av. Principal 456, Ciudad Moda", style_normal))
    story.append(Paragraph("Tel: 555-7890 | Email: info@zapateriaestilo.com", style_normal))
    story.append(Spacer(1, 24))

    # Datos del cliente y factura
    data = [
        [Paragraph("Cliente:", style_heading), Paragraph(datos['cliente'], style_normal)],
        [Paragraph("Fecha:", style_heading), Paragraph(datos['fecha'], style_normal)],
        [Paragraph("Factura #", style_heading), Paragraph(datos['numero'], style_normal)]
    ]
    table = Table(data, colWidths=[100, 300])
    table.setStyle(TableStyle([('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold')]))
    story.append(table)
    story.append(Spacer(1, 24))

    # Tabla de productos
    table_data = [['Descripción', 'Cantidad', 'Precio Unitario', 'Total']] + [
        [
            item['descripcion'],
            str(item['cantidad']),
            f"${item['precio_unitario']:,.0f}".replace(",", "."),
            f"${item['total']:,.0f}".replace(",", ".")
        ] for item in datos['items']
    ]
    table = Table(table_data, colWidths=[250, 60, 100, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f8f9fa")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#212529")),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#ffffff")),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#dee2e6")),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    story.append(table)
    story.append(Spacer(1, 24))

    # Totales y notas finales
    total_style = ParagraphStyle(name='Total', fontSize=12, fontName='Helvetica-Bold', alignment=1)
    story.append(Paragraph(f"Subtotal: $ {datos['subtotal']:,.0f}".replace(",", "."), total_style))
    story.append(Paragraph(f"IVA (16%): $ {datos['iva']:,.0f}".replace(",", "."), total_style))
    story.append(Paragraph(f"Total: $ {datos['total']:,.0f}".replace(",", "."), total_style))
    story.append(Spacer(1, 24))
    story.append(Paragraph("¡Gracias por su compra!", style_normal))
    story.append(Paragraph("Política de devolución: 30 días con recibo.", style_normal))
    story.append(Paragraph("www.zapateriaestilo.com", style_normal))

    doc.build(story)
    buffer.seek(0)
    return buffer

@bp.route('/comprar', methods=['POST'])
@login_required
def comprar():
    datos_carrito = request.get_json()
    if not datos_carrito or 'items' not in datos_carrito or len(datos_carrito['items']) == 0:
        return jsonify({'error': 'No hay productos seleccionados'}), 400

    try:
        # Cálculos
        subtotal = sum(item['cantidad'] * item['precio_unitario'] for item in datos_carrito['items'])
        iva = round(subtotal * 0.16)
        total = subtotal + iva

        # Crear factura
        nueva_factura = Factura(
            user_id=current_user.idUser,
            subtotal=subtotal,
            iva=iva,
            total=total
        )
        db.session.add(nueva_factura)
        db.session.commit()

        # Crear detalles
        for item in datos_carrito['items']:
            detalle = DetalleFactura(
                factura_id=nueva_factura.id,
                product_id=item['product_id'],
                quantity=item['cantidad'],
                price=item['precio_unitario'],
                total=item['cantidad'] * item['precio_unitario']
            )
            db.session.add(detalle)
        db.session.commit()

        # Preparar datos para PDF
        datos_factura = {
            'cliente': current_user.nameUser,
            'fecha': datetime.datetime.now().strftime("%d/%m/%Y"),
            'numero': f"FAC-{datetime.datetime.now().strftime('%Y%m%d')}-{nueva_factura.id}",
            'items': [{
                'descripcion': item.get('descripcion', 'Producto'),
                'cantidad': item['cantidad'],
                'precio_unitario': item['precio_unitario'],
                'total': item['cantidad'] * item['precio_unitario']
            } for item in datos_carrito['items']],
            'subtotal': subtotal,
            'iva': iva,
            'total': total
        }

        # Generar PDF y convertir a Base64
        pdf_buffer = generar_factura_pdf(datos_factura)
        pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')

        return jsonify({
            'invoice_data': datos_factura,
            'pdf_base64': pdf_base64
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500