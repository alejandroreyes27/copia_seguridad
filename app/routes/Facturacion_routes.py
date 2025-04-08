from flask import Blueprint, request, redirect, url_for, flash, send_file, current_app
from flask_login import current_user, login_required
from app import db
from app.models.Factura import Factura
from app.models.Detallefactura import DetalleFactura
import datetime
from io import BytesIO
import os

# ReportLab imports para generar el PDF
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

bp = Blueprint('facturacion', __name__, url_prefix='/facturacion')

def generar_factura_pdf(datos):
    """
    Genera un PDF con la factura usando ReportLab.
    Recibe un diccionario 'datos' con la información a imprimir.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    # Encabezado: Logo e información de la empresa
    logo_path = os.path.join(current_app.root_path, "static", "logo.png")
    try:
        im = Image(logo_path, 1.5 * inch, 0.5 * inch)
        story.append(im)
    except Exception as e:
        # Si no se encuentra el logo, continúa sin él.
        print("No se pudo cargar el logo:", e)
    
    story.append(Paragraph("Empresa S.A.", styles['Title']))
    story.append(Paragraph("Dirección: Calle Falsa 123, Ciudad", styles['Normal']))
    story.append(Paragraph("Teléfono: 555-1234", styles['Normal']))
    story.append(Paragraph("Email: info@empresa.com", styles['Normal']))
    story.append(Spacer(1, 12))

    # Información del cliente y factura
    story.append(Paragraph(f"Cliente: {datos['cliente']}", styles['Heading3']))
    story.append(Paragraph(f"Dirección: {datos['direccion']}", styles['Normal']))
    story.append(Paragraph(f"Fecha: {datos['fecha']}", styles['Normal']))
    story.append(Paragraph(f"Factura #: {datos['numero']}", styles['Normal']))
    story.append(Spacer(1, 24))

    # Tabla de productos
    table_data = [['Descripción', 'Cantidad', 'Precio Unitario', 'Total']]
    for item in datos['items']:
        table_data.append([
            item['descripcion'],
            str(item['cantidad']),
            f"${item['precio_unitario']:.2f}",
            f"${item['total']:.2f}"
        ])
    # Totales
    table_data.append(['', '', 'Subtotal:', f"${datos['subtotal']:.2f}"])
    table_data.append(['', '', 'IVA (16%):', f"${datos['iva']:.2f}"])
    table_data.append(['', '', 'Total:', f"${datos['total']:.2f}"])

    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))
    story.append(table)
    story.append(Spacer(1, 24))

    # Notas finales
    story.append(Paragraph("¡Gracias por su compra!", styles['Normal']))
    story.append(Paragraph("Condiciones de pago: 30 días", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer

@bp.route('/comprar', methods=['POST'])
@login_required
def comprar():
    """
    Ruta que procesa la compra desde el carrito.
    Se espera que la solicitud POST incluya información sobre los ítems a facturar.
    """
    # Por ejemplo, imaginemos que el front-end envía un JSON con los ítems seleccionados.
    datos_carrito = request.get_json()
    if not datos_carrito or 'items' not in datos_carrito or len(datos_carrito['items']) == 0:
        flash("No se han seleccionado productos.", "danger")
        return redirect(url_for('carrito.index'))

    # Cálculos de totales (debes ajustar la lógica según tu negocio).
    subtotal = sum(item['cantidad'] * item['precio_unitario'] for item in datos_carrito['items'])
    iva = subtotal * 0.16  # Ejemplo: IVA 16%
    total = subtotal + iva

    # Crear registro de factura
    nueva_factura = Factura(
        user_id=current_user.idUser,
        subtotal=subtotal,
        iva=iva,
        total=total
    )
    db.session.add(nueva_factura)
    db.session.commit()  # Es importante para obtener el ID de la factura

    # Crear registros de detalle de factura
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

    # Preparar los datos para el PDF
    datos_factura = {
        'cliente': current_user.nameUser,            # Asumimos que current_user tiene este atributo
        'direccion': "Dirección del cliente",          # Puedes obtenerlo de current_user o de otro modelo
        'fecha': datetime.datetime.now().strftime("%d/%m/%Y"),
        'numero': f"FAC-{datetime.datetime.now().strftime('%Y%m%d')}-{nueva_factura.id}",
        'items': [{
            'descripcion': item.get('descripcion', "Producto sin descripción"),
            'cantidad': item['cantidad'],
            'precio_unitario': item['precio_unitario'],
            'total': item['cantidad'] * item['precio_unitario']
        } for item in datos_carrito['items']],
        'subtotal': subtotal,
        'iva': iva,
        'total': total
    }

    # Generar el PDF de la factura
    pdf_buffer = generar_factura_pdf(datos_factura)

    # Puedes redirigir a otra página o devolver directamente el PDF
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        download_name='factura.pdf',
        as_attachment=True
    )
